import logging
import sys
from pathlib import Path

from platformdirs import user_log_dir

APP_NAME = "sift"


def _setup_logging():
    log_dir = Path(user_log_dir(APP_NAME))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "sift.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_file), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    _setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Sift starting up.")

    from app.wizard import is_first_run, run_wizard
    if is_first_run():
        logger.info("First run detected — launching setup wizard.")
        config = run_wizard()
        if config is None:
            logger.info("Wizard cancelled — exiting.")
            sys.exit(0)
        logger.info("Wizard completed. Config saved.")

    if sys.platform == "darwin":
        try:
            import rumps  # noqa: F401
            from app.menubar import run_app
            logger.info("Starting macOS menu bar app.")
            run_app()
        except ImportError:
            logger.warning("rumps not available — falling back to Tkinter tray.")
            _run_tkinter_fallback()
    else:
        try:
            import pystray  # noqa: F401
            from app.tray_linux import run_app
            logger.info("Starting Linux system tray app.")
            run_app()
        except ImportError:
            logger.warning("pystray not available — falling back to CLI mode.")
            _run_cli_mode()


def _run_tkinter_fallback():
    import tkinter as tk
    from app import db, pipeline
    from app.wizard import load_config

    db.init_db()
    config = load_config() or {}

    root = tk.Tk()
    root.title("Sift")
    root.geometry("320x180")

    import tkinter.ttk as ttk
    tk.Label(root, text="Sift — Research Digest", font=("system", 16, "bold"), pady=16).pack()
    status = tk.Label(root, text="Ready", fg="#555")
    status.pack()

    def fetch():
        if pipeline.is_running():
            status.config(text="Digest in progress…")
            return
        status.config(text="Fetching…")
        pipeline.run_pipeline(
            config=config,
            on_complete=lambda p, n: status.config(text=f"Done — {n} papers"),
            on_error=lambda e: status.config(text=f"Error: {e}"),
        )

    ttk.Button(root, text="Fetch Now", command=fetch).pack(pady=8)
    ttk.Button(root, text="Quit", command=root.destroy).pack()
    root.mainloop()


def _run_cli_mode():
    from app import db, pipeline
    from app.wizard import load_config
    import time

    db.init_db()
    config = load_config() or {}
    print("Sift CLI mode — running pipeline once.")

    done = [False]

    def on_complete(html_path, count):
        print(f"Done. {count} papers. Digest: {html_path}")
        done[0] = True

    def on_error(exc):
        print(f"Error: {exc}", file=sys.stderr)
        done[0] = True

    pipeline.run_pipeline(config, on_complete=on_complete, on_error=on_error)
    while not done[0]:
        time.sleep(1)


if __name__ == "__main__":
    main()
