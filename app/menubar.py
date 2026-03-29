import logging
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import rumps

from app import db, notifier, pipeline, scheduler
from app.wizard import load_config

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent.parent / "assets"


class SiftMenuBarApp(rumps.App):
    def __init__(self):
        self.config: dict = load_config() or {}

        icon_path = str(ASSETS_DIR / "icon.png")
        super().__init__(
            name="Sift",
            icon=icon_path,
            quit_button=None,  # We add our own
        )

        self._icon_default = icon_path
        self._icon_active = str(ASSETS_DIR / "icon_active.png")
        self._digest_ready = False

        self._build_menu()
        self._start_scheduler()

    def _build_menu(self):
        self._new_digest_item = rumps.MenuItem(
            "📬 New Digest Ready",
            callback=self._open_latest_digest,
        )
        self._new_digest_item.hide()

        self.menu = [
            self._new_digest_item,
            rumps.MenuItem("📖 Open Latest Digest", callback=self._open_latest_digest),
            rumps.MenuItem("📋 Digest History", callback=self._show_history),
            None,  # separator
            rumps.MenuItem("🔄 Fetch Now", callback=self._fetch_now),
            rumps.MenuItem("⚙️  Preferences", callback=self._open_preferences),
            rumps.MenuItem("📊 Model Info", callback=self._show_model_info),
            None,
            rumps.MenuItem("🔕 Pause Until Tomorrow", callback=self._pause_until_tomorrow),
            rumps.MenuItem("❌ Quit", callback=self._quit),
        ]

    def _start_scheduler(self):
        scheduler.start_scheduler(self.config, run_pipeline_fn=self._trigger_pipeline)

    def _trigger_pipeline(self):
        if pipeline.is_running():
            logger.info("Pipeline already running, skipping scheduled trigger.")
            return
        pipeline.run_pipeline(
            config=self.config,
            on_complete=self._on_pipeline_complete,
            on_error=self._on_pipeline_error,
        )
        self._update_fetch_label("Digest in progress…")

    def _on_pipeline_complete(self, html_path: str, paper_count: int):
        logger.info("Pipeline complete: %d papers, %s", paper_count, html_path)
        self._digest_ready = True

        def _ui_update():
            self.icon = self._icon_active
            self._new_digest_item.show()
            self._update_fetch_label("🔄 Fetch Now")

        rumps.rumps._app.callOnMainThread_(_ui_update) if hasattr(rumps.rumps, "_app") else None
        threading.Timer(0, _ui_update).start()

        if self.config.get("notifications_enabled", True):
            notifier.notify_digest_ready(paper_count)

    def _on_pipeline_error(self, exc: Exception):
        logger.error("Pipeline error: %s", exc)
        self._update_fetch_label("🔄 Fetch Now")

    def _update_fetch_label(self, label: str):
        try:
            fetch_item = self.menu["🔄 Fetch Now"]
            if fetch_item:
                fetch_item.title = label
        except Exception:
            pass

    @rumps.clicked("📖 Open Latest Digest")
    def _open_latest_digest(self, _=None):
        digest = db.get_latest_digest()
        if not digest:
            rumps.alert("Sift", "No digest generated yet. Use 'Fetch Now' to generate one.")
            return
        html_path = digest.get("html_path", "")
        if html_path and Path(html_path).exists():
            self._open_html(html_path)
            self._mark_digest_opened()
        else:
            rumps.alert("Sift", "Digest file not found.")

    @rumps.clicked("📋 Digest History")
    def _show_history(self, _=None):
        digests = db.get_all_digests()
        if not digests:
            rumps.alert("Sift", "No digest history yet.")
            return

        history_menu = rumps.Window(
            title="Digest History",
            message="\n".join(
                f"• {d['generated_at'][:16]}  —  {d['paper_count']} papers"
                for d in digests[:15]
            ),
            ok="Close",
        )
        history_menu.run()

    @rumps.clicked("🔄 Fetch Now")
    def _fetch_now(self, _=None):
        if pipeline.is_running():
            rumps.alert("Sift", "A digest is already being generated.")
            return
        self._trigger_pipeline()

    @rumps.clicked("⚙️  Preferences")
    def _open_preferences(self, _=None):
        def _show():
            from app.preferences import PreferencesWindow
            win = PreferencesWindow(self.config, on_save=self._on_prefs_saved)
            win.show()
            import tkinter as tk
            try:
                win.root.mainloop()
            except Exception:
                pass

        threading.Thread(target=_show, daemon=True).start()

    def _on_prefs_saved(self, new_config: dict):
        self.config = new_config
        scheduler.stop_scheduler()
        self._start_scheduler()

    @rumps.clicked("📊 Model Info")
    def _show_model_info(self, _=None):
        from app.summarizer import get_model_info as sum_info
        from app.embedder import get_model_info as emb_info
        s = sum_info()
        e = emb_info()
        digest = db.get_latest_digest()
        last_gen = digest["generated_at"][:16] if digest else "never"
        last_count = digest["paper_count"] if digest else 0

        lines = [
            f"Summarization model: {s.get('model_name') or 'not loaded'}",
            f"  Parameters: {s.get('parameters') or '—'}",
            f"Embedding model: {e.get('model_name') or 'not loaded'}",
            f"  Process RAM: {s.get('memory_mb') or '—'} MB",
            "",
            f"Last digest: {last_gen}  ({last_count} papers)",
        ]
        rumps.alert("Model Info", "\n".join(lines))

    @rumps.clicked("🔕 Pause Until Tomorrow")
    def _pause_until_tomorrow(self, _=None):
        scheduler.pause_until_tomorrow()
        rumps.alert("Sift", "Digest generation paused until tomorrow.")

    @rumps.clicked("❌ Quit")
    def _quit(self, _=None):
        scheduler.stop_scheduler()
        rumps.quit_application()

    def _open_html(self, path: str):
        if sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            webbrowser.open(f"file://{path}")

    def _mark_digest_opened(self):
        self._digest_ready = False
        self.icon = self._icon_default
        try:
            self._new_digest_item.hide()
        except Exception:
            pass


def run_app():
    db.init_db()
    app = SiftMenuBarApp()
    app.run()
