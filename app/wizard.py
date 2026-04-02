import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from typing import Optional

import yaml
from platformdirs import user_config_dir

from app.hardware import (
    SUPPORTED_EMBEDDING_MODELS,
    SUPPORTED_SUMMARIZATION_MODELS,
    HardwareProfile,
    ModelRecommendation,
    detect_hardware,
    human_readable_profile,
    recommend_models,
)

APP_NAME = "sift"


def get_config_path() -> Path:
    cfg_dir = Path(user_config_dir(APP_NAME))
    cfg_dir.mkdir(parents=True, exist_ok=True)
    return cfg_dir / "config.yaml"


def run_wizard() -> Optional[dict]:
    profile = detect_hardware()
    recommendation = recommend_models(profile)
    result: dict = {}

    root = tk.Tk()
    root.title("Sift — Setup")
    root.resizable(False, False)

    _WizardWindow(root, profile, recommendation, result)

    root.mainloop()

    if result.get("completed"):
        return result["config"]
    return None


class _WizardWindow:
    def __init__(
        self,
        root: tk.Tk,
        profile: HardwareProfile,
        recommendation: ModelRecommendation,
        result: dict,
    ):
        self.root = root
        self.profile = profile
        self.recommendation = recommendation
        self.result = result

        self._build_ui()
        root.protocol("WM_DELETE_WINDOW", self._on_cancel)
        _center_window(root, 640, 680)

    def _build_ui(self):
        root = self.root
        pad = {"padx": 20, "pady": 8}

        header = tk.Frame(root, bg="#1d1d1f", pady=16)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Welcome to Sift",
            font=("system", 22, "bold"),
            bg="#1d1d1f",
            fg="white",
        ).pack()
        tk.Label(
            header,
            text="Local ArXiv research digest — no cloud required",
            font=("system", 13),
            bg="#1d1d1f",
            fg="#a1a1a6",
        ).pack()

        body = tk.Frame(root, padx=24, pady=16)
        body.pack(fill="both", expand=True)

        _section(body, "Detected Hardware")
        tk.Label(
            body,
            text=human_readable_profile(self.profile),
            font=("system", 12),
            wraplength=570,
            justify="left",
        ).pack(anchor="w", pady=(0, 4))

        _section(body, "Summarization Model")
        tk.Label(
            body,
            text=f"Recommended: {self.recommendation.summarization_model}\n{self.recommendation.reason}",
            font=("system", 11),
            fg="#555",
            wraplength=570,
            justify="left",
        ).pack(anchor="w")
        self._sum_var = tk.StringVar(value=self.recommendation.summarization_model)
        sum_combo = ttk.Combobox(
            body,
            textvariable=self._sum_var,
            values=SUPPORTED_SUMMARIZATION_MODELS,
            state="readonly",
            width=45,
        )
        sum_combo.pack(anchor="w", pady=(4, 0))

        _section(body, "Embedding Model")
        self._emb_var = tk.StringVar(value=self.recommendation.embedding_model)
        emb_combo = ttk.Combobox(
            body,
            textvariable=self._emb_var,
            values=SUPPORTED_EMBEDDING_MODELS,
            state="readonly",
            width=30,
        )
        emb_combo.pack(anchor="w")

        _section(body, "ArXiv Topics  (comma-separated)")
        self._topics_var = tk.StringVar(
            value="prompt injection, vision language models, diffusion models"
        )
        topics_entry = ttk.Entry(body, textvariable=self._topics_var, width=60)
        topics_entry.pack(anchor="w", pady=(4, 0))
        tk.Label(
            body,
            text='e.g. "RAG systems, multimodal reasoning, protein folding"',
            font=("system", 10),
            fg="#888",
        ).pack(anchor="w")

        _section(body, "Digest Frequency")
        self._freq_var = tk.StringVar(value="once_daily")
        frq_frame = tk.Frame(body)
        frq_frame.pack(anchor="w")
        ttk.Radiobutton(
            frq_frame,
            text="Once daily (8 AM)",
            value="once_daily",
            variable=self._freq_var,
        ).pack(side="left", padx=(0, 16))
        ttk.Radiobutton(
            frq_frame,
            text="Twice daily (8 AM & 6 PM)",
            value="twice_daily",
            variable=self._freq_var,
        ).pack(side="left")

        _section(body, "Max Papers Per Digest")
        slider_frame = tk.Frame(body)
        slider_frame.pack(anchor="w", fill="x")
        self._max_papers_var = tk.IntVar(value=10)
        self._max_label = tk.Label(
            slider_frame, text="10", width=3, font=("system", 12, "bold")
        )
        self._max_label.pack(side="right")
        slider = ttk.Scale(
            slider_frame,
            from_=5,
            to=30,
            orient="horizontal",
            variable=self._max_papers_var,
            command=lambda v: self._max_label.config(text=str(int(float(v)))),
            length=300,
        )
        slider.pack(side="left")

        self._progress_frame = tk.Frame(body)
        self._progress_frame.pack(fill="x", pady=(8, 0))
        self._progress_label = tk.Label(
            self._progress_frame, text="", font=("system", 11)
        )
        self._progress_label.pack(anchor="w")
        self._progress = ttk.Progressbar(
            self._progress_frame, mode="indeterminate", length=580
        )

        btn_frame = tk.Frame(root, pady=12, padx=24)
        btn_frame.pack(fill="x")
        self._start_btn = ttk.Button(
            btn_frame, text="Download Models & Start", command=self._on_start
        )
        self._start_btn.pack(side="right", padx=(8, 0))
        ttk.Button(btn_frame, text="Cancel", command=self._on_cancel).pack(side="right")

    def _on_start(self):
        topics_raw = self._topics_var.get().strip()
        if not topics_raw:
            messagebox.showerror("Sift", "Please enter at least one ArXiv topic.")
            return

        topics = [t.strip() for t in topics_raw.split(",") if t.strip()]
        config = {
            "topics": topics,
            "digest_frequency": self._freq_var.get(),
            "max_papers": int(self._max_papers_var.get()),
            "summarization_model": self._sum_var.get(),
            "embedding_model": self._emb_var.get(),
            "digest_hour_morning": 8,
            "digest_hour_evening": 18,
            "digest_retention_days": 30,
            "notifications_enabled": True,
            "hours_back": 24,
        }

        self._start_btn.config(state="disabled")
        self._progress_label.config(
            text="Downloading models… this may take a few minutes."
        )
        self._progress.pack(fill="x")
        self._progress.start(10)

        def download():
            try:
                _download_models(
                    config["summarization_model"], config["embedding_model"]
                )
                self.root.after(0, lambda: self._finish(config))
            except Exception as exc:
                self.root.after(0, lambda: self._on_download_error(exc))

        threading.Thread(target=download, daemon=True).start()

    def _finish(self, config: dict):
        self._progress.stop()
        _save_config(config)
        self.result["completed"] = True
        self.result["config"] = config
        self.root.destroy()

    def _on_download_error(self, exc: Exception):
        self._progress.stop()
        self._start_btn.config(state="normal")
        self._progress_label.config(text="")
        messagebox.showerror("Sift — Download Error", str(exc))

    def _on_cancel(self):
        self.result["completed"] = False
        self.root.destroy()


def _section(parent, text: str):
    tk.Label(parent, text=text, font=("system", 12, "bold")).pack(
        anchor="w", pady=(14, 2)
    )


def _center_window(root: tk.Tk, w: int, h: int):
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    w = max(w, root.winfo_reqwidth())
    h = max(h, root.winfo_reqheight())
    x = (sw - w) // 2
    y = (sh - h) // 2
    root.geometry(f"{w}x{h}+{x}+{y}")


def _download_models(sum_model: str, emb_model: str) -> None:
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
    from sentence_transformers import SentenceTransformer

    AutoTokenizer.from_pretrained(sum_model)
    AutoModelForSeq2SeqLM.from_pretrained(sum_model)
    SentenceTransformer(emb_model)


def _save_config(config: dict) -> None:
    path = get_config_path()
    with open(path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False)


def load_config() -> Optional[dict]:
    path = get_config_path()
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def is_first_run() -> bool:
    return not get_config_path().exists()
