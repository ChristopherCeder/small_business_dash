"""
ui/directory.py — Customer Directory tab.
Auto-updated when invoices move to Paid. CSV import/export.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from theme import C, FONT
from ui.widgets import btn


class CustomerEditPopup(tk.Toplevel):
    def __init__(self, parent, customer: dict, on_save):
        super().__init__(parent)
        self.title("Edit Customer")
        self.configure(bg=C["bg"])
        self.geometry("460x480")
        self.resizable(False, True)
        self.grab_set()
        self.customer = customer
        self.on_save  = on_save
        self.vars     = {}

        tk.Label(self, text=customer.get("name", "Customer"), bg=C["bg"],
                 fg=C["text"], font=FONT["h3"]).pack(padx=20, pady=(16, 6), anchor="w")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x")

        from ui.widgets import ScrollFrame
        sf   = ScrollFrame(self, bg=C["bg"])
        sf.pack(fill="both", expand=True)
        form = sf.inner

        for label, key in [
            ("Name",          "name"),
            ("Email",         "email"),
            ("Phone",         "phone"),
            ("Source",        "source"),
            ("Last Contact",  "last_contact"),
            ("Total Spent",   "total_spent"),
            ("Last Event",    "event_type"),
            ("Notes",         "notes"),
        ]:
            tk.Label(form, text=label, bg=C["bg"], fg=C["muted"],
                     font=FONT["label"]).pack(anchor="w", padx=20, pady=(8, 1))
            var = tk.StringVar(value=customer.get(key, ""))
            self.vars[key] = var
            f = tk.Frame(form, bg=C["input_border"], padx=1, pady=1)
            f.pack(fill="x", padx=20)
            tk.Entry(f, textvariable=var, bg=C["input_bg"], fg=C["text"],
                     insertbackground=C["text"], relief="flat",
                     font=FONT["body"]).pack(fill="x", ipady=7)

        btn_row = tk.Frame(self, bg=C["bg"])
        btn_row.pack(fill="x", padx=20, pady=12, side="bottom")
        tk.Frame(self, bg=C["border"], height=1).pack(fill="x", side="bottom")
        btn(btn_row, "Save Changes", bg="success",
            command=self._save).pack(side="left", padx=(0, 8))
        btn(btn_row, "Cancel", bg="border", fg="text",
            command=self.destroy).pack(side="left")

    def _save(self):
        self.on_save({k: v.get().strip() for k, v in self.vars.items()})
        self.destroy()


class DirectoryTab:
    def __init__(self, app):
        self.app = app

    def build(self, parent: tk.Frame):
        self._parent = parent

        top = tk.Frame(parent, bg=C["bg"])
        top.pack(fill="x", padx=20, pady=14)
        tk.Label(top, text="Customer Directory", bg=C["bg"],
                 fg=C["text"], font=FONT["h2"]).pack(side="left")
        for label, cmd in [("Import CSV", self._import_csv),
                            ("Export CSV", self._export_csv)]:
            btn(top, label, bg="border", fg="text",
                command=cmd, px=12, py=5).pack(side="right", padx=4)

        # Search bar
        sr = tk.Frame(parent, bg=C["bg"])
        sr.pack(fill="x", padx=20, pady=(0, 8))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._refresh())
        e = tk.Entry(sr, textvariable=self._search_var,
                     bg=C["input_bg"], fg=C["text"], font=FONT["body"],
                     relief="flat", insertbackground=C["text"])
        e.pack(fill="x", ipady=8, padx=1)
        e.insert(0, "Search customers…")
        e.bind("<FocusIn>",  lambda ev: e.delete(0, "end") if e.get() == "Search customers…" else None)
        e.bind("<FocusOut>", lambda ev: e.insert(0, "Search customers…") if not e.get() else None)

        # Treeview
        style = ttk.Style()
        style.configure("Dir.Treeview",
                        background=C["panel"], foreground=C["text"],
                        rowheight=32, fieldbackground=C["panel"],
                        font=("Helvetica", 9))
        style.configure("Dir.Treeview.Heading",
                        background=C["bg"], foreground=C["muted"],
                        font=("Helvetica", 8, "bold"), relief="flat")
        style.map("Dir.Treeview", background=[("selected", C["accent"])])

        frame = tk.Frame(parent, bg=C["bg"])
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        self._tree = ttk.Treeview(frame, style="Dir.Treeview", selectmode="browse")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._tree.pack(fill="both", expand=True)
        self._tree.bind("<Double-1>", self._on_double_click)

        self._refresh()

    def _on_double_click(self, event):
        item = self._tree.focus()
        if not item:
            return
        vals   = self._tree.item(item, "values")
        if not vals:
            return
        # Find matching customer by name+email
        name  = vals[0] if len(vals) > 0 else ""
        email = vals[1] if len(vals) > 1 else ""
        cust  = next(
            (c for c in self.app.state.get("customers", [])
             if c.get("name") == name and c.get("email") == email),
            None,
        )
        if not cust:
            return
        def save(data):
            cust.update(data)
            self.app.save()
            self._refresh()
        CustomerEditPopup(self._parent.winfo_toplevel(), cust, save)

    def _refresh(self):
        if not hasattr(self, "_tree"):
            return
        cols = ["Name", "Email", "Phone", "Source", "Last Contact",
                "Total Spent", "Last Event", "Notes"]
        self._tree["columns"] = cols
        self._tree["show"]    = "headings"
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=130, minwidth=80)
        for row in self._tree.get_children():
            self._tree.delete(row)

        q = self._search_var.get().lower().strip()
        if q in ("", "search customers…"):
            q = ""

        key_map = {
            "Name": "name", "Email": "email", "Phone": "phone",
            "Source": "source", "Last Contact": "last_contact",
            "Total Spent": "total_spent", "Last Event": "event_type", "Notes": "notes",
        }
        for cust in self.app.state.get("customers", []):
            if q and not any(q in str(cust.get(v, "")).lower() for v in key_map.values()):
                continue
            self._tree.insert("", "end",
                              values=[cust.get(key_map[c], "") for c in cols])

    def update_from_invoice(self, inv: dict):
        """Called when an invoice moves to Paid. Upserts the customer record."""
        customers = self.app.state.setdefault("customers", [])
        email     = inv.get("email", "").lower().strip()
        existing  = next((c for c in customers
                          if c.get("email", "").lower() == email), None) if email else None
        amt = 0.0
        try:
            amt = float(inv.get("amount", "0").replace("$", "").replace(",", ""))
        except Exception:
            pass

        now_str = datetime.now().strftime("%Y-%m-%d")

        if existing:
            # Accumulate spend
            try:
                prev = float(str(existing.get("total_spent", "0")).replace("$", "").replace(",", ""))
            except Exception:
                prev = 0.0
            existing["total_spent"]   = f"${prev + amt:,.2f}"
            existing["last_contact"]  = now_str
            existing["event_type"]    = inv.get("event", existing.get("event_type", ""))
            # Update phone/email if new data is richer
            if inv.get("phone") and not existing.get("phone"):
                existing["phone"] = inv["phone"]
            if inv.get("name") and not existing.get("name"):
                existing["name"] = inv["name"]
        else:
            customers.append({
                "name":         inv.get("name", ""),
                "email":        inv.get("email", ""),
                "phone":        inv.get("phone", ""),
                "source":       inv.get("source", "script"),
                "last_contact": now_str,
                "total_spent":  f"${amt:,.2f}",
                "event_type":   inv.get("event", ""),
                "notes":        "",
            })
        self.app.save()
        self._refresh()

    def _import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if not path:
            return
        import csv
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self.app.state.setdefault("customers", []).append(
                    {k.lower().replace(" ", "_"): v for k, v in row.items()})
        self._refresh()
        messagebox.showinfo("Imported", f"Imported from {path}")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        import csv
        cols = ["name", "email", "phone", "source", "last_contact",
                "total_spent", "event_type", "notes"]
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(self.app.state.get("customers", []))
        messagebox.showinfo("Exported", f"Saved to {path}")

    def refresh(self):
        self._refresh()
