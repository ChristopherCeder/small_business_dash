"""
main.py — Entry point for El Hombre Taco Dashboard.
Run: python main.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import tkinter as tk
from ui.app import ElHombreApp

if __name__ == "__main__":
    root = tk.Tk()
    app  = ElHombreApp(root)
    root.mainloop()
