import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Callable, Optional

import yaml

from app.hardware import SUPPORTED_EMBEDDING_MODELS, SUPPORTED_SUMMARIZATION_MODELS
from app.wizard import get_config_path, _center_window, _download_models


class PreferencesWindow:
    def __init__(self, config: dict, on_save: Optional[Callable[[dict], None]] = None):
        self.config = dict(config)
        self.on_save = on_save
        self.root: Optional[tk.Toplevel | tk.Tk] = None

    def show(self):
        if self.root and self.root.winfo_exists():
            self.root.lift()
            return

        self.root = tk.Toplevel()
        self.root.title("Sift — Preferences")
        self.root.resizable(False, False)
        _center_window(self.root, 580, 620)
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

    def _build_ui(self):
        root = self.root
        body = tk.Frame(root, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        _section(body, "Topics")
        self._topics_list = tk.Listbox(body, height=5, width=55)
        for t in self.config.get("topics", []):
            self._topics_list.insert("end", t)
        self._topics_list.pack(anchor="w")

        topics_btn_frame = tk.Frame(body)
        topics_btn_frame.pack(anchor="w", pady=(4, 0))
        self._topic_entry = ttk.Entry(topics_btn_frame, width=38)
        self._topic_entry.pack(side="left", padx=(0, 6))
        ttk.Button(topics_btn_frame, text="Add", command=self._add_topic).pack(side="left", padx=(0, 4))
        ttk.Button(topics_btn_frame, text="Remove", command=self._remove_topic).pack(side="left")

        _section(body, "Digest Schedule")
        self._freq_var = tk.StringVar(value=self.config.get("digest_frequency", "once_daily"))
        frq_frame = tk.Frame(body)
        frq_frame.pack(anchor="w")
        ttk.Radiobutton(
            frq_frame, text="Once daily", value="once_daily", variable=self._freq_var
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            frq_frame, text="Twice daily", value="twice_daily", variable=self._freq_var
        ).pack(side="left")

        time_frame = tk.Frame(body)
        time_frame.pack(anchor="w", pady=(6, 0))
        tk.Label(time_frame, text="Morning hour:").pack(side="left")
        self._morning_var = tk.IntVar(value=self.config.get("digest_hour_morning", 8))
        ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self._morning_var, width=4).pack(
            side="left", padx=(4, 16)
        )
        tk.Label(time_frame, text="Evening hour:").pack(side="left")
        self._evening_var = tk.IntVar(value=self.config.get("digest_hour_evening", 18))
        ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self._evening_var, width=4).pack(
            side="left", padx=(4, 0)
        )

        _section(body, "Max Papers Per Digest")
        slider_frame = tk.Frame(body)
        slider_frame.pack(anchor="w", fill="x")
        self._max_papers_var = tk.IntVar(value=self.config.get("max_papers", 10))
        self._max_label = tk.Label(
            slider_frame, text=str(self.config.get("max_papers", 10)),
            width=3, font=("system", 12, "bold"),
        )
        self._max_label.pack(side="right")
        ttk.Scale(
            slider_frame, from_=5, to=30, orient="horizontal",
            variable=self._max_papers_var,
            command=lambda v: self._max_label.config(text=str(int(float(v)))),
            length=280,
        ).pack(side="left")

        _section(body, "Summarization Model")
        self._sum_var = tk.StringVar(value=self.config.get("summarization_model", ""))
        sum_combo = ttk.Combobox(
            body, textvariable=self._sum_var,
            values=SUPPORTED_SUMMARIZATION_MODELS, state="readonly", width=45,
        )
        sum_combo.pack(anchor="w")

        _section(body, "Embedding Model")
        self._emb_var = tk.StringVar(value=self.config.get("embedding_model", ""))
        emb_combo = ttk.Combobox(
            body, textvariable=self._emb_var,
            values=SUPPORTED_EMBEDDING_MODELS, state="readonly", width=30,
        )
        emb_combo.pack(anchor="w")

        _section(body, "Digest History Retention (days)")
        self._retention_var = tk.IntVar(value=self.config.get("digest_retention_days", 30))
        ttk.Spinbox(body, from_=1, to=365, textvariable=self._retention_var, width=6).pack(anchor="w")

        _section(body, "Notifications")
        self._notif_var = tk.BooleanVar(value=self.config.get("notifications_enabled", True))
        ttk.Checkbutton(
            body, text="Show system notification on digest completion",
            variable=self._notif_var,
        ).pack(anchor="w")

        btn_frame = tk.Frame(root, pady=12, padx=24)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="right", padx=(8, 0))
        ttk.Button(btn_frame, text="Cancel", command=root.destroy).pack(side="right")

    def _add_topic(self):
        topic = self._topic_entry.get().strip()
        if topic:
            self._topics_list.insert("end", topic)
            self._topic_entry.delete(0, "end")

    def _remove_topic(self):
        sel = self._topics_list.curselection()
        if sel:
            self._topics_list.delete(sel[0])

    def _on_save(self):
        topics = list(self._topics_list.get(0, "end"))
        if not topics:
            messagebox.showerror("Sift", "Add at least one topic.")
            return

        new_sum = self._sum_var.get()
        new_emb = self._emb_var.get()
        model_changed = (
            new_sum != self.config.get("summarization_model") or
            new_emb != self.config.get("embedding_model")
        )

        updated = dict(self.config)
        updated.update({
            "topics": topics,
            "digest_frequency": self._freq_var.get(),
            "digest_hour_morning": int(self._morning_var.get()),
            "digest_hour_evening": int(self._evening_var.get()),
            "max_papers": int(self._max_papers_var.get()),
            "summarization_model": new_sum,
            "embedding_model": new_emb,
            "digest_retention_days": int(self._retention_var.get()),
            "notifications_enabled": bool(self._notif_var.get()),
        })

        path = get_config_path()
        with open(path, "w") as f:
            yaml.safe_dump(updated, f, default_flow_style=False)

        if model_changed:
            self._trigger_model_download(updated)
            return

        if self.on_save:
            self.on_save(updated)
        self.root.destroy()

    def _trigger_model_download(self, config: dict):
        import threading
        self._on_save_btn_disabled = True
        progress_win = tk.Toplevel(self.root)
        progress_win.title("Downloading Models")
        _center_window(progress_win, 400, 120)
        tk.Label(progress_win, text="Downloading new models…", pady=16).pack()
        pb = ttk.Progressbar(progress_win, mode="indeterminate", length=340)
        pb.pack()
        pb.start(10)

        def download():
            try:
                _download_models(config["summarization_model"], config["embedding_model"])
                progress_win.after(0, lambda: _finish_download(None))
            except Exception as exc:
                progress_win.after(0, lambda: _finish_download(exc))

        def _finish_download(exc):
            pb.stop()
            progress_win.destroy()
            if exc:
                messagebox.showerror("Sift", f"Model download failed: {exc}")
                return
            if self.on_save:
                self.on_save(config)
            self.root.destroy()

        threading.Thread(target=download, daemon=True).start()


def _section(parent, text: str):
    tk.Label(parent, text=text, font=("system", 12, "bold")).pack(anchor="w", pady=(12, 2))
