"""
ui/invoices.py — Invoices tab.
- Edit popup with scroll and full notes field visible
- Invoice rows show customer name primary, order number secondary
- Square customer names used when available
- Draft → Approve → Square sends officially
- Auto-populates calendar on approval
"""

import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from theme import C, FONT
from ui.widgets import btn, ScrollFrame

try:
    import requests
except ImportError:
    requests = None


STAGES = ["Draft", "Waiting for Approval", "Sent", "Deposit Received", "Paid", "Overdue"]
STAGE_COLORS = {
    "Draft":               "muted",
    "Waiting for Approval":"warn",
    "Sent":                "info",
    "Deposit Received":    "gold",
    "Paid":                "success",
    "Overdue":             "error",
}


class InvoicePopup(tk.Toplevel):
    def __init__(self, parent, inv, on_save):
        super().__init__(parent)
        self.title(f"Edit Invoice — {inv.get('id','')}")
        self.configure(bg=C["bg"])
        self.geometry("520x580")
        self.resizable(False, True)
        self.grab_set()
        self.inv     = inv
        self.on_save = on_save
        self.vars    = {}

        # Header
        tk.Label(self, text=f"Edit Invoice  {inv.get('id','')}", bg=C["bg"],
                 fg=C["text"], font=FONT["h3"]).pack(padx=20, pady=(16, 6), anchor="w")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        # Scrollable form area
        sf = ScrollFrame(self, bg=C["bg"])
        sf.pack(fill="both", expand=True)
        form = sf.inner

        fields = [
            ("Customer Name", "name",   False),
            ("Email",         "email",  False),
            ("Phone",         "phone",  False),
            ("Event Type",    "event",  False),
            ("Event Date",    "date",   False),
            ("Guest Count",   "guests", False),
            ("Amount ($)",    "amount", False),
        ]
        for label, key, _ in fields:
            tk.Label(form, text=label, bg=C["bg"], fg=C["muted"],
                     font=FONT["label"]).pack(anchor="w", padx=20, pady=(8, 1))
            var = tk.StringVar(value=inv.get(key, ""))
            self.vars[key] = var
            f = tk.Frame(form, bg=C["input_border"], padx=1, pady=1)
            f.pack(fill="x", padx=20)
            tk.Entry(f, textvariable=var, bg=C["input_bg"], fg=C["text"],
                     insertbackground=C["text"], relief="flat",
                     font=FONT["body"]).pack(fill="x", ipady=7)

        # Notes — Text widget so it can expand
        tk.Label(form, text="Notes", bg=C["bg"], fg=C["muted"],
                 font=FONT["label"]).pack(anchor="w", padx=20, pady=(8, 1))
        notes_frame = tk.Frame(form, bg=C["input_border"], padx=1, pady=1)
        notes_frame.pack(fill="x", padx=20, pady=(0, 16))
        self.notes_text = tk.Text(notes_frame, bg=C["input_bg"], fg=C["text"],
                                  insertbackground=C["text"], relief="flat",
                                  font=FONT["body"], height=5, wrap="word")
        self.notes_text.pack(fill="x")
        self.notes_text.insert("1.0", inv.get("notes", ""))

        # Buttons — fixed at bottom
        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(fill="x", padx=20, pady=12, side="bottom")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", side="bottom")
        btn(btn_row, "Save", bg="success", command=self._save).pack(side="left", padx=(0, 10))
        btn(btn_row, "Cancel", bg="border", fg="text", command=self.destroy).pack(side="left")

    def _save(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        data["notes"] = self.notes_text.get("1.0", "end").strip()
        self.on_save(data)
        self.destroy()


class InvoicesTab:
    def __init__(self, app):
        self.app = app

    def build(self, parent: tk.Frame):
        self._parent = parent

        top = tk.Frame(parent, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=14)
        tk.Label(top, text="Invoices", bg=C["bg"], fg=C["text"],
                 font=FONT["h2"]).pack(side="left")
        btn(top, "+ New Invoice", bg="accent",
            command=self._new_invoice).pack(side="right")

        sf = ScrollFrame(parent)
        sf.pack(fill="both", expand=True)
        self._inner = sf.inner
        self.render()

    def render(self):
        for w in self._inner.winfo_children():
            w.destroy()
        invs    = self.app.state.get("invoices", {})
        has_any = any(invs.get(s) for s in STAGES)

        if not has_any:
            empty = tk.Frame(self._inner, bg=C["bg"])
            empty.pack(expand=True, pady=60)
            tk.Label(empty, text="📋", bg=C["bg"], font=("Helvetica", 36)).pack()
            tk.Label(empty, text="No invoices yet",
                     bg=C["bg"], fg=C["text"], font=FONT["h3"]).pack(pady=(8, 4))
            tk.Label(empty,
                     text="Click  + New Invoice  to create one manually,\n"
                          "or sync Square / let the AI draft one from a conversation.",
                     bg=C["bg"], fg=C["muted"], font=FONT["body"],
                     justify="center").pack()
            return

        for stage in STAGES:
            lst = invs.get(stage, [])
            if not lst:
                continue
            col = STAGE_COLORS.get(stage, "muted")
            hdr = tk.Frame(self._inner, bg=C["bg"])
            hdr.pack(fill="x", padx=20, pady=(14, 4))
            dot = tk.Frame(hdr, bg=C.get(col, C["muted"]), width=10, height=10)
            dot.pack(side="left", padx=(0, 8))
            dot.pack_propagate(False)
            tk.Label(hdr, text=f"{stage.upper()}  ({len(lst)})",
                     bg=C["bg"], fg=C["muted"], font=FONT["label"]).pack(side="left")
            for inv in lst:
                self._inv_row(inv, stage)

    def _inv_row(self, inv, stage):
        col = STAGE_COLORS.get(stage, "muted")
        row = tk.Frame(self._inner, bg=C["panel"],
                       highlightbackground=C["border"], highlightthickness=1)
        row.pack(fill="x", padx=20, pady=3)
        inner = tk.Frame(row, bg=C["panel"], padx=16, pady=10)
        inner.pack(fill="x")

        # Left: customer name primary, order number secondary
        left = tk.Frame(inner, bg=C["panel"])
        left.pack(side="left", fill="x", expand=True)

        name_row = tk.Frame(left, bg=C["panel"])
        name_row.pack(fill="x")

        # Primary: customer name (prefer sq customer name, fallback to inv name)
        display_name = inv.get("sq_customer_name") or inv.get("name") or "Unknown"
        tk.Label(name_row, text=display_name, bg=C["panel"],
                 fg=C["text"], font=FONT["h3"]).pack(side="left")

        if inv.get("source") == "script":
            tk.Label(name_row, text=" 🤖", bg=C["panel"],
                     fg=C["info"], font=FONT["tiny"]).pack(side="left", padx=2)
        if inv.get("sq_order_id"):
            tk.Label(name_row, text=" ■ Square", bg=C["panel"],
                     fg=C["gold"], font=FONT["tiny"]).pack(side="left", padx=4)

        # Secondary: order number + event + date
        inv_id = inv.get("id", "")
        sq_id  = inv.get("sq_order_id", "")
        id_str = f"{inv_id}"
        if sq_id:
            id_str += f"  ·  #{sq_id[:12]}"
        detail = f"{id_str}  ·  {inv.get('event','')}  ·  {inv.get('date','')}"
        tk.Label(left, text=detail, bg=C["panel"],
                 fg=C["muted"], font=FONT["tiny"]).pack(anchor="w")

        # Right: amount + actions
        right = tk.Frame(inner, bg=C["panel"])
        right.pack(side="right")
        tk.Label(right, text=inv.get("amount", "—"),
                 bg=C["panel"], fg=C.get(col, C["text"]),
                 font=FONT["h3"]).pack(anchor="e")

        action_row = tk.Frame(right, bg=C["panel"])
        action_row.pack(anchor="e", pady=(4, 0))
        btn(action_row, "Edit", bg="border", fg="text", px=8, py=4,
            command=lambda i=inv: self._edit(i)).pack(side="left", padx=2)

        if stage in ("Draft", "Waiting for Approval"):
            btn(action_row, "✓ Approve & Send via Square", bg="accent", px=8, py=4,
                command=lambda i=inv: self._approve(i)).pack(side="left", padx=2)

        for next_stage in STAGES:
            if next_stage == stage:
                continue
            btn(action_row, f"→ {next_stage}", bg="border", fg="muted", px=6, py=4,
                command=lambda i=inv, s=stage, ns=next_stage: self._move(i, s, ns)
                ).pack(side="left", padx=1)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _new_invoice(self):
        from config import next_inv_id
        inv = {"id": next_inv_id(), "name": "", "email": "", "phone": "",
               "event": "", "date": "", "guests": "", "amount": "", "notes": "",
               "created": datetime.now().strftime("%Y-%m-%d"), "source": "manual"}
        def save(data):
            inv.update(data)
            self.app.state["invoices"]["Draft"].append(inv)
            self.app.save()
            self.render()
        InvoicePopup(self._parent.winfo_toplevel(), inv, save)

    def _edit(self, inv):
        def save(data):
            inv.update(data)
            self.app.save()
            self.render()
        InvoicePopup(self._parent.winfo_toplevel(), inv, save)

    def _approve(self, inv):
        amt_str = inv.get("amount", "0").replace("$", "").replace(",", "")
        try:
            amt_cents = int(float(amt_str) * 100)
        except Exception:
            amt_cents = 0

        if not messagebox.askyesno(
            "Approve Invoice",
            f"Send Square invoice to {inv.get('email','?')} for {inv.get('amount','$0')}?\n"
            "This will send an official Square payment request."
        ):
            return

        sent = self._send_via_square(inv, amt_cents)
        stage = self._find_stage(inv)

        if sent:
            self._move(inv, stage, "Sent")
            if inv.get("source") == "script":
                self.app.state["ai_invoices_approved"] = (
                    self.app.state.get("ai_invoices_approved", 0) + 1)
            self.app.log_activity("📤", f"Invoice sent via Square — {inv['id']}", inv.get("name",""))

            # Auto-populate calendar
            self._add_to_calendar(inv)

            try:
                self.app.email_bot.send_owner_alert(
                    f"[Hombre] Invoice {inv['id']} sent to {inv.get('name','')}",
                    f"Invoice {inv['id']} was approved and sent via Square.\n\n"
                    f"Customer: {inv.get('name','')}\nEmail: {inv.get('email','')}\n"
                    f"Amount: {inv.get('amount','')}\nEvent: {inv.get('event','')}\n"
                    f"Date: {inv.get('date','')}"
                )
            except Exception:
                pass
        else:
            messagebox.showerror("Square Error",
                                 "Could not send via Square. Check credentials in Settings.")

    def _add_to_calendar(self, inv):
        """Create a calendar event when invoice is approved."""
        title    = inv.get("name") or inv.get("sq_customer_name") or "Event"
        event    = inv.get("event", "")
        date_str = inv.get("date", "")
        guests   = inv.get("guests", "")

        # Try to parse display date into YYYY-MM-DD
        cal_date = ""
        for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%m/%d/%Y"):
            try:
                cal_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                break
            except Exception:
                pass
        if not cal_date:
            cal_date = datetime.now().strftime("%Y-%m-%d")

        cal_event = {
            "title":    f"{title} — {event}" if event else title,
            "date":     cal_date,
            "guests":   guests,
            "amount":   inv.get("amount", ""),
            "inv_id":   inv.get("id", ""),
            "staff":    "",
            "notes":    inv.get("notes", ""),
            "source":   "invoice",
        }
        self.app.state.setdefault("calendar_events", []).append(cal_event)
        self.app.save()
        if hasattr(self.app, "calendar_tab"):
            self.app.calendar_tab.refresh()

    def _send_via_square(self, inv: dict, amt_cents: int) -> bool:
        s     = self.app.secrets
        token = s.get("sq_access_token", "")
        env   = s.get("sq_environment", "production")
        if not token or not requests:
            return False
        base = ("https://connect.squareup.com" if env == "production"
                else "https://connect.squareupsandbox.com")
        hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                "Square-Version": "2024-01-18"}
        import uuid
        customer_id = self._sq_find_or_create_customer(base, hdrs, inv)
        if not customer_id:
            return False
        loc_r = requests.get(f"{base}/v2/locations", headers=hdrs, timeout=10)
        locs  = loc_r.json().get("locations", [])
        if not locs:
            return False
        loc_id = locs[0]["id"]
        order_body = {
            "idempotency_key": str(uuid.uuid4()),
            "order": {
                "location_id": loc_id,
                "customer_id": customer_id,
                "line_items": [{
                    "name":     inv.get("event", "Catering Services"),
                    "quantity": "1",
                    "base_price_money": {"amount": amt_cents, "currency": "USD"},
                }],
            }
        }
        order_r  = requests.post(f"{base}/v2/orders", headers=hdrs,
                                 json=order_body, timeout=12)
        order_id = order_r.json().get("order", {}).get("id", "")
        if not order_id:
            return False
        inv_body = {
            "idempotency_key": str(uuid.uuid4()),
            "invoice": {
                "order_id":    order_id,
                "location_id": loc_id,
                "primary_recipient": {"customer_id": customer_id},
                "payment_requests": [{
                    "request_type": "BALANCE",
                    "due_date":     inv.get("date", "")[:10] or "2099-12-31",
                    "automatic_payment_source": "NONE",
                }],
                "delivery_method": "EMAIL",
                "invoice_number":  inv.get("id", ""),
                "description":     inv.get("notes", ""),
            }
        }
        cr       = requests.post(f"{base}/v2/invoices", headers=hdrs,
                                 json=inv_body, timeout=12)
        sq_inv_id = cr.json().get("invoice", {}).get("id", "")
        if not sq_inv_id:
            return False
        ver = cr.json().get("invoice", {}).get("version", 0)
        requests.post(f"{base}/v2/invoices/{sq_inv_id}/publish",
                      headers=hdrs,
                      json={"idempotency_key": str(uuid.uuid4()), "version": ver},
                      timeout=12)
        inv["sq_invoice_id"] = sq_inv_id
        return True

    def _sq_find_or_create_customer(self, base, hdrs, inv) -> str:
        email = inv.get("email", "")
        if not email:
            return ""
        import uuid
        sr = requests.post(f"{base}/v2/customers/search", headers=hdrs,
                           json={"query": {"filter": {"email_address":
                                 {"exact": email}}}}, timeout=10)
        results = sr.json().get("customers", [])
        if results:
            c = results[0]
            # Store Square's display name on the invoice
            sq_name = f"{c.get('given_name','')} {c.get('family_name','')}".strip()
            if sq_name:
                inv["sq_customer_name"] = sq_name
            return c["id"]
        cr = requests.post(f"{base}/v2/customers", headers=hdrs,
                           json={"idempotency_key": str(uuid.uuid4()),
                                 "given_name":    inv.get("name", "").split()[0] if inv.get("name") else "",
                                 "family_name":   " ".join(inv.get("name", "").split()[1:]),
                                 "email_address": email,
                                 "phone_number":  inv.get("phone", "")},
                           timeout=10)
        return cr.json().get("customer", {}).get("id", "")

    def _move(self, inv, from_stage, to_stage):
        lst = self.app.state["invoices"].get(from_stage, [])
        if inv in lst:
            lst.remove(inv)
        self.app.state["invoices"].setdefault(to_stage, []).append(inv)
        if to_stage == "Paid" and inv.get("source") == "script":
            self.app.state["ai_invoices_paid"] = (
                self.app.state.get("ai_invoices_paid", 0) + 1)
            self.app.update_customer_from_invoice(inv)
        self.app.log_activity("📋", f"Invoice {inv['id']} → {to_stage}", inv.get("name", ""))
        self.app.save()
        self.render()
        self.app.dashboard_tab.refresh()
        self.app.metrics_tab.render()

    def _find_stage(self, inv) -> str:
        for stage, lst in self.app.state["invoices"].items():
            if inv in lst:
                return stage
        return "Draft"
