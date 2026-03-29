import logging
import sys

logger = logging.getLogger(__name__)


def notify_digest_ready(paper_count: int) -> None:
    title = "Sift"
    body = f"📄 {paper_count} new paper{'s' if paper_count != 1 else ''} ready"
    if sys.platform == "darwin":
        _notify_macos(title, body)
    else:
        _notify_linux(title, body)


def _notify_macos(title: str, body: str) -> None:
    try:
        import subprocess
        script = (
            f'display notification "{body}" with title "{title}" '
            f'sound name "default"'
        )
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception as exc:
        logger.warning("macOS notification failed: %s", exc)


def _notify_linux(title: str, body: str) -> None:
    try:
        import subprocess
        subprocess.run(
            ["notify-send", "-a", "Sift", title, body],
            check=False,
            timeout=5,
        )
    except Exception as exc:
        logger.warning("notify-send failed: %s", exc)
