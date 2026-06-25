"""
ui/dashboard.py — Dashboard tab.
KPI cards, script conversion rate, invoice pipeline sidebar, Square sync.
"""

import threading
from datetime import datetime, timedelta
import tkinter as tk

from theme import C, FONT
from ui.widgets import btn, div, card, ScrollFrame

try:
    import requests
except ImportError:
    requests = None


class DashboardTab:
    def __init__(self, app):
        self.app = app
        self.dash_cards   = {}
        self.dash_conv_lbl= None
        self.dash_conv_sub= None
        self.dash_inv_frame = None

    def build(self, parent: tk.Frame):
        # ── Square sync bar ──────────────────────────────────────────────────
        sync_bar = tk.Frame(parent, bg=C["panel"], height=44)
        sync_bar.pack(fill="x")
        sync_bar.pack_propagate(False)
        tk.Frame(sync_bar, bg=C["border"], height=1).pack(fill="x", side="bottom")
        self.sq_status = tk.Label(sync_bar, text="", bg=C["panel"],
                                  fg=C["muted"], font=FONT["tiny"])
        self.sq_status.pack(side="right", padx=16)
        btn(sync_bar, "⟳  Sync Square", bg="accent", command=self._sync_square,
            px=14, py=5).pack(side="right", padx=4, pady=8)

        sf = ScrollFrame(parent)
        sf.pack(fill="both", expand=True)
        inner = sf.inner

        # ── KPI row ──────────────────────────────────────────────────────────
        kpi_row = tk.Frame(inner, bg=C["bg"])
        kpi_row.pack(fill="x", padx=20, pady=(20, 8))

        for title, val, sub, col, key in [
            ("REVENUE — 30 DAYS",       "$0.00", "Paid invoices (rolling 30d)", "gold",    "rev30"),
            ("INVOICES PAID — 30 DAYS", "0",     "Completed",                  "success",  "paid30"),
            ("LEADS",                   "0",     "AI replies sent",             "info",     "leads30"),
            ("PENDING INVOICES",        "0",     "Awaiting approval",           "warn",     "pending"),
        ]:
            f, v = card(kpi_row, title, val, sub, value_color=col)
            f.pack(side="left", fill="x", expand=True, padx=(0, 8))
            self.dash_cards[key] = v

        # ── Script Conversion Rate card ───────────────────────────────────────
        conv_row = tk.Frame(inner, bg=C["bg"])
        conv_row.pack(fill="x", padx=20, pady=(0, 12))

        cf = tk.Frame(conv_row, bg=C["card2"],
                      highlightbackground=C["accent"], highlightthickness=2,
                      padx=20, pady=14)
        cf.pack(fill="x")
        header_row = tk.Frame(cf, bg=C["card2"]); header_row.pack(fill="x")
        tk.Label(header_row, text="🤖  SCRIPT CONVERSION RATE", bg=C["card2"],
                 fg=C["accent"], font=FONT["label"]).pack(side="left")
        self.dash_conv_lbl = tk.Label(header_row, text="0.0%", bg=C["card2"],
                                       fg=C["muted"], font=FONT["h1"])
        self.dash_conv_lbl.pack(side="right")
        self.dash_conv_sub = tk.Label(cf, text="0 AI replies · 0 script-closed paid",
                                       bg=C["card2"], fg=C["dim"], font=FONT["tiny"])
        self.dash_conv_sub.pack(anchor="w", pady=(4, 0))

        # ── Bottom row: latest conversation + pipeline ────────────────────────
        bottom = tk.Frame(inner, bg=C["bg"])
        bottom.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Latest conversation preview
        left = tk.Frame(bottom, bg=C["panel"],
                        highlightbackground=C["border"], highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        tk.Label(left, text="LATEST CONVERSATION", bg=C["panel"],
                 fg=C["muted"], font=FONT["label"], padx=16, pady=10).pack(anchor="w")
        tk.Frame(left, bg=C["border"], height=1).pack(fill="x")
        self.dash_chat_frame = tk.Frame(left, bg=C["panel"])
        self.dash_chat_frame.pack(fill="both", expand=True, padx=14, pady=10)
        tk.Label(self.dash_chat_frame, text="No conversations yet.",
                 bg=C["panel"], fg=C["dim"], font=FONT["body"]).pack(pady=20)
        btn(left, "Open Messaging →", bg="accent",
            command=lambda: self.app.switch_tab("Messaging")).pack(
            fill="x", side="bottom", padx=0, pady=0)

        # Invoice pipeline sidebar
        right = tk.Frame(bottom, bg=C["panel"], width=220,
                         highlightbackground=C["border"], highlightthickness=1)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="INVOICES — 30 DAYS", bg=C["panel"],
                 fg=C["muted"], font=FONT["label"], padx=16, pady=10).pack(anchor="w")
        tk.Frame(right, bg=C["border"], height=1).pack(fill="x")
        self.dash_inv_frame = tk.Frame(right, bg=C["panel"])
        self.dash_inv_frame.pack(fill="x")
        btn(right, "View Invoices →", bg="accent",
            command=lambda: self.app.switch_tab("Invoices")).pack(
            fill="x", side="bottom")

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self, sq_rev=None, sq_paid=None):
        app = self.app
        cutoff  = datetime.now() - timedelta(days=30)

        def _paid_in_30():
            return [i for i in app.state["invoices"].get("Paid", [])
                    if self._in_30(i, cutoff)]

        rev30   = sq_rev  if sq_rev  is not None else sum(
            self._parse_amt(i) for i in _paid_in_30())
        paid30  = sq_paid if sq_paid is not None else len(_paid_in_30())
        leads30 = app.state.get("ai_reply_count", 0)
        pending = len(app.state["invoices"].get("Waiting for Approval", []))

        if "rev30"   in self.dash_cards: self.dash_cards["rev30"].config(text=f"${rev30:,.2f}")
        if "paid30"  in self.dash_cards: self.dash_cards["paid30"].config(text=str(paid30))
        if "leads30" in self.dash_cards: self.dash_cards["leads30"].config(text=str(leads30))
        if "pending" in self.dash_cards: self.dash_cards["pending"].config(text=str(pending))

        # Conversion rate
        approved_total = app.state.get("ai_invoices_approved", 0)
        approved_paid  = app.state.get("ai_invoices_paid", 0)
        conv_pct = round((approved_paid / approved_total * 100), 1) if approved_total else 0.0
        conv_col = C["success"] if conv_pct >= 20 else C["warn"] if conv_pct >= 8 else C["error"]
        if self.dash_conv_lbl:
            self.dash_conv_lbl.config(text=f"{conv_pct}%", fg=conv_col)
            self.dash_conv_sub.config(
                text=f"{leads30} AI replies · {approved_paid} approved-then-paid / {approved_total} approved")

        # Pipeline sidebar
        if self.dash_inv_frame:
            for w in self.dash_inv_frame.winfo_children():
                w.destroy()
            for label, stage, col in [
                ("Waiting",  "Waiting for Approval", "warn"),
                ("Sent",     "Sent",                 "muted"),
                ("Deposit",  "Deposit Received",      "gold"),
                ("Paid",     "Paid",                  "success"),
                ("Overdue",  "Overdue",               "error"),
            ]:
                cnt = len([i for i in app.state["invoices"].get(stage, [])
                           if self._in_30(i, cutoff)])
                r = tk.Frame(self.dash_inv_frame, bg=C["panel"])
                r.pack(fill="x", padx=16, pady=5)
                tk.Label(r, text=label, bg=C["panel"], fg=C["muted"],
                         font=FONT["body"]).pack(side="left")
                tk.Label(r, text=str(cnt), bg=C["panel"], fg=C.get(col, C["text"]),
                         font=FONT["h3"]).pack(side="right")

    # ── Square Sync ───────────────────────────────────────────────────────────

    def _sync_square(self):
        self.sq_status.config(text="Syncing…", fg=C["gold"])

        def task():
            try:
                s     = self.app.secrets
                token = s.get("sq_access_token", "")
                env   = s.get("sq_environment", "production") or "production"
                if not requests:
                    self._sq_err("requests not installed (pip install requests)"); return
                if not token:
                    self._sq_err("No Square token in Settings → Credentials"); return

                base  = ("https://connect.squareup.com" if env == "production"
                         else "https://connect.squareupsandbox.com")
                since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                hdrs  = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

                loc_r   = requests.get(f"{base}/v2/locations", headers=hdrs, timeout=10)
                loc_ids = [l["id"] for l in loc_r.json().get("locations", [])]
                body    = {"query": {"filter": {"date_time_filter": {
                    "created_at": {"start_at": since}}}}, "location_ids": loc_ids}
                r       = requests.post(f"{base}/v2/orders/search", headers=hdrs,
                                        json=body, timeout=12)
                orders    = r.json().get("orders", [])
                completed = [o for o in orders if o.get("state") == "COMPLETED"]
                rev30     = sum(o.get("total_money", {}).get("amount", 0) / 100 for o in completed)
                paid30    = len(completed)
                ts        = datetime.now().strftime("%I:%M %p")

                self.app.root.after(0, lambda: self._apply_sq(completed, rev30, paid30, ts))

            except Exception as ex:
                self.app.root.after(0, lambda: self._sq_err(str(ex)[:60]))

        threading.Thread(target=task, daemon=True).start()

    def _apply_sq(self, completed, rev30, paid30, ts):
        from config import next_inv_id
        existing_ids = {i.get("sq_order_id")
                        for i in self.app.state["invoices"].get("Paid", [])
                        if i.get("sq_order_id")}
        for o in completed:
            oid = o.get("id", "")
            if oid in existing_ids:
                continue
            amt      = o.get("total_money", {}).get("amount", 0) / 100
            raw_date = o.get("created_at", "")
            try:
                created      = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
                display_date = datetime.strptime(raw_date[:10], "%Y-%m-%d").strftime("%b %d, %Y")
            except Exception:
                created      = datetime.now().strftime("%Y-%m-%d")
                display_date = "Unknown"
            name = ""
            for f in o.get("fulfillments", []):
                name = (f.get("shipment_details", {}).get("recipient", {}).get("display_name", "")
                        or f.get("pickup_details", {}).get("recipient", {}).get("display_name", ""))
                if name:
                    break
            if not name:
                name = f"Square Order {oid[:8]}"
            self.app.state["invoices"]["Paid"].append({
                "id": next_inv_id(), "sq_order_id": oid,
                "name": name, "email": "", "phone": "",
                "event": "Square Sale", "date": display_date,
                "amount": f"${amt:,.2f}",
                "notes": f"Imported from Square on {ts}",
                "created": created,
            })
        self.sq_status.config(
            text=f"Square: ${rev30:,.2f} · {paid30} paid · synced {ts}", fg=C["success"])
        self.app.log_activity("🟦", "Square synced",
                              f"${rev30:,.2f} revenue · {paid30} orders (30d)")
        self.app.save()
        self.app.invoice_tab.render()
        self.refresh(sq_rev=rev30, sq_paid=paid30)
        self.app.metrics_tab.render()

    def _sq_err(self, msg):
        self.sq_status.config(text=f"✗ {msg}", fg=C["error"])

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _in_30(inv, cutoff):
        try:
            return datetime.strptime(inv.get("created", ""), "%Y-%m-%d") >= cutoff
        except Exception:
            return True

    @staticmethod
    def _parse_amt(inv):
        try:
            return float(inv.get("amount", "0").replace("$", "").replace(",", ""))
        except Exception:
            return 0.0
