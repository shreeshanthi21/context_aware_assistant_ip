
"""
action_router.py — ActionRouter class with APScheduler + SQLite persistence.

Multi-user version (user_id support)

Public interface:
    ActionRouter.handle_action(intent, message, user_id) → dict
    ActionRouter.cancel_by_id(reminder_id)               → dict
    ActionRouter.get_all_reminders(user_id, status=None) → list[dict]
"""

import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from .database import (
    init_db,
    save_reminder,
    mark_fired,
    mark_cancelled,
    get_all_reminders_db,
    get_pending_reminders_db,
)

from .time_parser import parse_time, extract_task

logger = logging.getLogger(__name__)

# ── APScheduler SQLite jobstore path ──────────────────────────────────────────

_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_APSCHED_URL = f"sqlite:///{_DATA_DIR / 'apscheduler_jobs.db'}"

# ── Scheduler configuration ───────────────────────────────────────────────────

_scheduler = BackgroundScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=_APSCHED_URL)},
    executors={"default": ThreadPoolExecutor(max_workers=10)},
    job_defaults={
        "coalesce": True,
        "max_instances": 1,
        "misfire_grace_time": 3600,
    },
    timezone="UTC",
)

# ── Reminder callback ─────────────────────────────────────────────────────────

def _reminder_callback(reminder_id: str, message: str):
    logger.info("🔔 REMINDER FIRED [%s]: %s", reminder_id, message)
    mark_fired(reminder_id)

# ── Scheduler event logging ───────────────────────────────────────────────────

def _on_job_event(event):
    if event.exception:
        logger.error("❌ Job %s failed: %s", event.job_id, event.exception)
    else:
        logger.info("✅ Job %s completed")

_scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

# ── Scheduler lifecycle ───────────────────────────────────────────────────────

def start_scheduler():
    init_db()

    if not _scheduler.running:
        _scheduler.start()
        logger.info("🚀 APScheduler started — jobstore: %s", _APSCHED_URL)

    _reload_pending_reminders()


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 APScheduler stopped")

# ── Reload pending reminders on startup ───────────────────────────────────────

def _reload_pending_reminders():

    pending = get_pending_reminders_db()
    reloaded = 0

    for rem in pending:

        jid = rem["id"]

        if _scheduler.get_job(jid):
            continue

        trigger_at = datetime.fromisoformat(rem["trigger_at"])

        _scheduler.add_job(
            _reminder_callback,
            trigger="date",
            run_date=trigger_at,
            args=[jid, rem["message"]],
            id=jid,
            replace_existing=True,
        )

        reloaded += 1

        logger.info("♻️ Reloaded reminder %s → %s", jid, trigger_at)

    logger.info("ℹ️ %d pending reminder(s) reloaded", reloaded)

# ── Action Router ─────────────────────────────────────────────────────────────

class ActionRouter:

    def handle_action(self, intent: str, message: str, user_id: str) -> dict:

        if intent == "set_reminder":
            return self._set_reminder(message, user_id)

        elif intent == "cancel_reminder":
            return self._cancel_latest(user_id)

        elif intent == "list_reminders":
            return self._list_reminders(user_id)

        return {"reply": "I didn't understand that action."}

    # ── Create reminder ───────────────────────────────────────────────────────

    def _set_reminder(self, message: str, user_id: str):

        trigger_at = parse_time(message)

        if not trigger_at:
            return {
                "reply": "I couldn't figure out when to remind you. Try: 'remind me in 30 minutes to call John'"
            }

        clean_msg = extract_task(message)

        reminder_id = str(uuid.uuid4())

        save_reminder(reminder_id, user_id, clean_msg, trigger_at)

        _scheduler.add_job(
            _reminder_callback,
            trigger="date",
            run_date=trigger_at,
            args=[reminder_id, clean_msg],
            id=reminder_id,
            replace_existing=True,
        )

        try:
            friendly = trigger_at.strftime("%-I:%M %p")
        except ValueError:
            friendly = trigger_at.strftime("%I:%M %p").lstrip("0")

        return {
            "reply": f"✅ Reminder set for {friendly}: \"{clean_msg}\"",
            "reminder_id": reminder_id,
            "trigger_at": trigger_at.isoformat(),
        }

    # ── Cancel latest reminder ───────────────────────────────────────────────

    def _cancel_latest(self, user_id: str):

        pending = get_all_reminders_db(user_id=user_id, status="pending")

        if not pending:
            return {"reply": "You have no pending reminders to cancel."}

        return self.cancel_by_id(pending[0]["id"])

    # ── List reminders ───────────────────────────────────────────────────────

    def _list_reminders(self, user_id: str):

        pending = get_all_reminders_db(user_id=user_id, status="pending")

        if not pending:
            return {"reply": "You have no pending reminders."}

        lines = []

        for r in pending:

            dt = datetime.fromisoformat(r["trigger_at"])

            try:
                t_str = dt.strftime("%-I:%M %p")
            except ValueError:
                t_str = dt.strftime("%I:%M %p").lstrip("0")

            lines.append(f"• {t_str} — {r['message']}")

        return {"reply": "📋 Your pending reminders:\n" + "\n".join(lines)}

    # ── Cancel by ID ─────────────────────────────────────────────────────────

    def cancel_by_id(self, reminder_id: str):

        job = _scheduler.get_job(reminder_id)

        if job:
            job.remove()

        updated = mark_cancelled(reminder_id)

        if updated:
            return {"reply": "🗑️ Reminder cancelled.", "cancelled_id": reminder_id}

        return {"error": f"Reminder '{reminder_id}' not found or already completed."}

    # ── Get reminders ────────────────────────────────────────────────────────

    def get_all_reminders(self, user_id: str, status: Optional[str] = None):

        return get_all_reminders_db(user_id=user_id, status=status)

