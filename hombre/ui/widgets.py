"""
ui/widgets.py — Shared UI primitives used across all tabs.
"""

import tkinter as tk
from tkinter import ttk
from theme import C, FONT


# ── Scroll Frame ──────────────────────────────────────────────────────────────

class ScrollFrame(tk.Frame):
    _all = []

    def __init__(self, parent, bg=None, **kw):
        bg = bg or C["bg"]
        super().__init__(parent, bg=bg, **kw)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.inner  = tk.Frame(self.canvas, bg=bg)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        ScrollFrame._all.append(self)
        top = self.winfo_toplevel()
        if not getattr(top, "_sf_bound", False):
            top._sf_bound = True
            top.bind_all("<MouseWheel>", ScrollFrame._dispatch)
            top.bind_all("<Button-4>",   ScrollFrame._dispatch)
            top.bind_all("<Button-5>",   ScrollFrame._dispatch)

    @classmethod
    def _dispatch(cls, e):
        try:
            x, y = cls._all[0].winfo_pointerxy()
            w    = cls._all[0].winfo_containing(x, y)
        except Exception:
            return
        while w:
            for sf in cls._all:
                if w in (sf, sf.canvas, sf.inner):
                    if e.num == 4:
                        sf.canvas.yview_scroll(-1, "units")
                    elif e.num == 5:
                        sf.canvas.yview_scroll(1, "units")
                    else:
                        step = int(-e.delta / 120) if abs(e.delta) >= 120 else (-1 if e.delta > 0 else 1)
                        sf.canvas.yview_scroll(step, "units")
                    return
            w = getattr(w, "master", None)


# ── Toggle Switch ─────────────────────────────────────────────────────────────

class OvalToggle(tk.Canvas):
    def __init__(self, parent, var, on_color=None, locked_var=None, command=None, **kw):
        kw.setdefault("bg", C["panel"])
        super().__init__(parent, width=48, height=24, highlightthickness=0, **kw)
        self.var        = var
        self.on_color   = on_color or C["success"]
        self.locked_var = locked_var
        self.command    = command
        self.bind("<Button-1>", self._toggle)
        self._draw()

    def _draw(self):
        self.delete("all")
        on  = self.var.get()
        locked = self.locked_var and self.locked_var.get()
        col = C["border_dk"] if locked else (self.on_color if on else C["border_dk"])
        # track
        self.create_oval(0, 2, 22, 22, fill=col, outline="")
        self.create_oval(26, 2, 48, 22, fill=col, outline="")
        self.create_rectangle(11, 2, 37, 22, fill=col, outline="")
        # knob
        if on:
            self.create_oval(28, 4, 46, 20, fill="white", outline="")
        else:
            self.create_oval(2, 4, 20, 20, fill="white", outline="")

    def _toggle(self, _=None):
        if self.locked_var and self.locked_var.get():
            return
        self.var.set(not self.var.get())
        self._draw()
        if self.command:
            self.command(self.var.get())

    def refresh(self):
        self._draw()


# ── Widget Helpers ────────────────────────────────────────────────────────────

def lbl(parent, text, fg="text", font=None, bg="panel", **kw):
    return tk.Label(
        parent, text=text,
        bg=C.get(bg, bg), fg=C.get(fg, fg),
        font=font or FONT["body"], **kw
    )

def div(parent, padx=16, color="border"):
    tk.Frame(parent, bg=C.get(color, C["border"]), height=1).pack(fill="x", padx=padx, pady=4)

def btn(parent, text, bg="accent", fg="btn_txt", command=None, px=14, py=7, **kw):
    b = tk.Label(
        parent, text=text,
        bg=C.get(bg, bg), fg=C.get(fg, fg),
        font=FONT["small"], cursor="hand2", padx=px, pady=py, **kw
    )
    if command:
        b.bind("<Button-1>", lambda e: command())
    return b

def entry(parent, var, secret=False, state="normal", width=None):
    """Flat entry widget with border frame."""
    f = tk.Frame(parent, bg=C["input_border"], padx=1, pady=1)
    kw = dict(
        textvariable=var,
        bg=C["input_bg"], fg=C["text"],
        insertbackground=C["text"],
        relief="flat", font=FONT["body"],
        show="*" if secret else "",
        state=state,
        disabledbackground=C["bg"],
        disabledforeground=C["dim"],
    )
    if width:
        kw["width"] = width
    tk.Entry(f, **kw).pack(fill="x", ipady=7)
    return f

def card(parent, title, value, subtitle="", value_color="text", **kw):
    """KPI card — returns (frame, value_label)."""
    f = tk.Frame(
        parent, bg=C["panel"],
        highlightbackground=C["border"], highlightthickness=1,
        padx=20, pady=16, **kw
    )
    tk.Label(f, text=title, bg=C["panel"], fg=C["muted"], font=FONT["label"]).pack(anchor="w")
    v = tk.Label(f, text=value, bg=C["panel"], fg=C.get(value_color, C["text"]),
                 font=FONT["h1"])
    v.pack(anchor="w", pady=(2, 0))
    if subtitle:
        tk.Label(f, text=subtitle, bg=C["panel"], fg=C["dim"], font=FONT["tiny"]).pack(anchor="w")
    return f, v

def section_header(parent, text, padx=20, pady=(18, 6)):
    tk.Label(
        parent, text=text.upper(),
        bg=C["bg"], fg=C["muted"], font=FONT["label"]
    ).pack(anchor="w", padx=padx, pady=pady)
