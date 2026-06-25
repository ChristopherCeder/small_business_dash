"""
ui/settings.py — Settings tab.
Granular AI prompt boxes, credentials, bot toggles, admin-locked code editor.
"""

import os, sys, shutil, subprocess, threading
import tkinter as tk
from tkinter import messagebox, simpledialog

from theme import C, FONT
from ui.widgets import btn, div, entry, section_header, ScrollFrame, OvalToggle
import config as cfg_module


class SettingsTab:
    def __init__(self, app):
        self.app             = app
        self._locked         = tk.BooleanVar(value=True)
        self._code_locked    = tk.BooleanVar(value=True)
        self._entry_widgets  = []
        self._prompt_widgets = {}   # key → tk.Text

    def build(self, parent: tk.Frame):
        self._parent = parent

        # ── Lock bar ─────────────────────────────────────────────────────────
        lock_bar = tk.Frame(parent, bg=C["panel"], height=50)
        lock_bar.pack(fill="x")
        lock_bar.pack_propagate(False)
        tk.Frame(lock_bar, bg=C["border"], height=1).pack(fill="x", side="bottom")

        self._lock_lbl = tk.Label(lock_bar, text="🔒  Settings Locked",
                                  bg=C["panel"], fg=C["warn"], font=FONT["h3"])
        self._lock_lbl.pack(side="left", padx=18, pady=10)
        btn(lock_bar, "Unlock All", bg="warn", command=self._toggle_lock,
            px=14, py=5).pack(side="left", padx=8)

        sf    = ScrollFrame(parent)
        sf.pack(fill="both", expand=True)
        inner = sf.inner

        # ── Bot toggles ───────────────────────────────────────────────────────
        section_header(inner, "Automation")
        self._bot_toggles = []
        for label, attr, col in [
            ("Email Bot (auto-reply every 60s)", "email_bot_var", C["success"]),
            ("Instagram Bot",                    "ig_bot_var",    C["success"]),
            ("Facebook Bot",                     "fb_bot_var",    C["success"]),
            ("Global AI Assist",                 "global_ai_var", C["accent"]),
            ("Auto-Draft Invoices from AI",      "auto_inv_var",  C["gold"]),
        ]:
            row = tk.Frame(inner, bg=C["bg"]); row.pack(fill="x", padx=24, pady=5)
            tk.Label(row, text=label, bg=C["bg"], fg=C["muted"],
                     font=FONT["body"], width=42, anchor="w").pack(side="left")
            tog = OvalToggle(row, getattr(self.app, attr),
                             on_color=col, locked_var=self._locked,
                             command=lambda v, a=attr: self._bot_cb(a, v),
                             bg=C["bg"])
            tog.pack(side="left", padx=8)
            self._bot_toggles.append(tog)
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=20, pady=8)

        # ── Credentials (locked by default) ──────────────────────────────────
        section_header(inner, "Credentials (stored in secrets.json)")
        tk.Label(inner, text="⚠  These are read from secrets.json. Edit that file directly "
                             "or unlock and save here.",
                 bg=C["bg"], fg=C["dim"], font=FONT["tiny"]).pack(anchor="w", padx=24, pady=(0, 6))

        cred_sections = [
            ("Gmail", [
                ("Email Address",      "email",          False),
                ("App Password",       "app_password",   True),
                ("Forward Replies To", "forward_to",     False),
                ("Subject Filter",     "subject_filter", False),
                ("Poll Interval (sec)","interval",       False),
            ]),
            ("Claude AI", [("API Key", "claude_api_key", True)]),
            ("Meta — Facebook & Instagram", [
                ("Facebook Page ID",  "fb_page_id",     False),
                ("Page Access Token", "fb_page_token",  True),
                ("App Secret",        "fb_app_secret",  True),
                ("Verify Token",      "fb_verify_token",False),
                ("Instagram User ID", "ig_user_id",     False),
            ]),
            ("Square Payments", [
                ("Application ID",  "sq_app_id",       False),
                ("Access Token",    "sq_access_token", True),
                ("Environment",     "sq_environment",  False),
                ("Webhook Secret",  "sq_webhook_secret",True),
            ]),
            ("Admin", [("Admin PIN (for code editor)", "admin_pin", True)]),
        ]

        self._cred_vars = {}
        self._cred_entries = []
        for sec_name, fields in cred_sections:
            section_header(inner, sec_name, padx=24, pady=(10, 3))
            frm = tk.Frame(inner, bg=C["bg"]); frm.pack(fill="x", padx=24)
            combined = {**self.app.secrets, **self.app.settings}
            for label, key, secret in fields:
                tk.Label(frm, text=label, bg=C["bg"], fg=C["muted"],
                         font=FONT["label"]).pack(anchor="w", pady=(6, 1))
                var = tk.StringVar(value=combined.get(key, ""))
                self._cred_vars[key] = var
                f = tk.Frame(frm, bg=C["input_border"], padx=1, pady=1)
                f.pack(fill="x")
                e = tk.Entry(f, textvariable=var, bg=C["bg"], fg=C["dim"],
                             insertbackground=C["text"], relief="flat", font=FONT["body"],
                             show="*" if secret else "", state="disabled",
                             disabledbackground=C["bg"], disabledforeground=C["dim"])
                e.pack(fill="x", ipady=7)
                self._cred_entries.append(e)

        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=20, pady=10)

        # ── Granular AI Prompts ───────────────────────────────────────────────
        section_header(inner, "AI Brain — Granular Prompt Control")

        for label, key, height, warning in [
            ("Sales Style & Tone",
             "ai_sales_style", 6,
             "Controls voice, persuasion, follow-up questions."),
            ("Business Facts & FAQ",
             "ai_business_facts", 6,
             "Pricing, service area, event types, deposit terms."),
            ("Handoff Rules",
             "ai_handoff_rules", 6,
             "When AI stops and flags 'Needs Owner'. Use exact rules."),
        ]:
            section_header(inner, label, padx=24, pady=(10, 2))
            tk.Label(inner, text=warning, bg=C["bg"], fg=C["dim"],
                     font=FONT["tiny"]).pack(anchor="w", padx=24, pady=(0, 3))
            cf = tk.Frame(inner, bg=C["input_border"], padx=1, pady=1)
            cf.pack(fill="x", padx=24, pady=(0, 6))
            t = tk.Text(cf, bg=C["bg"], fg=C["dim"], insertbackground=C["text"],
                        font=FONT["small"], relief="flat", height=height,
                        wrap="word", state="disabled")
            t.pack(fill="x")
            t.config(state="normal")
            t.insert("1.0", self.app.settings.get(key, ""))
            t.config(state="disabled")
            self._prompt_widgets[key] = t

        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=20, pady=10)

        # ── Code Editor (admin-locked) ────────────────────────────────────────
        self._build_code_editor(inner)

        # ── Save button ───────────────────────────────────────────────────────
        tk.Frame(inner, bg=C["border"], height=1).pack(fill="x", padx=20, pady=6)
        btn(inner, "  Save All Settings  ", bg="accent",
            command=self._save, px=20, py=10).pack(anchor="w", padx=24, pady=16)

    # ── Lock ──────────────────────────────────────────────────────────────────

    def _toggle_lock(self):
        locked = not self._locked.get()
        self._locked.set(locked)
        self._lock_lbl.config(
            text="🔒  Settings Locked" if locked else "🔓  Settings Unlocked",
            fg=C["warn"] if locked else C["success"])
        state  = "disabled" if locked else "normal"
        in_bg  = C["bg"]       if locked else C["input_bg"]
        in_fg  = C["dim"]      if locked else C["text"]
        for e in self._cred_entries:
            e.config(state=state,
                     disabledbackground=in_bg, disabledforeground=in_fg)
        for t in self._prompt_widgets.values():
            t.config(state=state, bg=in_bg, fg=in_fg)
        for tog in self._bot_toggles:
            tog.refresh()

    # ── Bot callback ──────────────────────────────────────────────────────────

    def _bot_cb(self, attr, val):
        key_map = {
            "email_bot_var": "email_bot_on",
            "ig_bot_var":    "ig_bot_on",
            "fb_bot_var":    "fb_bot_on",
            "global_ai_var": "global_ai_on",
            "auto_inv_var":  "auto_invoice",
        }
        self.app.settings[key_map.get(attr, attr)] = val
        self.app._maybe_start_bots()

    # ── Save ─────────────────────────────────────────────────────────────────

    def _save(self):
        # Separate secret keys vs setting keys
        secret_keys  = set(cfg_module.DEFAULT_SECRETS.keys())
        setting_keys = set(cfg_module.DEFAULT_SETTINGS.keys())

        for key, var in self._cred_vars.items():
            val = var.get().strip()
            if key in secret_keys:
                self.app.secrets[key] = val
            else:
                self.app.settings[key] = val

        for key, t in self._prompt_widgets.items():
            self.app.settings[key] = t.get("1.0", "end").strip()

        cfg_module.save_secrets(self.app.secrets)
        cfg_module.save_settings(self.app.settings)

        # Rebuild engines with new credentials
        self.app._rebuild_engines()
        messagebox.showinfo("Saved", "Settings saved successfully.")

    # ── Admin-locked Code Editor ──────────────────────────────────────────────

    def _build_code_editor(self, parent):
        hdr = tk.Frame(parent, bg=C["bg"])
        hdr.pack(fill="x", padx=20, pady=(10, 3))
        tk.Label(hdr, text="CODE EDITOR — AI ASSISTANT", bg=C["bg"],
                 fg=C["muted"], font=FONT["label"]).pack(side="left")
        self._code_lock_lbl = tk.Label(hdr, text="🔒 Admin Locked", bg=C["bg"],
                                       fg=C["warn"], font=FONT["tiny"], cursor="hand2")
        self._code_lock_lbl.pack(side="left", padx=(10, 0))
        self._code_lock_lbl.bind("<Button-1>", lambda e: self._toggle_code_lock())

        tk.Label(parent,
                 text="Describe a change in plain English. AI edits the file, backs up first, "
                      "and restarts the app. Requires admin PIN.",
                 bg=C["bg"], fg=C["dim"], font=FONT["tiny"]).pack(anchor="w", padx=24, pady=(0, 6))

        self._code_log = tk.Text(parent, bg=C["log_bg"], fg=C["muted"], font=FONT["mono"],
                                 height=5, relief="flat", state="disabled", wrap="word")
        self._code_log.pack(fill="x", padx=24, pady=(0, 4))

        row = tk.Frame(parent, bg=C["bg"]); row.pack(fill="x", padx=24, pady=(0, 4))
        self._code_input = tk.Entry(row, bg=C["bg"], fg=C["dim"],
                                    insertbackground=C["text"], font=FONT["body"],
                                    relief="flat", state="disabled",
                                    disabledbackground=C["bg"], disabledforeground=C["dim"])
        self._code_input.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        self._code_input.bind("<Return>", lambda e: self._run_code_edit())
        self._send_btn = btn(row, "Send to AI", bg="dim", fg="muted", px=12, py=7)
        self._send_btn.pack(side="right")

        # Which file to edit
        file_row = tk.Frame(parent, bg=C["bg"]); file_row.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(file_row, text="Target file:", bg=C["bg"],
                 fg=C["muted"], font=FONT["tiny"]).pack(side="left")
        self._file_var = tk.StringVar(value="ui/dashboard.py")
        files = [
            "ui/dashboard.py", "ui/messaging.py", "ui/invoices.py",
            "ui/metrics.py", "ui/settings.py", "ui/calendar.py",
            "ui/directory.py", "ui/widgets.py",
            "engine/ai.py", "engine/email_bot.py", "engine/meta_bot.py",
            "config.py", "theme.py", "ui/app.py",
        ]
        tk.OptionMenu(file_row, self._file_var, *files).pack(side="left", padx=8)

    def _toggle_code_lock(self):
        if self._locked.get():
            messagebox.showwarning("Locked", "Unlock settings first.")
            return
        if self._code_locked.get():
            pin = simpledialog.askstring("Admin PIN", "Enter admin PIN:",
                                         show="*",
                                         parent=self._parent.winfo_toplevel())
            if pin != self.app.secrets.get("admin_pin", "1234"):
                messagebox.showerror("Wrong PIN", "Incorrect admin PIN.")
                return
            self._code_locked.set(False)
            self._code_lock_lbl.config(text="🔓 Unlocked", fg=C["success"])
            self._code_input.config(state="normal",
                                    bg=C["input_bg"], fg=C["text"],
                                    disabledbackground=C["input_bg"])
            self._send_btn.config(bg=C["accent"], fg=C["btn_txt"],
                                  cursor="hand2")
            self._send_btn.bind("<Button-1>", lambda e: self._run_code_edit())
        else:
            self._code_locked.set(True)
            self._code_lock_lbl.config(text="🔒 Admin Locked", fg=C["warn"])
            self._code_input.config(state="disabled",
                                    bg=C["bg"], fg=C["dim"])
            self._send_btn.config(bg=C["dim"], fg=C["muted"])
            self._send_btn.unbind("<Button-1>")

    def _code_log_append(self, text):
        self._code_log.config(state="normal")
        self._code_log.insert("end", text + "\n")
        self._code_log.see("end")
        self._code_log.config(state="disabled")

    def _run_code_edit(self):
        if self._code_locked.get():
            return
        instruction = self._code_input.get().strip()
        if not instruction:
            return
        self._code_input.delete(0, "end")
        target_rel  = self._file_var.get()
        base_dir    = os.path.dirname(os.path.dirname(__file__))
        target_path = os.path.join(base_dir, target_rel.replace("/", os.sep))

        if not os.path.exists(target_path):
            self._code_log_append(f"✗ File not found: {target_path}")
            return

        self._code_log_append(f"🤖 Editing {target_rel}…")
        self._code_log_append(f"   Instruction: {instruction}")

        def task():
            # 1. Backup
            backup_path = target_path + ".bak"
            shutil.copy2(target_path, backup_path)
            self._code_log_append(f"✓ Backup saved: {os.path.basename(backup_path)}")
            try:
                # 2. Ask AI
                new_src = self.app.ai.edit_file(target_path, instruction)
                # 3. Write
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(new_src)
                self._code_log_append("✓ File updated. Restarting app…")
                # 4. Restart
                self.app.root.after(1500, self._restart)
            except Exception as ex:
                # Rollback
                shutil.copy2(backup_path, target_path)
                self.app.root.after(0, lambda:
                    self._code_log_append(f"✗ Edit failed — rolled back.\n   {ex}"))

        threading.Thread(target=task, daemon=True).start()

    def _restart(self):
        python = sys.executable
        os.execv(python, [python] + sys.argv)
