"""
ui/app.py — ElHombreApp shell.
Tab switching, inbound message handler, multi-turn AI, handoff escalation,
owner email approval polling, file backup before AI edits.
"""

import tkinter as tk
from datetime import datetime

import config as cfg_module
from theme import C, FONT
from ui.widgets import btn

from ui.dashboard  import DashboardTab
from ui.messaging  import MessagingTab
from ui.invoices   import InvoicesTab
from ui.metrics    import MetricsTab
from ui.calendar   import CalendarTab
from ui.directory  import DirectoryTab
from ui.settings   import SettingsTab

from engine.ai        import AIEngine
from engine.email_bot import EmailBot
from engine.meta_bot  import MetaBot


TAB_NAMES = ["Dashboard", "Messaging", "Calendar", "Invoices", "Metrics", "Directory", "Settings"]


class ElHombreApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("El Hombre Taco — Dashboard")
        root.configure(bg=C["bg"])
        root.geometry("1280x820")
        root.minsize(1024, 700)

        # Load config
        self.secrets  = cfg_module.load_secrets()
        self.settings = cfg_module.load_settings()
        self.state    = cfg_module.load_state()

        # Ensure counters exist
        self.state.setdefault("ai_reply_count",       0)
        self.state.setdefault("ai_invoices_approved", 0)
        self.state.setdefault("ai_invoices_paid",     0)

        # Bot vars
        self.email_bot_var = tk.BooleanVar(value=self.settings.get("email_bot_on", False))
        self.ig_bot_var    = tk.BooleanVar(value=self.settings.get("ig_bot_on",    False))
        self.fb_bot_var    = tk.BooleanVar(value=self.settings.get("fb_bot_on",    False))
        self.global_ai_var = tk.BooleanVar(value=self.settings.get("global_ai_on", True))
        self.auto_inv_var  = tk.BooleanVar(value=self.settings.get("auto_invoice",  True))

        self._build_engines()
        self._build_ui()
        self._maybe_start_bots()
        self._poll_owner_approvals()

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── Engine init / rebuild ─────────────────────────────────────────────────

    def _build_engines(self):
        self.ai        = AIEngine(self.secrets, self.settings)
        self.email_bot = EmailBot(self.secrets, self.settings, self._on_inbound)
        self.meta_bot  = MetaBot(self.secrets,  self.settings, self._on_inbound)

    def _rebuild_engines(self):
        self.email_bot.stop()
        self.meta_bot.stop()
        self.ai        = AIEngine(self.secrets, self.settings)
        self.ai.invalidate_cache()
        self.email_bot = EmailBot(self.secrets, self.settings, self._on_inbound)
        self.meta_bot  = MetaBot(self.secrets,  self.settings, self._on_inbound)
        self._maybe_start_bots()

    def _maybe_start_bots(self):
        if self.email_bot_var.get():
            self.email_bot.start()
        if self.fb_bot_var.get() or self.ig_bot_var.get():
            self.meta_bot.start()

    # ── UI Shell ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=C["sidebar"], height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="EL HOMBRE TACO", bg=C["sidebar"], fg="white",
                 font=("Helvetica", 16, "bold"), padx=20).pack(side="left", pady=14)
        tk.Label(hdr, text="Business Dashboard", bg=C["sidebar"],
                 fg="#9CA3AF", font=FONT["small"]).pack(side="left")
        self._status_lbl = tk.Label(hdr, text="● Idle", bg=C["sidebar"],
                                    fg="#6EE7B7", font=FONT["tiny"], padx=20)
        self._status_lbl.pack(side="right", pady=14)

        # Tab bar
        tab_bar = tk.Frame(self.root, bg=C["panel"], height=44)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x")

        self._tab_btns   = {}
        self._tab_frames = {}
        for name in TAB_NAMES:
            b = tk.Label(tab_bar, text=name, bg=C["panel"], fg=C["muted"],
                         font=FONT["small"], cursor="hand2", padx=18, pady=14)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, n=name: self.switch_tab(n))
            self._tab_btns[name] = b

        content = tk.Frame(self.root, bg=C["bg"])
        content.pack(fill="both", expand=True)
        for name in TAB_NAMES:
            f = tk.Frame(content, bg=C["bg"])
            f.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._tab_frames[name] = f

        # Build each tab
        self.dashboard_tab  = DashboardTab(self);  self.dashboard_tab.build(self._tab_frames["Dashboard"])
        self.messaging_tab  = MessagingTab(self);  self.messaging_tab.build(self._tab_frames["Messaging"])
        self.calendar_tab   = CalendarTab(self);   self.calendar_tab.build(self._tab_frames["Calendar"])
        self.invoice_tab    = InvoicesTab(self);   self.invoice_tab.build(self._tab_frames["Invoices"])
        self.metrics_tab    = MetricsTab(self);    self.metrics_tab.build(self._tab_frames["Metrics"])
        self.directory_tab  = DirectoryTab(self);  self.directory_tab.build(self._tab_frames["Directory"])
        self.settings_tab   = SettingsTab(self);   self.settings_tab.build(self._tab_frames["Settings"])

        self.switch_tab("Dashboard")

    def switch_tab(self, name: str):
        for n, b in self._tab_btns.items():
            active = n == name
            b.config(
                fg=C["accent"] if active else C["muted"],
                font=("Helvetica", 10, "bold") if active else FONT["small"],
                bg=C["bg"] if active else C["panel"],
            )
        self._tab_frames[name].lift()

    def set_status(self, text: str, color: str = "success"):
        self._status_lbl.config(text=f"● {text}", fg=C.get(color, C["success"]))

    def log_activity(self, icon: str, title: str, sub: str):
        ts = datetime.now().strftime("%I:%M %p")
        self.state.setdefault("activity_log", []).insert(0, (ts, icon, title, sub))
        self.state["activity_log"] = self.state["activity_log"][:100]

    def save(self):
        cfg_module.save_state(self.state)

    def update_customer_from_invoice(self, inv: dict):
        self.directory_tab.update_from_invoice(inv)

    # ── Inbound message handler ───────────────────────────────────────────────

    def _on_inbound(self, msg_data, system_text, kind):
        if kind == "system":
            self.root.after(0, lambda t=system_text: self.set_status(t[:50], "muted"))
            return
        self.root.after(0, lambda m=msg_data: self._process(m))

    def _process(self, msg_data: dict):
        source  = msg_data.get("source", "Email")
        sender  = msg_data.get("sender", "Unknown")
        body    = msg_data.get("body",   "")
        subject = msg_data.get("subject","")

        # Store in master inbox
        self.state.setdefault("messages", []).insert(0, {
            "source": source, "sender": sender,
            "body": body, "subject": subject,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "unprocessed",
        })

        self.set_status(f"Processing {source} from {sender}", "warn")
        self.log_activity("📨", f"New {source} — {sender}", body[:40])

        # Find or create conversation (thread by email/sender)
        convos = self.state.setdefault("conversations", [])
        conv   = next((c for c in convos if c.get("email") == sender), None)
        if not conv:
            conv = {
                "id":        f"c{len(convos) + 1}",
                "name":      sender,
                "email":     sender,
                "source":    source,
                "subject":   subject,
                "last_msg":  body,
                "last_time": datetime.now().strftime("%I:%M %p"),
                "ai_assist": True,
                "status":    "active",
                "messages":  [],
                "raw":       msg_data,
            }
            convos.insert(0, conv)
        conv["messages"].append({
            "from": "customer", "text": body,
            "time": datetime.now().strftime("%I:%M %p"),
        })
        conv["last_msg"]  = body
        conv["last_time"] = datetime.now().strftime("%I:%M %p")
        conv["last_message_id"] = msg_data.get("message_id", "")

        # Skip AI if disabled for this thread or globally
        if not conv.get("ai_assist", True) or not self.global_ai_var.get():
            self.state["messages"][0]["status"] = "ai_disabled"
            self._refresh_ui()
            return

        # ── Check if requested date is a blackout ────────────────────────
        import re as _re
        date_match = _re.search(r'\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})\b', body)
        if date_match and hasattr(self, "calendar_tab"):
            raw_date = date_match.group(0)
            parsed_date = None
            for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
                try:
                    parsed_date = datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                    break
                except Exception:
                    pass
            if parsed_date and self.calendar_tab.is_blackout(parsed_date):
                conv["status"] = "needs_owner"
                self.log_activity("🚫", f"Blackout date — {sender}",
                                  f"Requested {parsed_date} is blacked out")
                self._send_handoff_alert(conv,
                    f"Customer requested a blacked-out date: {parsed_date}")
                self._refresh_ui()
                self.save()
                return

        # ── AI reply ──────────────────────────────────────────────────────────
        try:
            self.set_status("AI composing reply…", "gold")

            # Build thread history for multi-turn
            thread = []
            for m in conv["messages"]:
                role    = "assistant" if m["from"] in ("ai", "manual") else "user"
                thread.append({"role": role, "content": m["text"]})

            raw    = self.ai.reply(thread, source)
            parsed = self.ai.parse_response(raw)

            # ── Filtered / skipped (Meta only) ──────────────────────────────
            if parsed["skip"]:
                conv["status"] = "ignored"
                conv["messages"][-1]["skip_reason"] = parsed["skip_reason"]
                self.state["messages"][0]["status"] = "ignored"
                self.log_activity("🚫", f"AI skipped {source} from {sender}",
                                  parsed["skip_reason"])
                self._refresh_ui()
                self.save()
                return

            # ── Handoff ──────────────────────────────────────────────────────
            if parsed["handoff"]:
                conv["status"] = "needs_owner"
                self.state["messages"][0]["status"] = "needs_owner"
                self.log_activity("⚠", f"Handoff — {sender}", parsed["handoff_reason"])
                self._send_handoff_alert(conv, parsed["handoff_reason"])
                self._refresh_ui()
                self.save()
                return

            reply_text = parsed["reply_text"]
            if not reply_text:
                return

            # ── Send reply ───────────────────────────────────────────────────
            conv["messages"].append({
                "from": "ai", "text": reply_text,
                "time": datetime.now().strftime("%I:%M %p"),
            })
            conv["last_msg"]  = reply_text
            conv["last_time"] = datetime.now().strftime("%I:%M %p")

            # Increment AI reply count (used for lead metric)
            self.state["ai_reply_count"] = self.state.get("ai_reply_count", 0) + 1
            self.state["messages"][0]["status"] = "replied"

            cost_str = f"${self.ai.session_cost_usd:.4f} session"
            self.log_activity("🤖", f"AI replied to {sender}", reply_text[:40])
            self.set_status(f"Replied · {cost_str}", "success")

            sent_id = ""
            if source == "Email":
                try:
                    sent_id = self.email_bot.send_reply(
                        sender, subject, reply_text,
                        in_reply_to=msg_data.get("message_id", ""))
                    conv["last_message_id"] = sent_id
                    self.email_bot.record_reply(sender.lower())
                    self.log_activity("📤", f"Reply sent → {sender}", "")
                except Exception as ex:
                    self.log_activity("⚠", "Email send failed", str(ex))
            else:
                try:
                    self.meta_bot.send_reply(msg_data, reply_text)
                    self.log_activity("📤", f"Meta reply → {sender}", "")
                except Exception as ex:
                    self.log_activity("⚠", "Meta reply failed", str(ex))

            # ── Auto-draft invoice ───────────────────────────────────────────
            if parsed["invoice_ok"] and self.auto_inv_var.get():
                fields = parsed["fields"]
                inv = {
                    "id":      cfg_module.next_inv_id(),
                    "name":    fields.get("name", sender),
                    "email":   fields.get("email", sender),
                    "phone":   fields.get("phone", ""),
                    "event":   fields.get("event", ""),
                    "date":    fields.get("date", "TBD"),
                    "guests":  fields.get("guests", ""),
                    "amount":  "",
                    "notes":   fields.get("notes", ""),
                    "created": datetime.now().strftime("%Y-%m-%d"),
                    "source":  "script",
                }
                self.state["invoices"].setdefault("Draft", []).append(inv)
                self.log_activity("🧾", f"Invoice drafted — {inv['id']}", inv["name"])
                self._send_draft_alert(inv)

            self._refresh_ui()
            self.save()
            self.set_status("Idle")

        except Exception as ex:
            self.log_activity("⚠", "AI error", str(ex))
            self.set_status(f"Error: {str(ex)[:40]}", "error")

    # ── Owner alerts ──────────────────────────────────────────────────────────

    def _send_handoff_alert(self, conv: dict, reason: str):
        try:
            recent = "\n".join(
                f"  [{m['from'].upper()}]: {m['text'][:120]}"
                for m in conv["messages"][-4:]
            )
            self.email_bot.send_owner_alert(
                f"[Hombre] ⚠ Needs Owner — {conv.get('name', conv.get('email', ''))}",
                f"A conversation needs your attention.\n\n"
                f"Customer: {conv.get('name', '')} ({conv.get('email', '')})\n"
                f"Source: {conv.get('source', '')}\n"
                f"Reason: {reason}\n\n"
                f"Recent messages:\n{recent}\n\n"
                f"Log in to the dashboard to review and take over this thread."
            )
        except Exception:
            pass

    def _send_draft_alert(self, inv: dict):
        try:
            self.email_bot.send_owner_alert(
                f"[Hombre] 📋 New Draft Invoice — {inv['id']} for {inv.get('name','')}",
                f"The AI drafted a new invoice ready for your review.\n\n"
                f"Invoice: {inv['id']}\n"
                f"Customer: {inv.get('name','')}\n"
                f"Email: {inv.get('email','')}\n"
                f"Event: {inv.get('event','')}\n"
                f"Date: {inv.get('date','')}\n"
                f"Guests: {inv.get('guests','')}\n\n"
                f"Open the Invoices tab to set the amount and approve.\n"
                f"Or reply to this email with exactly 'Approved' to approve and send via Square."
            )
        except Exception:
            pass

    # ── Owner email approval polling ──────────────────────────────────────────

    def _poll_owner_approvals(self):
        """Check every 2 minutes if owner replied 'Approved' to a draft alert."""
        def check():
            try:
                approved_subjects = self.email_bot.check_owner_approvals()
                for subj in approved_subjects:
                    # Match subject to a draft invoice by ID
                    for inv in list(self.state["invoices"].get("Draft", [])):
                        if inv.get("id", "") in subj:
                            self.root.after(0, lambda i=inv: self.invoice_tab._approve(i))
                            break
            except Exception:
                pass
            self.root.after(120_000, check)

        self.root.after(120_000, check)

    # ── UI refresh ───────────────────────────────────────────────────────────

    def _refresh_ui(self):
        self.messaging_tab.refresh()
        self.dashboard_tab.refresh()
        self.invoice_tab.render()
        self.metrics_tab.render()

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        self.email_bot.stop()
        self.meta_bot.stop()
        self.save()
        self.root.destroy()
