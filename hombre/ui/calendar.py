"""
ui/calendar.py — Calendar tab.
- Click a day: choose Blackout or Create Event
- Blackout days are greyed and blocked from AI booking
- Events are editable with a Staff field
- Auto-populated from invoice approvals
"""

import tkinter as tk
from datetime import datetime
import calendar

from theme import C, FONT
from ui.widgets import btn, ScrollFrame


class EventEditPopup(tk.Toplevel):
    def __init__(self, parent, event: dict, on_save, on_delete=None):
        super().__init__(parent)
        self.title("Edit Event")
        self.configure(bg=C["bg"])
        self.geometry("440x440")
        self.resizable(False, False)
        self.grab_set()
        self.event    = event
        self.on_save  = on_save
        self.on_delete= on_delete
        self.vars     = {}

        tk.Label(self, text="Event Details", bg=C["bg"],
                 fg=C["text"], font=FONT["h3"]).pack(padx=20, pady=(16, 6), anchor="w")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        sf   = ScrollFrame(self, bg=C["bg"])
        sf.pack(fill="both", expand=True)
        form = sf.inner

        for label, key in [
            ("Title",       "title"),
            ("Date (YYYY-MM-DD)", "date"),
            ("Guest Count", "guests"),
            ("Amount",      "amount"),
            ("Staff",       "staff"),
        ]:
            tk.Label(form, text=label, bg=C["bg"], fg=C["muted"],
                     font=FONT["label"]).pack(anchor="w", padx=20, pady=(8, 1))
            var = tk.StringVar(value=event.get(key, ""))
            self.vars[key] = var
            f = tk.Frame(form, bg=C["input_border"], padx=1, pady=1)
            f.pack(fill="x", padx=20)
            tk.Entry(f, textvariable=var, bg=C["input_bg"], fg=C["text"],
                     insertbackground=C["text"], relief="flat",
                     font=FONT["body"]).pack(fill="x", ipady=7)

        tk.Label(form, text="Notes", bg=C["bg"], fg=C["muted"],
                 font=FONT["label"]).pack(anchor="w", padx=20, pady=(8, 1))
        nf = tk.Frame(form, bg=C["input_border"], padx=1, pady=1)
        nf.pack(fill="x", padx=20, pady=(0, 16))
        self.notes_text = tk.Text(nf, bg=C["input_bg"], fg=C["text"],
                                  insertbackground=C["text"], relief="flat",
                                  font=FONT["body"], height=4, wrap="word")
        self.notes_text.pack(fill="x")
        self.notes_text.insert("1.0", event.get("notes", ""))

        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(fill="x", padx=20, pady=12, side="bottom")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", side="bottom")
        btn(btn_row, "Save Changes", bg="success", command=self._save).pack(side="left", padx=(0, 8))
        btn(btn_row, "Cancel", bg="border", fg="text", command=self.destroy).pack(side="left")
        if on_delete:
            btn(btn_row, "Delete", bg="error", command=self._delete).pack(side="right")

    def _save(self):
        data = {k: v.get().strip() for k, v in self.vars.items()}
        data["notes"] = self.notes_text.get("1.0", "end").strip()
        self.on_save(data)
        self.destroy()

    def _delete(self):
        if self.on_delete:
            self.on_delete()
        self.destroy()


class DayChoicePopup(tk.Toplevel):
    """Small popup: Blackout or Create Event."""
    def __init__(self, parent, day_str, on_blackout, on_create):
        super().__init__(parent)
        self.title("")
        self.configure(bg=C["panel"])
        self.geometry("220x110")
        self.resizable(False, False)
        self.grab_set()
        self.overrideredirect(True)

        # Position near parent center
        px = parent.winfo_rootx() + parent.winfo_width()  // 2 - 110
        py = parent.winfo_rooty() + parent.winfo_height() // 2 - 55
        self.geometry(f"+{px}+{py}")

        tk.Label(self, text=day_str, bg=C["panel"], fg=C["muted"],
                 font=FONT["label"]).pack(pady=(12, 6))

        row = tk.Frame(self, bg=C["panel"]); row.pack()
        btn(row, "🚫 Blackout", bg="error", px=12, py=8,
            command=lambda: [on_blackout(), self.destroy()]).pack(side="left", padx=6)
        btn(row, "📅 Create Event", bg="accent", px=12, py=8,
            command=lambda: [self.destroy(), on_create()]).pack(side="left", padx=6)

        btn(self, "Cancel", bg="border", fg="muted", px=10, py=4,
            command=self.destroy).pack(pady=8)


class CalendarTab:
    def __init__(self, app):
        self.app       = app
        self.cal_year  = datetime.now().year
        self.cal_month = datetime.now().month

    def build(self, parent: tk.Frame):
        self._parent = parent

        nav = tk.Frame(parent, bg=C["panel"], height=48)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        tk.Frame(nav, bg=C["border"], height=1).pack(fill="x", side="bottom")

        btn(nav, "◀", bg="bg", fg="text", px=12, py=8,
            command=self._prev).pack(side="left", padx=8, pady=8)
        self._month_lbl = tk.Label(nav, text="", bg=C["panel"],
                                   fg=C["text"], font=FONT["h3"])
        self._month_lbl.pack(side="left", padx=10)
        btn(nav, "▶", bg="bg", fg="text", px=12, py=8,
            command=self._next).pack(side="left", padx=4, pady=8)

        # Legend
        leg = tk.Frame(nav, bg=C["panel"]); leg.pack(side="right", padx=14)
        tk.Frame(leg, bg=C["error"], width=12, height=12).pack(side="left")
        tk.Label(leg, text=" Blackout", bg=C["panel"], fg=C["muted"],
                 font=FONT["tiny"]).pack(side="left", padx=(0, 10))
        tk.Frame(leg, bg=C["accent"], width=12, height=12).pack(side="left")
        tk.Label(leg, text=" Event", bg=C["panel"], fg=C["muted"],
                 font=FONT["tiny"]).pack(side="left")

        self._grid_frame = tk.Frame(parent, bg=C["bg"])
        self._grid_frame.pack(fill="both", expand=True, padx=20, pady=16)

        self._render()

    def _render(self):
        for w in self._grid_frame.winfo_children():
            w.destroy()

        self._month_lbl.config(
            text=datetime(self.cal_year, self.cal_month, 1).strftime("%B %Y"))

        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for c, d in enumerate(days):
            tk.Label(self._grid_frame, text=d, bg=C["bg"], fg=C["muted"],
                     font=FONT["label"], width=10, anchor="center").grid(
                row=0, column=c, padx=2, pady=(0, 4))

        cal    = calendar.monthcalendar(self.cal_year, self.cal_month)
        events = self.app.state.get("calendar_events", [])
        blackouts = set(self.app.state.get("blackout_dates", []))
        today  = datetime.now()

        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Frame(self._grid_frame, bg=C["bg"], width=90, height=80).grid(
                        row=r + 1, column=c, padx=2, pady=2)
                    continue

                day_str  = f"{self.cal_year}-{self.cal_month:02d}-{day:02d}"
                is_today = (day == today.day and self.cal_month == today.month
                            and self.cal_year == today.year)
                is_black = day_str in blackouts

                if is_black:
                    bg = "#D1D5DB"  # greyed out
                    fg = C["dim"]
                elif is_today:
                    bg = C["accent"]
                    fg = "white"
                else:
                    bg = C["panel"]
                    fg = C["text"]

                cell = tk.Frame(self._grid_frame, bg=bg, width=90, height=80,
                                highlightbackground=C["border"], highlightthickness=1)
                cell.grid(row=r + 1, column=c, padx=2, pady=2)
                cell.pack_propagate(False)

                day_lbl = tk.Label(cell, text=str(day), bg=bg, fg=fg, font=FONT["small"])
                day_lbl.pack(anchor="nw", padx=6, pady=4)

                if is_black:
                    tk.Label(cell, text="Blackout", bg=bg, fg=C["dim"],
                             font=FONT["tiny"]).pack(anchor="center")

                day_events = [e for e in events if e.get("date", "").startswith(day_str)]
                for ev in day_events[:2]:
                    staff = f" · {ev['staff']}" if ev.get("staff") else ""
                    ev_lbl = tk.Label(cell,
                                      text=(ev.get("title", "")[:12] + staff)[:14],
                                      bg=C["accent_lt"], fg="white",
                                      font=FONT["tiny"], padx=3, pady=1, anchor="w")
                    ev_lbl.pack(fill="x", padx=3, pady=1)
                    ev_lbl.bind("<Double-Button-1>",
                                lambda e, ev=ev: self._edit_event(ev))

                # Click handler
                for widget in [cell, day_lbl]:
                    widget.bind("<Button-1>",
                                lambda e, d=day, ds=day_str: self._day_click(d, ds))

    def _day_click(self, day, day_str):
        blackouts = self.app.state.get("blackout_dates", [])
        is_black  = day_str in blackouts
        label     = datetime(self.cal_year, self.cal_month, day).strftime("%B %d, %Y")

        if is_black:
            # Already blacked out — ask to remove
            if tk.messagebox.askyesno("Remove Blackout",
                                      f"Remove blackout from {label}?",
                                      parent=self._parent.winfo_toplevel()):
                self.app.state["blackout_dates"].remove(day_str)
                self.app.save()
                self._render()
            return

        DayChoicePopup(
            self._parent.winfo_toplevel(),
            label,
            on_blackout=lambda: self._add_blackout(day_str),
            on_create=lambda: self._create_event(day_str),
        )

    def _add_blackout(self, day_str):
        self.app.state.setdefault("blackout_dates", [])
        if day_str not in self.app.state["blackout_dates"]:
            self.app.state["blackout_dates"].append(day_str)
        self.app.save()
        self._render()

    def _create_event(self, day_str):
        new_event = {
            "title": "", "date": day_str, "guests": "",
            "amount": "", "staff": "", "notes": "", "source": "manual",
        }
        def save(data):
            new_event.update(data)
            if not new_event["title"]:
                return
            self.app.state.setdefault("calendar_events", []).append(new_event)
            self.app.save()
            self._render()
        EventEditPopup(self._parent.winfo_toplevel(), new_event, save)

    def _edit_event(self, ev):
        def save(data):
            ev.update(data)
            self.app.save()
            self._render()
        def delete():
            events = self.app.state.get("calendar_events", [])
            if ev in events:
                events.remove(ev)
            self.app.save()
            self._render()
        EventEditPopup(self._parent.winfo_toplevel(), ev, save, on_delete=delete)

    def _prev(self):
        if self.cal_month == 1:
            self.cal_month = 12; self.cal_year -= 1
        else:
            self.cal_month -= 1
        self._render()

    def _next(self):
        if self.cal_month == 12:
            self.cal_month = 1; self.cal_year += 1
        else:
            self.cal_month += 1
        self._render()

    def refresh(self):
        self._render()

    def is_blackout(self, date_str: str) -> bool:
        """Check if a date is blacked out. Used by AI handoff logic."""
        return date_str in self.app.state.get("blackout_dates", [])
