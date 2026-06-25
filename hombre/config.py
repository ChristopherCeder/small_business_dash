"""
config.py — Load/save secrets, app settings, and persistent state.
All API keys and passwords live in secrets.json only.
"""

import json, os
from datetime import datetime

BASE_DIR     = os.path.dirname(__file__)
SECRETS_FILE = os.path.join(BASE_DIR, "secrets.json")
SETTINGS_FILE= os.path.join(BASE_DIR, "settings.json")
STATE_FILE   = os.path.join(BASE_DIR, "state.json")
INV_FILE     = os.path.join(BASE_DIR, "inv_counter.json")

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_SECRETS = {
    "email": "", "app_password": "", "forward_to": "", "claude_api_key": "",
    "fb_page_id": "", "fb_page_token": "", "fb_app_secret": "",
    "fb_verify_token": "", "ig_user_id": "",
    "sq_app_id": "", "sq_access_token": "", "sq_environment": "production",
    "sq_webhook_secret": "", "admin_pin": "1234",
}

DEFAULT_SETTINGS = {
    "subject_filter": "New contact form message for El Hombre Taco",
    "interval":       "60",
    "email_bot_on":   False,
    "ig_bot_on":      False,
    "fb_bot_on":      False,
    "global_ai_on":   True,
    "auto_invoice":   True,

    # Granular AI prompt sections
    "ai_sales_style": (
        "Be warm, genuine, and subtly persuasive — like a real person who loves tacos and cares "
        "about making the customer's event perfect. Match the laid-back but professional vibe of "
        "a beloved local Texas taco spot. Use first names. Show genuine excitement. "
        "Ask one proactive follow-up question per reply to keep the conversation moving toward a booking. "
        "For email form submissions, always ask: 'Is [phone number if provided] the best number for "
        "our team to reach you?' If no phone given, ask for the best callback number. "
        "Keep replies 3-5 sentences. Sign off as 'The El Hombre Taco Team'."
    ),
    "ai_business_facts": (
        "El Hombre Taco is a professional taco catering company based in Georgetown, TX. "
        "We specialize in Tex-Mex 'Texafied Tacos' for weddings, corporate events, birthdays, "
        "quinceañeras, and more. Website: elhombretaco.com. "
        "Service area: Greater Austin / Georgetown TX region. "
        "Packages start at approximately $12-18 per person depending on menu and headcount. "
        "A deposit is required to hold a date. Final payment is due before the event. "
        "Minimum guest count: 25 people. We provide all equipment, staff, and setup."
    ),
    "ai_handoff_rules": (
        "STOP replying automatically and flag as 'needs_owner' if ANY of these apply:\n"
        "- Customer asks for pricing outside standard packages or requests a custom quote.\n"
        "- Customer mentions a date conflict or reschedule.\n"
        "- Customer expresses frustration, dissatisfaction, or complains about a past event.\n"
        "- Customer asks to speak to a human, manager, or owner directly.\n"
        "- You are unsure how to answer a specific question accurately.\n"
        "- The conversation has gone 5+ rounds without a booking commitment.\n"
        "When flagging, output exactly: HANDOFF:YES and a one-line REASON: on the next line."
    ),
}

DEFAULT_STATE = {
    "conversations":   [],
    "messages":        [],      # master inbox — all inbound messages
    "invoices": {
        "Draft":               [],
        "Waiting for Approval":[],
        "Sent":                [],
        "Deposit Received":    [],
        "Paid":                [],
        "Overdue":             [],
    },
    "customers":        [],
    "calendar_events":  [],
    "activity_log":     [],
}

# ── Loaders ───────────────────────────────────────────────────────────────────

def load_secrets() -> dict:
    d = dict(DEFAULT_SECRETS)
    if os.path.exists(SECRETS_FILE):
        try:
            with open(SECRETS_FILE) as f:
                d.update(json.load(f))
        except Exception:
            pass
    return d

def save_secrets(data: dict):
    existing = load_secrets()
    existing.update(data)
    with open(SECRETS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

def load_settings() -> dict:
    d = dict(DEFAULT_SETTINGS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                d.update(json.load(f))
        except Exception:
            pass
    return d

def save_settings(data: dict):
    existing = load_settings()
    existing.update(data)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(existing, f, indent=2)

def load_state() -> dict:
    d = dict(DEFAULT_STATE)
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                saved = json.load(f)
            # Merge top-level keys; keep default invoice stages if missing
            for k, v in saved.items():
                if k == "invoices":
                    for stage, lst in DEFAULT_STATE["invoices"].items():
                        d["invoices"].setdefault(stage, lst)
                    d["invoices"].update(v)
                else:
                    d[k] = v
        except Exception:
            pass
    return d

def save_state(data: dict):
    # activity_log: keep only last 100
    if "activity_log" in data:
        data["activity_log"] = data["activity_log"][:100]
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Invoice ID counter ─────────────────────────────────────────────────────────

def next_inv_id() -> str:
    n = 1
    if os.path.exists(INV_FILE):
        try:
            with open(INV_FILE) as f:
                n = json.load(f).get("n", 1)
        except Exception:
            pass
    with open(INV_FILE, "w") as f:
        json.dump({"n": n + 1}, f)
    return f"INV-{n:03d}"

# ── Merged cfg convenience (secrets + settings in one dict) ───────────────────

def load_cfg() -> dict:
    """Return a merged dict of secrets + settings for legacy compatibility."""
    cfg = {}
    cfg.update(load_settings())
    cfg.update(load_secrets())
    return cfg
