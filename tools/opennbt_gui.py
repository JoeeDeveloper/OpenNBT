#!/usr/bin/env python3
"""OpenNBT GUI (tkinter, stdlib only). Wraps the read-only probe. Run: python tools/opennbt_gui.py

'Demo mode' talks to a built-in fake gateway on this computer, so you can try it without a car.
"""
import queue
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_capture as ac  # noqa: E402
import fake_gateway as fg  # noqa: E402
import hsfz_probe as hp  # noqa: E402

CAPTURES = Path(__file__).resolve().parent.parent / ".local" / "captures"


def recon_plan():
    return [(ecu, bytes.fromhex(did)) for ecu, did in hp.RECON_PLAN]


def idscan_plan():
    return [(ecu, bytes.fromhex(did)) for ecu, did in hp.IDSCAN_PLAN]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OpenNBT - read-only recon")
        self.q = queue.Queue()
        self.gw, self.local = tk.StringVar(), tk.StringVar()
        self.parked, self.demo = tk.BooleanVar(), tk.BooleanVar()
        f = ttk.Frame(self, padding=8)
        f.pack(fill="x")
        ttk.Label(f, text="Gateway IP").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.gw, width=18).grid(row=0, column=1)
        ttk.Label(f, text="Laptop IP (169.254.x.x)").grid(row=0, column=2, padx=(12, 0))
        ttk.Entry(f, textvariable=self.local, width=18).grid(row=0, column=3)
        ttk.Checkbutton(f, text="Parked, handbrake on, ignition on, engine off", variable=self.parked).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=4)
        ttk.Checkbutton(f, text="Demo mode (fake gateway, no car)", variable=self.demo).grid(
            row=2, column=0, columnspan=4, sticky="w")
        self.btn = ttk.Button(f, text="Run recon (12 read-only requests)", command=lambda: self.start(recon_plan))
        self.btn.grid(row=3, column=0, columnspan=2, pady=6, sticky="w")
        self.btn2 = ttk.Button(f, text="Run idscan (12 read-only requests)", command=lambda: self.start(idscan_plan))
        self.btn2.grid(row=4, column=0, columnspan=2, pady=(0, 6), sticky="w")
        self.status = ttk.Label(f, text="Idle")
        self.status.grid(row=4, column=2, columnspan=2, sticky="w")
        cols = ("ecu", "request", "result", "text")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=14)
        for c, w in zip(cols, (60, 90, 260, 300)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w)
        self.tree.pack(fill="both", expand=True, padx=8)
        self.summary = tk.Text(self, height=10, wrap="none")
        self.summary.pack(fill="both", expand=True, padx=8, pady=8)
        self.after(100, self.poll)

    def start(self, plan_fn):
        if not self.parked.get():
            self.status.config(text="Tick the parked/handbrake box first")
            return
        self.tree.delete(*self.tree.get_children())
        self.summary.delete("1.0", "end")
        self.btn.state(["disabled"])
        self.btn2.state(["disabled"])
        self.status.config(text="Running...")
        threading.Thread(target=self.work,
                         args=(plan_fn, self.gw.get().strip(), self.local.get().strip(), self.demo.get()),
                         daemon=True).start()

    def work(self, plan_fn, gw, local, demo):
        stop = None
        try:
            port = hp.HSFZ_PORT
            if demo:
                port, stop = fg.start()
                gw, local = "127.0.0.1", ""
            else:
                gw = hp.link_local(gw)
                local = hp.link_local(local) if local else ""
            out = hp.run_requests(plan_fn(), gw, local, CAPTURES, port=port, on_row=lambda r: self.q.put(("row", r)))
            self.q.put(("done", out))
        except Exception as e:  # shown to the user, not swallowed
            self.q.put(("fail", "%s: %s" % (type(e).__name__, e)))
        finally:
            if stop:
                stop()

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "row":
                    self.tree.insert("", "end", values=(val["ecu"], val["request"], ac.classify(val), val.get("ascii", val.get("data", ""))))
                elif kind == "done":
                    self.status.config(text="Saved %s" % val)
                    self.summary.insert("1.0", ac.summarize(ac.load_rows(val)))
                    self.btn.state(["!disabled"])
                    self.btn2.state(["!disabled"])
                else:
                    self.status.config(text="Failed: %s" % val)
                    self.btn.state(["!disabled"])
                    self.btn2.state(["!disabled"])
        except queue.Empty:
            pass
        self.after(100, self.poll)


if __name__ == "__main__":
    App().mainloop()
