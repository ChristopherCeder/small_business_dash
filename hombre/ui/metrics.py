"""
ui/metrics.py — Metrics tab.
- Revenue by AI Script (not all-time)
- Events 30d with weekly avg
- 12-month chart with revenue + inquiry counts
- Stage breakdown, conversion rate, activity feed
"""

import tkinter as tk
from datetime import datetime, timedelta
from theme import C, FONT
from ui.widgets import ScrollFrame


class MetricsTab:
    def __init__(self, app):
        self.app    = app
        self._inner = None

    def build(self, parent: tk.Frame):
        tk.Label(parent, text="Financial Overview", bg=C["bg"],
                 fg=C["text"], font=FONT["h2"]).pack(anchor="w", padx=20, pady=(16, 6))
        sf = ScrollFrame(parent)
        sf.pack(fill="both", expand=True)
        self._inner = sf.inner
        self.render()

    def render(self):
        if not self._inner:
            return
        for w in self._inner.winfo_children():
            w.destroy()
        self._draw()

    def _draw(self):
        inner  = self._inner
        cutoff = datetime.now() - timedelta(days=30)
        paid_all = self.app.state["invoices"].get("Paid", [])
        paid_30  = [i for i in paid_all if self._in_date(i, cutoff)]

        def amt(inv):
            return self._parse_amt(inv)

        rev_30   = sum(amt(i) for i in paid_30)
        # Revenue by AI Script — lifetime paid invoices drafted by AI
        rev_ai   = sum(amt(i) for i in paid_all
                       if i.get("source") == "script" and not i.get("sq_order_id"))

        events_30 = len(paid_30)
        weekly_avg = round(events_30 / 4, 1)

        leads      = self.app.state.get("ai_reply_count", 0)
        ap_total   = self.app.state.get("ai_invoices_approved", 0)
        ap_paid    = self.app.state.get("ai_invoices_paid", 0)
        conv_pct   = round(ap_paid / ap_total * 100, 1) if ap_total else 0.0
        pending    = len(self.app.state["invoices"].get("Waiting for Approval", []))
        overdue    = len(self.app.state["invoices"].get("Overdue", []))

        # ── KPI cards ──
        krow = tk.Frame(inner, bg=C["bg"])
        krow.pack(fill="x", padx=20, pady=(4, 10))

        # Revenue — 30 Days
        self._kpi_card(krow, "Revenue — 30 Days", f"${rev_30:,.2f}",
                       "Rolling 30d paid", C["gold"])

        # Revenue by AI Script
        self._kpi_card(krow, "Revenue by AI Script", f"${rev_ai:,.2f}",
                       "Lifetime AI-closed paid", C["accent"])

        # Events — 30 Days with weekly avg
        events_card = tk.Frame(krow, bg=C["panel"],
                               highlightbackground=C["border"], highlightthickness=1,
                               padx=14, pady=12)
        events_card.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(events_card, text="EVENTS — 30 DAYS", bg=C["panel"],
                 fg=C["muted"], font=FONT["label"]).pack(anchor="w")
        tk.Label(events_card, text=str(events_30), bg=C["panel"],
                 fg=C["info"], font=FONT["h2"]).pack(anchor="w")
        tk.Label(events_card, text=f"Weekly avg: {weekly_avg}",
                 bg=C["panel"], fg=C["dim"], font=FONT["tiny"]).pack(anchor="w")

        self._kpi_card(krow, "Pending",  str(pending), "Awaiting action",  C["warn"])
        self._kpi_card(krow, "Overdue",  str(overdue), "Need follow-up",   C["error"])

        # ── AI Conversion Rate ──
        conv_col = C["success"] if conv_pct >= 20 else C["warn"] if conv_pct >= 8 else C["error"]
        cf = tk.Frame(inner, bg=C["card2"],
                      highlightbackground=C["accent"], highlightthickness=2)
        cf.pack(fill="x", padx=20, pady=(0, 12))
        hr = tk.Frame(cf, bg=C["card2"]); hr.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(hr, text="🤖  AI SCRIPT CONVERSION RATE", bg=C["card2"],
                 fg=C["accent"], font=FONT["label"]).pack(side="left")
        tk.Label(hr, text=f"{conv_pct}%", bg=C["card2"], fg=conv_col,
                 font=FONT["h1"]).pack(side="right", padx=8)
        dr = tk.Frame(cf, bg=C["card2"]); dr.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(dr,
                 text=(f"AI replies sent: {leads}   ·   "
                       f"AI invoices approved: {ap_total}   ·   "
                       f"Approved → Paid: {ap_paid}"),
                 bg=C["card2"], fg=C["muted"], font=FONT["tiny"]).pack(side="left")

        # ── Stage breakdown ──
        all_flat = [i for lst in self.app.state["invoices"].values() for i in lst]
        total    = len(all_flat) or 1
        stage_rows = []
        for stage, col in [
            ("Waiting for Approval", C["warn"]),
            ("Sent",                 C["info"]),
            ("Deposit Received",     C["gold"]),
            ("Paid",                 C["success"]),
            ("Overdue",              C["error"]),
        ]:
            invs = self.app.state["invoices"].get(stage, [])
            stage_rows.append((stage, len(invs), total, col,
                               f"${sum(self._parse_amt(i) for i in invs):,.0f}"))
        self._stage_card(inner, "Invoice Stage Breakdown — All", stage_rows)

        # ── 12-month chart: revenue + inquiries ──
        self._monthly_chart(inner, paid_all)

        # ── Recent activity ──
        self._activity_feed(inner)

    # ── 12-month chart ────────────────────────────────────────────────────────

    def _monthly_chart(self, parent, paid_all):
        chart_f = tk.Frame(parent, bg=C["panel"],
                           highlightbackground=C["border"], highlightthickness=1)
        chart_f.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(chart_f, text="Monthly Revenue & Inquiries",
                 bg=C["panel"], fg=C["text"], font=FONT["h3"],
                 padx=14, pady=10).pack(anchor="w")
        tk.Frame(chart_f, bg=C["border"], height=1).pack(fill="x")

        now     = datetime.now()
        cur_key = now.strftime("%Y-%m")

        # Correct month subtraction — no timedelta drift
        def month_key(year, month):
            return f"{year}-{month:02d}"

        def subtract_months(dt, n):
            month = dt.month - n
            year  = dt.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            return datetime(year, month, 1)

        # Next month for forecast
        next_dt  = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        next_key = next_dt.strftime("%Y-%m")

        # Build monthly revenue from paid invoices
        monthly_rev = {}
        for inv in paid_all:
            try:
                d   = datetime.strptime(inv.get("created", ""), "%Y-%m-%d")
                key = d.strftime("%Y-%m")
                monthly_rev[key] = monthly_rev.get(key, 0) + self._parse_amt(inv)
            except Exception:
                pass

        # Build monthly inquiry count from conversations
        monthly_inq = {}
        for conv in self.app.state.get("conversations", []):
            created = conv.get("created", "")
            if not created:
                continue
            try:
                d   = datetime.strptime(created[:10], "%Y-%m-%d")
                key = d.strftime("%Y-%m")
                monthly_inq[key] = monthly_inq.get(key, 0) + 1
            except Exception:
                pass

        # All 12 past months, most recent first, using correct month arithmetic
        past_months = []
        for i in range(12):
            dt  = subtract_months(now, i)
            key = dt.strftime("%Y-%m")
            past_months.append((key, monthly_rev.get(key, 0), monthly_inq.get(key, 0)))

        # Forecast = trailing average of months with revenue (exclude current partial)
        historical = [r for k, r, _ in past_months if k != cur_key and r > 0]
        forecast   = round(sum(historical) / len(historical), 2) if historical else 0.0

        # Display: forecast first, then all 12 months
        display = [(next_key, forecast, 0, "forecast")]
        for key, rev, inq in past_months:
            display.append((key, rev, inq, "current" if key == cur_key else "past"))

        # Scale bars to actual max (ignore $0 months for scale)
        rev_vals = [r for _, r, _, t in display if t != "forecast" and r > 0]
        max_rev  = max(rev_vals + [forecast], default=1) or 1
        inq_vals = [i for _, _, i, t in display if i > 0]
        max_inq  = max(inq_vals, default=1) or 1
        BAR_W    = 180

        # Legend
        leg = tk.Frame(chart_f, bg=C["panel"]); leg.pack(anchor="w", padx=14, pady=(6, 4))
        for col, label in [(C["gold"], "Revenue"), (C["accent"], "Inquiries"), (C["dim"], "Forecast")]:
            tk.Frame(leg, bg=col, width=10, height=8).pack(side="left", padx=(0, 3))
            tk.Label(leg, text=label, bg=C["panel"], fg=C["muted"],
                     font=FONT["tiny"]).pack(side="left", padx=(0, 14))

        for mo_key, rev, inq, tag in display:
            try:
                mo_label = datetime.strptime(mo_key, "%Y-%m").strftime("%b %Y")
            except Exception:
                mo_label = mo_key

            if tag == "forecast":
                fg_col    = C["dim"]
                rev_col   = C["dim"]
                rev_label = f"~${forecast:,.0f}"
                tag_label = "Forecast"
            elif tag == "current":
                fg_col    = C["info"]
                rev_col   = C["info"]
                rev_label = f"${rev:,.0f}"
                tag_label = "In Progress"
            else:
                fg_col    = C["muted"]
                rev_col   = C["gold"]
                rev_label = f"${rev:,.0f}"
                tag_label = ""

            # Row
            outer = tk.Frame(chart_f, bg=C["panel"]); outer.pack(fill="x", padx=14, pady=3)

            # Month label column — fixed 100px, two lines if needed
            lf = tk.Frame(outer, bg=C["panel"], width=100); lf.pack(side="left", anchor="n")
            lf.pack_propagate(False)
            tk.Label(lf, text=mo_label, bg=C["panel"], fg=fg_col,
                     font=FONT["tiny"], anchor="w").pack(fill="x")
            if tag_label:
                tk.Label(lf, text=tag_label, bg=C["panel"], fg=fg_col,
                         font=FONT["tiny"], anchor="w").pack(fill="x")

            # Bars column
            bars = tk.Frame(outer, bg=C["panel"]); bars.pack(side="left", fill="x", expand=True)

            # Revenue bar
            rr = tk.Frame(bars, bg=C["panel"]); rr.pack(fill="x", pady=(1, 0))
            rb = tk.Frame(rr, bg=C["bg"], height=9, width=BAR_W)
            rb.pack(side="left"); rb.pack_propagate(False)
            bar_w = max(2, int((rev / max_rev) * (BAR_W - 2))) if rev > 0 else 2
            tk.Frame(rb, bg=rev_col, width=bar_w, height=9).place(x=0, y=0)
            tk.Label(rr, text=rev_label, bg=C["panel"],
                     fg=rev_col, font=FONT["tiny"]).pack(side="left", padx=6)

            # Inquiries bar (not on forecast row)
            if tag != "forecast":
                ir = tk.Frame(bars, bg=C["panel"]); ir.pack(fill="x", pady=(1, 0))
                ib = tk.Frame(ir, bg=C["bg"], height=9, width=BAR_W)
                ib.pack(side="left"); ib.pack_propagate(False)
                inq_w = max(2, int((inq / max_inq) * (BAR_W - 2))) if inq > 0 else 2
                tk.Frame(ib, bg=C["accent"], width=inq_w, height=9).place(x=0, y=0)
                tk.Label(ir, text=f"{inq} inq.", bg=C["panel"],
                         fg=C["accent"], font=FONT["tiny"]).pack(side="left", padx=6)

            tk.Frame(chart_f, bg=C["border"], height=1).pack(fill="x", padx=14)

    def _stage_card(self, parent, title, rows):
        f = tk.Frame(parent, bg=C["panel"],
                     highlightbackground=C["border"], highlightthickness=1)
        f.pack(fill="x", padx=20, pady=(0, 12))
        tk.Label(f, text=title, bg=C["panel"], fg=C["text"],
                 font=FONT["h3"], padx=14, pady=10).pack(anchor="w")
        tk.Frame(f, bg=C["border"], height=1).pack(fill="x")
        for label, cnt, total, col, rev_str in rows:
            pct = int(cnt / total * 100)
            r   = tk.Frame(f, bg=C["panel"]); r.pack(fill="x", padx=14, pady=6)
            tk.Label(r, text=label, bg=C["panel"], fg=C["muted"],
                     font=FONT["small"], width=26, anchor="w").pack(side="left")
            bar_out = tk.Frame(r, bg=C["bg"], height=8, width=120)
            bar_out.pack(side="left", padx=6); bar_out.pack_propagate(False)
            tk.Frame(bar_out, bg=col, width=max(4, int(pct * 1.2)), height=8).place(x=0, y=0)
            tk.Label(r, text=f"{cnt} ({pct}%)  {rev_str}", bg=C["panel"],
                     fg=col, font=FONT["small"]).pack(side="left", padx=4)

    def _kpi_card(self, parent, title, value, subtitle, col):
        f = tk.Frame(parent, bg=C["panel"],
                     highlightbackground=C["border"], highlightthickness=1,
                     padx=14, pady=12)
        f.pack(side="left", fill="x", expand=True, padx=(0, 6))
        tk.Label(f, text=title.upper(), bg=C["panel"],
                 fg=C["muted"], font=FONT["label"]).pack(anchor="w")
        tk.Label(f, text=value, bg=C["panel"], fg=col,
                 font=FONT["h2"]).pack(anchor="w")
        tk.Label(f, text=subtitle, bg=C["panel"],
                 fg=C["dim"], font=FONT["tiny"]).pack(anchor="w")

    def _activity_feed(self, parent):
        act_f = tk.Frame(parent, bg=C["panel"],
                         highlightbackground=C["border"], highlightthickness=1)
        act_f.pack(fill="x", padx=20, pady=(0, 20))
        tk.Label(act_f, text="Recent Invoice Activity",
                 bg=C["panel"], fg=C["text"], font=FONT["h3"],
                 padx=14, pady=10).pack(anchor="w")
        tk.Frame(act_f, bg=C["border"], height=1).pack(fill="x")
        events = [(ts, icon, title, sub)
                  for ts, icon, title, sub in self.app.state.get("activity_log", [])
                  if any(k in title for k in
                         ("Invoice", "invoice", "INV", "Paid", "Deposit", "Square", "sent"))]
        feed = events[:10] if events else [("—", "🧾", "No invoice activity yet.", "")]
        for ts, icon, title, sub in feed:
            r = tk.Frame(act_f, bg=C["panel"]); r.pack(fill="x", padx=14, pady=5)
            tk.Label(r, text=icon, bg=C["panel"], font=FONT["body"]).pack(side="left", padx=(0, 8))
            c = tk.Frame(r, bg=C["panel"]); c.pack(side="left", fill="x", expand=True)
            tk.Label(c, text=title, bg=C["panel"], fg=C["text"],
                     font=FONT["small"], anchor="w").pack(fill="x")
            if sub:
                tk.Label(c, text=sub, bg=C["panel"], fg=C["dim"],
                         font=FONT["tiny"], anchor="w").pack(fill="x")
            tk.Label(r, text=ts, bg=C["panel"], fg=C["dim"],
                     font=FONT["tiny"]).pack(side="right")
            tk.Frame(act_f, bg=C["border"], height=1).pack(fill="x", padx=14)

    @staticmethod
    def _in_date(inv, cutoff):
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
