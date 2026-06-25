"""
ui/messaging.py — Messaging tab.
Master inbox with All / Email / Meta / Ignored filters.
Per-thread AI toggle. Handoff flagging. Multi-turn thread display.
"""

import tkinter as tk
from datetime import datetime
from theme import C, FONT
from ui.widgets import btn, div, ScrollFrame, OvalToggle


SOURCE_COLORS = {
    "Email":     C["info"],
    "Facebook":  C["accent"],
    "Instagram": C["accent"],
}


class MessagingTab:
    def __init__(self, app):
        self.app          = app
        self.active_conv  = None
        self._filter      = "All"

    def build(self, parent: tk.Frame):
        self._parent = parent

        # ── Top filter bar ────────────────────────────────────────────────────
        bar = tk.Frame(parent, bg=C["panel"], height=46)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=C["border"], height=1).pack(fill="x", side="bottom")

        self._filter_btns = {}
        for label in ("All", "Email", "Meta", "Ignored"):
            b = tk.Label(bar, text=label, bg=C["panel"], fg=C["muted"],
                         font=FONT["small"], cursor="hand2", padx=16, pady=14)
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, l=label: self._set_filter(l))
            self._filter_btns[label] = b
        # Note: _set_filter("All") is called at end of build, after _list_inner exists

        # ── Main layout: list left, thread right ─────────────────────────────
        pane = tk.Frame(parent, bg=C["bg"])
        pane.pack(fill="both", expand=True)

        # Conversation list
        list_frame = tk.Frame(pane, bg=C["panel"], width=280,
                              highlightbackground=C["border"], highlightthickness=1)
        list_frame.pack(side="left", fill="y")
        list_frame.pack_propagate(False)
        tk.Label(list_frame, text="CONVERSATIONS", bg=C["panel"],
                 fg=C["muted"], font=FONT["label"], padx=14, pady=10).pack(anchor="w")
        tk.Frame(list_frame, bg=C["border"], height=1).pack(fill="x")
        self._list_scroll = ScrollFrame(list_frame, bg=C["panel"])
        self._list_scroll.pack(fill="both", expand=True)
        self._list_inner  = self._list_scroll.inner

        # Thread view
        right = tk.Frame(pane, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True)

        # Thread header
        self._thread_header = tk.Frame(right, bg=C["panel"], height=54)
        self._thread_header.pack(fill="x")
        self._thread_header.pack_propagate(False)
        tk.Frame(self._thread_header, bg=C["border"], height=1).pack(fill="x", side="bottom")
        self._thread_name = tk.Label(self._thread_header, text="Select a conversation",
                                     bg=C["panel"], fg=C["text"], font=FONT["h3"], padx=16)
        self._thread_name.pack(side="left", pady=14)

        # Per-thread AI toggle
        self._ai_toggle_var = tk.BooleanVar(value=True)
        tog_frame = tk.Frame(self._thread_header, bg=C["panel"])
        tog_frame.pack(side="right", padx=16, pady=12)
        tk.Label(tog_frame, text="AI Assist", bg=C["panel"],
                 fg=C["muted"], font=FONT["tiny"]).pack(side="left", padx=(0, 6))
        self._ai_tog = OvalToggle(tog_frame, self._ai_toggle_var,
                                  on_color=C["success"],
                                  command=self._on_ai_toggle, bg=C["panel"])
        self._ai_tog.pack(side="left")

        # Handoff badge (hidden by default)
        self._handoff_badge = tk.Label(self._thread_header, text="⚠ Needs Owner",
                                       bg=C["warn"], fg="white", font=FONT["small"],
                                       padx=10, pady=4)

        # Thread messages
        self._thread_sf = ScrollFrame(right, bg=C["bg"])
        self._thread_sf.pack(fill="both", expand=True)
        self._thread_inner = self._thread_sf.inner

        # Reply box
        reply_bar = tk.Frame(right, bg=C["panel"], height=70)
        reply_bar.pack(fill="x", side="bottom")
        reply_bar.pack_propagate(False)
        tk.Frame(reply_bar, bg=C["border"], height=1).pack(fill="x", side="top")
        self._reply_var = tk.StringVar()
        entry = tk.Entry(reply_bar, textvariable=self._reply_var,
                         bg=C["input_bg"], fg=C["text"], font=FONT["body"],
                         relief="flat", insertbackground=C["text"])
        entry.pack(side="left", fill="x", expand=True, padx=14, pady=14, ipady=6)
        entry.bind("<Return>", lambda e: self._send_manual())
        btn(reply_bar, "Send", bg="accent", command=self._send_manual,
            px=16, py=8).pack(side="right", padx=(0, 14), pady=14)

        self._set_filter("All")
        self._populate_list()

    # ── Filter ────────────────────────────────────────────────────────────────

    def _set_filter(self, label):
        self._filter = label
        for k, b in self._filter_btns.items():
            active = k == label
            b.config(
                fg=C["accent"] if active else C["muted"],
                font=(FONT["small"][0], FONT["small"][1], "bold") if active else FONT["small"],
            )
        if hasattr(self, "_list_inner"):
            self._populate_list()

    def _visible_convos(self):
        convos = self.app.state.get("conversations", [])
        f = self._filter
        if f == "All":
            return [c for c in convos if c.get("status") != "ignored"]
        if f == "Email":
            return [c for c in convos if c.get("source") == "Email"
                    and c.get("status") != "ignored"]
        if f == "Meta":
            return [c for c in convos if c.get("source") in ("Facebook", "Instagram")
                    and c.get("status") != "ignored"]
        if f == "Ignored":
            return [c for c in convos if c.get("status") == "ignored"]
        return convos

    # ── Conversation list ─────────────────────────────────────────────────────

    def _populate_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()
        for conv in self._visible_convos():
            self._conv_row(conv)

    def _conv_row(self, conv):
        is_active = self.active_conv and self.active_conv["id"] == conv["id"]
        bg = C["card2"] if is_active else C["panel"]
        row = tk.Frame(self._list_inner, bg=bg, cursor="hand2")
        row.pack(fill="x")
        tk.Frame(row, bg=C["border"], height=1).pack(fill="x")

        inner = tk.Frame(row, bg=bg, padx=12, pady=8)
        inner.pack(fill="x")

        # Source badge
        src_col = SOURCE_COLORS.get(conv.get("source", "Email"), C["muted"])
        tk.Label(inner, text=conv.get("source", "Email")[:2].upper(),
                 bg=src_col, fg="white", font=FONT["tiny"],
                 padx=4, pady=1).pack(side="left", anchor="nw", padx=(0, 8))

        text_frame = tk.Frame(inner, bg=bg)
        text_frame.pack(side="left", fill="x", expand=True)

        name_row = tk.Frame(text_frame, bg=bg); name_row.pack(fill="x")
        tk.Label(name_row, text=conv.get("name", conv.get("email", "Unknown")),
                 bg=bg, fg=C["text"], font=FONT["small"]).pack(side="left")
        if conv.get("status") == "needs_owner":
            tk.Label(name_row, text=" ⚠", bg=bg, fg=C["warn"],
                     font=FONT["tiny"]).pack(side="left")
        tk.Label(name_row, text=conv.get("last_time", ""),
                 bg=bg, fg=C["dim"], font=FONT["tiny"]).pack(side="right")

        preview = conv.get("last_msg", "")[:50]
        tk.Label(text_frame, text=preview, bg=bg, fg=C["muted"],
                 font=FONT["tiny"], anchor="w").pack(fill="x")

        row.bind("<Button-1>",   lambda e, c=conv: self._open(c))
        inner.bind("<Button-1>", lambda e, c=conv: self._open(c))
        for child in inner.winfo_children():
            child.bind("<Button-1>", lambda e, c=conv: self._open(c))

    # ── Thread view ───────────────────────────────────────────────────────────

    def _open(self, conv):
        self.active_conv = conv
        self._thread_name.config(
            text=conv.get("name", conv.get("email", "Unknown")))

        # AI toggle state for this thread
        self._ai_toggle_var.set(conv.get("ai_assist", True))
        self._ai_tog.refresh()

        # Handoff badge
        if conv.get("status") == "needs_owner":
            self._handoff_badge.pack(side="right", padx=8, pady=10)
        else:
            self._handoff_badge.pack_forget()

        # Render messages
        for w in self._thread_inner.winfo_children():
            w.destroy()
        for msg in conv.get("messages", []):
            self._msg_bubble(msg)

        self._populate_list()

    def _msg_bubble(self, msg):
        frm = msg.get("from", "customer")
        bg  = C["bubble_ai"] if frm == "ai" else (
              C["bubble_me"]  if frm == "manual" else C["bubble_in"])
        align = "e" if frm in ("ai", "manual") else "w"

        row = tk.Frame(self._thread_inner, bg=C["bg"])
        row.pack(fill="x", padx=14, pady=4, anchor=align)

        bubble = tk.Frame(row, bg=bg, padx=12, pady=8)
        bubble.pack(anchor=align)

        prefix = "🤖 AI  " if frm == "ai" else ("✉ You  " if frm == "manual" else "")
        if prefix:
            tk.Label(bubble, text=prefix, bg=bg, fg=C["muted"],
                     font=FONT["tiny"]).pack(anchor="w")

        tk.Label(bubble, text=msg.get("text", ""), bg=bg, fg=C["text"],
                 font=FONT["body"], wraplength=480, justify="left",
                 anchor="w").pack(anchor="w")
        tk.Label(bubble, text=msg.get("time", ""), bg=bg, fg=C["dim"],
                 font=FONT["tiny"]).pack(anchor="e")

        # Show skip/ignore reason if present
        if msg.get("skip_reason"):
            tk.Label(bubble, text=f"[Filtered: {msg['skip_reason']}]",
                     bg=bg, fg=C["warn"], font=FONT["tiny"]).pack(anchor="w")

    # ── AI toggle per thread ──────────────────────────────────────────────────

    def _on_ai_toggle(self, val):
        if self.active_conv:
            self.active_conv["ai_assist"] = val
            self.app.save()

    # ── Manual send ──────────────────────────────────────────────────────────

    def _send_manual(self):
        if not self.active_conv:
            return
        text = self._reply_var.get().strip()
        if not text:
            return
        self._reply_var.set("")
        ts = datetime.now().strftime("%I:%M %p")
        msg = {"from": "manual", "text": text, "time": ts}
        self.active_conv.setdefault("messages", []).append(msg)
        self.active_conv["last_msg"]  = text
        self.active_conv["last_time"] = ts

        # Send via correct channel
        conv = self.active_conv
        src  = conv.get("source", "Email")
        try:
            if src == "Email":
                self.app.email_bot.send_reply(
                    conv.get("email", ""),
                    conv.get("subject", "El Hombre Taco"),
                    text,
                    in_reply_to=conv.get("last_message_id", ""),
                )
            else:
                self.app.meta_bot.send_reply(conv.get("raw", {}), text)
            self.app.log_activity("📤", f"Manual reply → {conv.get('name','')}", text[:40])
        except Exception as ex:
            self.app.log_activity("⚠", "Send failed", str(ex))

        self.app.save()
        self._open(conv)

    # ── Refresh (called when new message arrives) ─────────────────────────────

    def refresh(self):
        self._populate_list()
        if self.active_conv:
            # Re-open to update thread view
            updated = next(
                (c for c in self.app.state.get("conversations", [])
                 if c["id"] == self.active_conv["id"]),
                None,
            )
            if updated:
                self._open(updated)
