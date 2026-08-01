"""Background scheduler for periodic jobs."""

import atexit
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from config import CLEANUP_INTERVAL_HOURS
from jobs.cleanup import run_cleanup

_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        run_cleanup,
        "interval",
        hours=CLEANUP_INTERVAL_HOURS,
        id="daily_cleanup",
        replace_existing=True,
    )
    _scheduler.start()
    atexit.register(lambda: _scheduler.shutdown(wait=False))
    print(f"Background scheduler started (cleanup every {CLEANUP_INTERVAL_HOURS}h)")
    return _scheduler


def start_scheduler_in_thread():
    """Non-blocking scheduler start for FastAPI lifespan."""
    t = threading.Thread(target=start_scheduler, daemon=True)
    t.start()
