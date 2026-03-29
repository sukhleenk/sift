import logging
import subprocess
import threading
import webbrowser
from pathlib import Path
from typing import Optional

from PIL import Image

from app import db, notifier, pipeline, scheduler
from app.wizard import load_config

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(__file__).parent.parent / "assets"


class SiftTrayApp:
    def __init__(self):
        self.config: dict = load_config() or {}
        self._digest_ready = False
        self._icon: Optional[object] = None

    def run(self):
        import pystray
        db.init_db()

        image = self._load_icon(active=False)
        self._icon = pystray.Icon(
            "sift",
            image,
            "Sift",
            menu=self._build_menu(),
        )
        scheduler.start_scheduler(self.config, run_pipeline_fn=self._trigger_pipeline)
        self._icon.run()

    def _load_icon(self, active: bool) -> Image.Image:
        name = "icon_active.png" if active else "icon.png"
        path = ASSETS_DIR / name
        if path.exists():
            return Image.open(str(path)).convert("RGBA")
        # Fallback: generate a simple colored square
        img = Image.new("RGBA", (64, 64), (80, 80, 200, 255) if not active else (255, 140, 0, 255))
        return img

    def _build_menu(self):
        import pystray

        items = []
        if self._digest_ready:
            items.append(pystray.MenuItem("📬 New Digest Ready", self._open_latest_digest))
        items += [
            pystray.MenuItem("📖 Open Latest Digest", self._open_latest_digest),
            pystray.MenuItem("🔄 Fetch Now", self._fetch_now),
            pystray.MenuItem("⚙️  Preferences", self._open_preferences),
            pystray.MenuItem("📊 Model Info", self._show_model_info),
            pystray.MenuItem("🔕 Pause Until Tomorrow", self._pause_until_tomorrow),
            pystray.MenuItem("❌ Quit", self._quit),
        ]
        return pystray.Menu(*items)

    def _trigger_pipeline(self):
        if pipeline.is_running():
            return
        pipeline.run_pipeline(
            config=self.config,
            on_complete=self._on_pipeline_complete,
            on_error=self._on_pipeline_error,
        )

    def _on_pipeline_complete(self, html_path: str, paper_count: int):
        self._digest_ready = True
        if self._icon:
            self._icon.icon = self._load_icon(active=True)
            self._icon.menu = self._build_menu()
        if self.config.get("notifications_enabled", True):
            notifier.notify_digest_ready(paper_count)

    def _on_pipeline_error(self, exc: Exception):
        logger.error("Pipeline error: %s", exc)

    def _open_latest_digest(self, icon=None, item=None):
        digest = db.get_latest_digest()
        if not digest:
            return
        html_path = digest.get("html_path", "")
        if html_path and Path(html_path).exists():
            webbrowser.open(f"file://{html_path}")
            self._digest_ready = False
            if self._icon:
                self._icon.icon = self._load_icon(active=False)
                self._icon.menu = self._build_menu()

    def _fetch_now(self, icon=None, item=None):
        threading.Thread(target=self._trigger_pipeline, daemon=True).start()

    def _open_preferences(self, icon=None, item=None):
        def _show():
            import tkinter as tk
            from app.preferences import PreferencesWindow
            root = tk.Tk()
            root.withdraw()
            win = PreferencesWindow(self.config, on_save=self._on_prefs_saved)
            win.root = tk.Toplevel(root)
            win._build_ui()
            win.root.protocol("WM_DELETE_WINDOW", lambda: (win.root.destroy(), root.destroy()))
            root.mainloop()
        threading.Thread(target=_show, daemon=True).start()

    def _on_prefs_saved(self, new_config: dict):
        self.config = new_config
        scheduler.stop_scheduler()
        scheduler.start_scheduler(self.config, run_pipeline_fn=self._trigger_pipeline)

    def _show_model_info(self, icon=None, item=None):
        from app.summarizer import get_model_info as sum_info
        from app.embedder import get_model_info as emb_info
        s = sum_info()
        e = emb_info()
        msg = (
            f"Summarization: {s.get('model_name') or 'not loaded'}\n"
            f"Embedding: {e.get('model_name') or 'not loaded'}\n"
            f"RAM: {s.get('memory_mb') or '—'} MB"
        )
        subprocess.run(["notify-send", "Sift — Model Info", msg], check=False)

    def _pause_until_tomorrow(self, icon=None, item=None):
        scheduler.pause_until_tomorrow()

    def _quit(self, icon=None, item=None):
        scheduler.stop_scheduler()
        if self._icon:
            self._icon.stop()


def run_app():
    app = SiftTrayApp()
    app.run()
