"""
ui/outreach.py — Outreach tab.
Email (Apple Mail-style popup) and SMS (iMessage-style) outreach
using contacts from the Directory (app.state["customers"]).
"""

import tkinter as tk
from tkinter import ttk, messagebox
import smtplib, threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from theme import C, FONT
from ui.widgets import btn


# ── Recipient filter helpers ──────────────────────────────────────────────────

def _get_recipients(state, mode):
    """
    mode: "ALL" | "ALL_EMAIL" | "ALL_NUMBER"
    Returns list of customer dicts matching the filter.
    """
    customers = state.get("customers", [])
    if mode == "ALL":
        return [c for c in customers if c.get("email") or c.get("phone")]
    if mode == "ALL_EMAIL":
        return [c for c in customers if c.get("email") and not c.get("phone")]
    if mode == "ALL_NUMBER":
        return [c for c in customers if c.get("phone") and not c.get("email")]
    return []


RECIPIENT_OPTIONS = [
    ("ALL — Everyone with email or phone",  "ALL"),
    ("ALL W/ EMAIL — Email, no phone",      "ALL_EMAIL"),
    ("ALL W/ NUMBER — Phone, no email",     "ALL_NUMBER"),
]


# ── Email compose popup (Apple Mail style) ────────────────────────────────────

class EmailComposePopup(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("New Message")
        self.configure(bg="#F5F5F7")          # light Mac-like background
        self.geometry("640x540")
        self.resizable(True, True)
        self.grab_set()
        self._build()

    def _build(self):
        # ── Title bar area ────────────────────────────────────────────────
        title_row = tk.Frame(self, bg="#E8E8EA", height=40)
        title_row.pack(fill="x")
        title_row.pack_propagate(False)
        tk.Label(title_row, text="New Message", bg="#E8E8EA",
                 fg="#1C1C1E", font=("Helvetica", 13, "bold")).pack(pady=10)

        # ── To row (dropdown) ─────────────────────────────────────────────
        self._build_field_row("To")
        self._to_var = tk.StringVar(value=RECIPIENT_OPTIONS[0][0])
        to_frame = tk.Frame(self, bg="white")
        to_frame.pack(fill="x")
        tk.Label(to_frame, text="To:", width=8, anchor="w",
                 bg="white", fg="#1C1C1E",
                 font=("Helvetica", 11)).pack(side="left", padx=(12, 0), pady=6)
        self._to_menu = ttk.Combobox(
            to_frame, textvariable=self._to_var,
            values=[o[0] for o in RECIPIENT_OPTIONS],
            state="readonly", font=("Helvetica", 11), width=44
        )
        self._to_menu.pack(side="left", padx=8, pady=6)
        tk.Frame(self, bg="#D1D1D6", height=1).pack(fill="x")

        # ── Subject row ───────────────────────────────────────────────────
        subj_row = tk.Frame(self, bg="white")
        subj_row.pack(fill="x")
        tk.Label(subj_row, text="Subject:", width=8, anchor="w",
                 bg="white", fg="#1C1C1E",
                 font=("Helvetica", 11)).pack(side="left", padx=(12, 0), pady=6)
        self._subj_var = tk.StringVar()
        tk.Entry(subj_row, textvariable=self._subj_var,
                 bg="white", fg="#1C1C1E", relief="flat",
                 font=("Helvetica", 11),
                 insertbackground="#1C1C1E").pack(side="left", fill="x",
                                                  expand=True, padx=8, ipady=5)
        tk.Frame(self, bg="#D1D1D6", height=1).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────────────
        self._body = tk.Text(self, font=("Helvetica", 12), bg="white",
                             fg="#1C1C1E", relief="flat", wrap="word",
                             padx=14, pady=12, insertbackground="#1C1C1E",
                             selectbackground="#0071E3", selectforeground="white")
        self._body.pack(fill="both", expand=True)

        # ── Bottom toolbar ────────────────────────────────────────────────
        tk.Frame(self, bg="#D1D1D6", height=1).pack(fill="x")
        bar = tk.Frame(self, bg="#F5F5F7", height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        self._status = tk.Label(bar, text="", bg="#F5F5F7",
                                fg="#636366", font=("Helvetica", 10))
        self._status.pack(side="left", padx=12, pady=10)

        # Blue Mac-style send button
        send = tk.Button(bar, text="Send",
                         bg="#0071E3", fg="white", relief="flat",
                         font=("Helvetica", 12, "bold"),
                         padx=20, pady=4, cursor="hand2",
                         activebackground="#0051A8", activeforeground="white",
                         bd=0, command=self._send)
        send.pack(side="right", padx=12, pady=8)

    def _build_field_row(self, label):
        pass  # placeholder — rows built inline above

    def _selected_mode(self):
        label = self._to_var.get()
        for display, code in RECIPIENT_OPTIONS:
            if display == label:
                return code
        return "ALL"

    def _send(self):
        subject = self._subj_var.get().strip()
        body    = self._body.get("1.0", "end").strip()
        if not subject:
            messagebox.showwarning("Missing subject", "Please add a subject.", parent=self)
            return
        if not body:
            messagebox.showwarning("Empty body", "Please write a message.", parent=self)
            return

        mode       = self._selected_mode()
        recipients = _get_recipients(self.app.state, mode)
        emails     = [c["email"] for c in recipients if c.get("email")]

        if not emails:
            messagebox.showwarning("No recipients",
                "No contacts match that filter with an email address.", parent=self)
            return

        if not messagebox.askyesno("Confirm",
                f"Send to {len(emails)} recipient(s)?", parent=self):
            return

        secrets = self.app.secrets
        smtp_user = secrets.get("email", "")
        smtp_pass = secrets.get("app_password", "")

        self._status.config(text=f"Sending to {len(emails)}…", fg="#636366")
        self.update()

        def worker():
            sent = errors = 0
            try:
                with smtplib.SMTP("smtp.gmail.com", 587) as s:
                    s.starttls()
                    s.login(smtp_user, smtp_pass)
                    for addr in emails:
                        try:
                            msg = MIMEMultipart("alternative")
                            msg["From"]    = smtp_user
                            msg["To"]      = addr
                            msg["Subject"] = subject
                            msg.attach(MIMEText(body, "plain"))
                            s.send_message(msg)
                            sent += 1
                        except Exception:
                            errors += 1
            except Exception as e:
                self.after(0, lambda: self._status.config(
                    text=f"SMTP error: {e}", fg="red"))
                return
            summary = f"✓ {sent} sent" + (f"  ·  {errors} failed" if errors else "")
            self.after(0, lambda: self._status.config(text=summary, fg="#34C759"))

        threading.Thread(target=worker, daemon=True).start()


# ── SMS compose panel (iMessage style) ───────────────────────────────────────

class SMSPanel(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        self._log = []   # list of (direction, text) — "out" only for now
        self._build()

    def _build(self):
        # ── To dropdown ──────────────────────────────────────────────────
        top = tk.Frame(self, bg=C["panel"])
        top.pack(fill="x", padx=0, pady=0)

        tk.Label(top, text="Send To:", bg=C["panel"], fg=C["muted"],
                 font=FONT["label"]).pack(side="left", padx=(16, 6), pady=10)

        self._to_var = tk.StringVar(value=RECIPIENT_OPTIONS[0][0])
        self._to_menu = ttk.Combobox(
            top, textvariable=self._to_var,
            values=[o[0] for o in RECIPIENT_OPTIONS],
            state="readonly", font=("Helvetica", 11), width=42
        )
        self._to_menu.pack(side="left", padx=6, pady=10)

        self._count_lbl = tk.Label(top, text="", bg=C["panel"],
                                   fg=C["muted"], font=FONT["tiny"])
        self._count_lbl.pack(side="left", padx=6)
        self._to_menu.bind("<<ComboboxSelected>>", self._update_count)
        self._update_count()

        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        # ── Message bubble area ───────────────────────────────────────────
        self._bubble_frame = tk.Frame(self, bg=C["bg"])
        self._bubble_frame.pack(fill="both", expand=True, padx=0, pady=0)

        self._canvas = tk.Canvas(self._bubble_frame, bg=C["bg"],
                                 highlightthickness=0)
        vsb = ttk.Scrollbar(self._bubble_frame, orient="vertical",
                             command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(self._canvas, bg=C["bg"])
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", lambda e: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(
            self._canvas_window, width=e.width))

        # ── Input area ────────────────────────────────────────────────────
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")
        input_row = tk.Frame(self, bg=C["panel"], pady=10)
        input_row.pack(fill="x", padx=12)

        self._msg_var = tk.StringVar()
        entry = tk.Entry(input_row, textvariable=self._msg_var,
                         bg=C["input_bg"], fg=C["text"], relief="flat",
                         font=("Helvetica", 12), insertbackground=C["text"])
        entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        entry.bind("<Return>", lambda e: self._send())

        self._send_btn = tk.Button(
            input_row, text="⬆", font=("Helvetica", 14, "bold"),
            bg=C["accent"], fg="white", relief="flat",
            width=3, cursor="hand2",
            activebackground=C.get("accent_hover", C["accent"]),
            command=self._send
        )
        self._send_btn.pack(side="right")

        self._status = tk.Label(self, text="", bg=C["bg"],
                                fg=C["muted"], font=FONT["tiny"])
        self._status.pack(pady=(0, 4))

    def _selected_mode(self):
        label = self._to_var.get()
        for display, code in RECIPIENT_OPTIONS:
            if display == label:
                return code
        return "ALL"

    def _update_count(self, _=None):
        mode = self._selected_mode()
        recipients = _get_recipients(self.app.state, mode)
        phones = [c for c in recipients if c.get("phone")]
        self._count_lbl.config(text=f"{len(phones)} with phone number")

    def _add_bubble(self, text, direction="out"):
        """Add an iMessage-style bubble to the conversation."""
        row = tk.Frame(self._inner, bg=C["bg"])
        row.pack(fill="x", padx=12, pady=4,
                 anchor="e" if direction == "out" else "w")

        color   = C["accent"] if direction == "out" else C["panel"]
        fg      = "white"     if direction == "out" else C["text"]
        anchor  = "e"         if direction == "out" else "w"

        bubble = tk.Label(row, text=text, bg=color, fg=fg,
                          font=("Helvetica", 11), wraplength=380,
                          justify="left", padx=12, pady=8,
                          relief="flat")
        bubble.pack(side="right" if direction == "out" else "left")
        self._log.append((direction, text))

        # scroll to bottom
        self._inner.update_idletasks()
        self._canvas.yview_moveto(1.0)

    def _send(self):
        text = self._msg_var.get().strip()
        if not text:
            return

        mode       = self._selected_mode()
        recipients = _get_recipients(self.app.state, mode)
        phones     = [c["phone"] for c in recipients if c.get("phone")]

        if not phones:
            messagebox.showwarning("No recipients",
                "No contacts match that filter with a phone number.")
            return

        if not messagebox.askyesno("Confirm",
                f"Send SMS to {len(phones)} recipient(s)?\n\n"
                "Note: SMS requires a Twilio account configured in Settings."):
            return

        self._add_bubble(text, "out")
        self._msg_var.set("")

        secrets = self.app.secrets
        account_sid = secrets.get("twilio_sid", "")
        auth_token  = secrets.get("twilio_token", "")
        from_number = secrets.get("twilio_from", "")

        if not account_sid or not auth_token or not from_number:
            self._status.config(
                text="⚠ Add twilio_sid / twilio_token / twilio_from to secrets.json",
                fg="orange")
            return

        self._status.config(text=f"Sending to {len(phones)}…", fg=C["muted"])

        def worker():
            try:
                from twilio.rest import Client
                client = Client(account_sid, auth_token)
                sent = errors = 0
                for phone in phones:
                    try:
                        client.messages.create(
                            body=text, from_=from_number, to=phone)
                        sent += 1
                    except Exception:
                        errors += 1
                summary = f"✓ {sent} sent" + (f"  ·  {errors} failed" if errors else "")
                self.after(0, lambda: self._status.config(text=summary, fg=C["success"]))
            except ImportError:
                self.after(0, lambda: self._status.config(
                    text="pip install twilio  to enable SMS", fg="orange"))
            except Exception as e:
                self.after(0, lambda: self._status.config(
                    text=f"Error: {e}", fg=C["error"]))

        threading.Thread(target=worker, daemon=True).start()


# ── Outreach tab shell ────────────────────────────────────────────────────────

class OutreachTab:
    def __init__(self, app):
        self.app = app

    def build(self, parent: tk.Frame):
        self._parent = parent

        # ── Header ───────────────────────────────────────────────────────
        top = tk.Frame(parent, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=14)
        tk.Label(top, text="Outreach", bg=C["bg"],
                 fg=C["text"], font=FONT["h2"]).pack(side="left")

        # ── Channel picker ────────────────────────────────────────────────
        picker = tk.Frame(parent, bg=C["bg"])
        picker.pack(pady=(0, 16))

        tk.Label(picker, text="Choose outreach type:",
                 bg=C["bg"], fg=C["muted"],
                 font=FONT["body"]).pack(side="left", padx=(0, 16))

        self._mode = tk.StringVar(value="")

        # Content area that swaps between email/sms views
        self._content = tk.Frame(parent, bg=C["bg"])
        self._content.pack(fill="both", expand=True)

        def pick(mode):
            self._mode.set(mode)
            # Highlight active button
            email_btn.config(
                bg=C["accent"] if mode == "email" else C["panel"],
                fg="white"     if mode == "email" else C["text"])
            sms_btn.config(
                bg=C["accent"] if mode == "sms" else C["panel"],
                fg="white"     if mode == "sms" else C["text"])
            # Clear and rebuild content
            for w in self._content.winfo_children():
                w.destroy()
            if mode == "email":
                # Show button to open the popup
                launch = tk.Frame(self._content, bg=C["bg"])
                launch.pack(expand=True)
                tk.Label(launch,
                         text="✉  Email Outreach",
                         bg=C["bg"], fg=C["text"],
                         font=FONT["h3"]).pack(pady=(60, 8))
                tk.Label(launch,
                         text="Opens an Apple Mail-style compose window.\n"
                              "Choose your recipient group from the To: dropdown.",
                         bg=C["bg"], fg=C["muted"],
                         font=FONT["body"], justify="center").pack(pady=(0, 24))
                tk.Button(launch, text="  ✉  Compose Email  ",
                          bg=C["accent"], fg="white", relief="flat",
                          font=("Helvetica", 13, "bold"),
                          padx=20, pady=10, cursor="hand2",
                          activebackground=C.get("accent_hover", C["accent"]),
                          command=lambda: EmailComposePopup(
                              parent.winfo_toplevel(), self.app)
                          ).pack()
            else:
                # Inline iMessage panel
                SMSPanel(self._content, self.app).pack(
                    fill="both", expand=True)

        email_btn = tk.Button(picker, text="✉  Email",
                              bg=C["panel"], fg=C["text"], relief="flat",
                              font=FONT["body"], padx=20, pady=8,
                              cursor="hand2",
                              command=lambda: pick("email"))
        email_btn.pack(side="left", padx=4)

        sms_btn = tk.Button(picker, text="💬  Text",
                            bg=C["panel"], fg=C["text"], relief="flat",
                            font=FONT["body"], padx=20, pady=8,
                            cursor="hand2",
                            command=lambda: pick("sms"))
        sms_btn.pack(side="left", padx=4)

        # Default to email
        pick("email")
