"""
engine/ai.py — Claude AI engine.
- Haiku for all customer replies (cheap, fast, capable)
- Sonnet only for code editor (needs stronger reasoning)
- System prompt cached until settings change
- Thread history capped at last 6 messages to control costs
- Tracks estimated token usage for dashboard cost display
"""

import os

try:
    import anthropic
except ImportError:
    anthropic = None

REPLY_MODEL  = "claude-haiku-4-5-20251001"   # ~$0.80/1M in, $4/1M out
EDITOR_MODEL = "claude-sonnet-4-6"            # ~$3/1M in, $15/1M out

# Approximate cost per 1M tokens (USD)
COSTS = {
    REPLY_MODEL:  {"in": 0.80,  "out": 4.00},
    EDITOR_MODEL: {"in": 3.00,  "out": 15.00},
}

MAX_THREAD_MESSAGES = 6   # keep last N messages to cap input tokens


class AIEngine:
    def __init__(self, secrets: dict, settings: dict):
        self.secrets          = secrets
        self.settings         = settings
        self._cached_prompt   = None
        self._cached_settings = None   # settings snapshot for cache invalidation
        self.session_cost_usd = 0.0    # running cost this session

    def _client(self):
        if not anthropic:
            raise RuntimeError("pip install anthropic")
        key = self.secrets.get("claude_api_key", "")
        if not key:
            raise RuntimeError("Claude API key not set in Settings → Credentials.")
        return anthropic.Anthropic(api_key=key)

    def _system_prompt(self, source: str = "Email") -> str:
        # Cache until settings change
        sig = (
            self.settings.get("ai_sales_style", ""),
            self.settings.get("ai_business_facts", ""),
            self.settings.get("ai_handoff_rules", ""),
            source,
        )
        if self._cached_settings == sig and self._cached_prompt:
            return self._cached_prompt

        sales   = self.settings.get("ai_sales_style", "")
        facts   = self.settings.get("ai_business_facts", "")
        handoff = self.settings.get("ai_handoff_rules", "")

        prompt = (
            f"You are the automated sales assistant for El Hombre Taco.\n\n"
            f"=== BUSINESS FACTS ===\n{facts}\n\n"
            f"=== SALES STYLE & TONE ===\n{sales}\n\n"
            f"=== INVOICE EXTRACTION ===\n"
            f"For every message, output line 1 as INVOICE:YES or INVOICE:NO.\n"
            f"INVOICE:YES only when you have: name, email, event type, AND approximate date or guest count.\n"
            f"If YES, lines 2-8 must be:\n"
            f"NAME: / EMAIL: / PHONE: / EVENT: / DATE: / GUESTS: / NOTES:\n"
            f"Then write your reply on the lines that follow.\n\n"
            f"=== HANDOFF RULES ===\n{handoff}\n\n"
            f"=== FILTERING (Meta messages only) ===\n"
            f"For Instagram/Facebook: skip story mentions, emoji-only, generic greetings, "
            f"and spam. Only respond to real catering inquiries. "
            f"If you skip a message, output: SKIP:YES and REASON: <one line>.\n\n"
            f"Source channel for this conversation: {source}"
        )
        self._cached_settings = sig
        self._cached_prompt   = prompt
        return prompt

    def invalidate_cache(self):
        """Call this after settings are saved."""
        self._cached_prompt   = None
        self._cached_settings = None

    def reply(self, thread: list, source: str = "Email") -> str:
        """
        thread: list of {"role": "user"|"assistant", "content": str}
        Caps to last MAX_THREAD_MESSAGES before sending.
        Returns raw AI text (caller parses INVOICE/HANDOFF/SKIP lines).
        Tracks estimated cost.
        """
        cl = self._client()

        # Cap thread to last N messages to control token cost
        capped = thread[-MAX_THREAD_MESSAGES:] if len(thread) > MAX_THREAD_MESSAGES else thread

        resp = cl.messages.create(
            model      = REPLY_MODEL,
            max_tokens = 600,          # replies are short; 600 is plenty
            system     = self._system_prompt(source),
            messages   = capped,
        )
        raw = resp.content[0].text.strip()

        # Track cost estimate
        usage = resp.usage
        cost  = self._estimate_cost(REPLY_MODEL, usage.input_tokens, usage.output_tokens)
        self.session_cost_usd += cost

        return raw

    def parse_response(self, raw: str) -> dict:
        """
        Parse the structured header lines from AI output.
        Returns dict with keys:
          invoice_ok, fields, skip, skip_reason, handoff, handoff_reason, reply_text
        """
        lines = raw.splitlines()
        result = {
            "invoice_ok":     False,
            "fields":         {},
            "skip":           False,
            "skip_reason":    "",
            "handoff":        False,
            "handoff_reason": "",
            "reply_text":     "",
        }
        reply_lines = []
        field_keys  = {"NAME", "EMAIL", "PHONE", "EVENT", "DATE", "GUESTS", "NOTES"}

        for line in lines:
            up = line.strip().upper()
            if up.startswith("INVOICE:YES"):
                result["invoice_ok"] = True
            elif up.startswith("INVOICE:NO"):
                pass
            elif up.startswith("SKIP:YES"):
                result["skip"] = True
            elif up.startswith("REASON:"):
                txt = line.partition(":")[2].strip()
                if result["skip"] and not result["skip_reason"]:
                    result["skip_reason"] = txt
                elif result["handoff"] and not result["handoff_reason"]:
                    result["handoff_reason"] = txt
            elif up.startswith("HANDOFF:YES"):
                result["handoff"] = True
            elif any(line.startswith(k + ":") for k in field_keys):
                k, _, v = line.partition(":")
                result["fields"][k.strip().lower()] = v.strip()
            else:
                reply_lines.append(line)

        result["reply_text"] = "\n".join(reply_lines).strip()
        return result

    # ── Code editor (Sonnet only) ─────────────────────────────────────────────

    def edit_file(self, filepath: str, instruction: str) -> str:
        """
        Ask Claude Sonnet to edit a single source file.
        Returns new file contents. Raises RuntimeError if output too short.
        """
        cl = self._client()
        with open(filepath, encoding="utf-8") as f:
            src = f.read()
        n = len(src.splitlines())
        prompt = (
            f"You are a Python code editor. Edit this file per the instruction below.\n"
            f"Instruction: {instruction}\n\n"
            f"RULES:\n"
            f"1. Return ONLY raw Python — no markdown, no explanation.\n"
            f"2. Output the COMPLETE file. Original is {n} lines; output at least {int(n*0.85)} lines.\n"
            f"3. Never summarise omitted sections.\n\n"
            f"FILE: {os.path.basename(filepath)}\n\n{src}"
        )
        resp = cl.messages.create(
            model      = EDITOR_MODEL,
            max_tokens = 4000,
            messages   = [{"role": "user", "content": prompt}],
        )
        result = resp.content[0].text.strip()
        if result.startswith("```"):
            result = "\n".join(result.splitlines()[1:])
        if result.endswith("```"):
            result = "\n".join(result.splitlines()[:-1])
        result = result.strip()

        # Track cost
        usage = resp.usage
        cost  = self._estimate_cost(EDITOR_MODEL, usage.input_tokens, usage.output_tokens)
        self.session_cost_usd += cost

        out_lines = len(result.splitlines())
        if out_lines < int(n * 0.75):
            raise RuntimeError(
                f"AI returned only {out_lines} lines (original: {n}). "
                "Edit aborted to protect your file."
            )
        return result

    # ── Cost tracking ─────────────────────────────────────────────────────────

    @staticmethod
    def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        rates = COSTS.get(model, {"in": 3.0, "out": 15.0})
        return (input_tokens / 1_000_000 * rates["in"] +
                output_tokens / 1_000_000 * rates["out"])
