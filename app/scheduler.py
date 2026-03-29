import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler(
    config: dict,
    run_pipeline_fn: Callable,
) -> None:
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)

    _scheduler = BackgroundScheduler(daemon=True)

    frequency: str = config.get("digest_frequency", "once_daily")
    hour_morning: int = config.get("digest_hour_morning", 8)
    hour_evening: int = config.get("digest_hour_evening", 18)

    _scheduler.add_job(
        func=run_pipeline_fn,
        trigger=CronTrigger(hour=hour_morning, minute=0),
        id="morning_digest",
        replace_existing=True,
        misfire_grace_time=300,
    )
    logger.info("Scheduled morning digest at %02d:00", hour_morning)

    if frequency == "twice_daily":
        _scheduler.add_job(
            func=run_pipeline_fn,
            trigger=CronTrigger(hour=hour_evening, minute=0),
            id="evening_digest",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Scheduled evening digest at %02d:00", hour_evening)

    _scheduler.start()
    logger.info("Scheduler started.")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def pause_until_tomorrow() -> None:
    if _scheduler is None:
        return
    from datetime import datetime, timedelta
    tomorrow = (datetime.now() + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    for job in _scheduler.get_jobs():
        job.pause()
    _scheduler.add_job(
        func=_resume_all_jobs,
        trigger="date",
        run_date=tomorrow,
        id="resume_after_pause",
        replace_existing=True,
    )
    logger.info("All jobs paused until tomorrow (%s)", tomorrow.isoformat())


def _resume_all_jobs() -> None:
    if _scheduler is None:
        return
    for job in _scheduler.get_jobs():
        if job.id != "resume_after_pause":
            job.resume()
    logger.info("Jobs resumed after pause.")
