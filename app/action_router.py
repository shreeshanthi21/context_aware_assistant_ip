"""
action_router.py — ActionRouter class with APScheduler + SQLite persistence.

Drop-in replacement for the original. Same public interface:
    ActionRouter.handle_action(intent, message) → dict
    ActionRouter.cancel_by_id(reminder_id)      → dict
    ActionRouter.get_all_reminders(status=None) → list[dict]

Uses parse_time() and extract_task() from the existing time_parser.py.
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
from .time_parser import parse_time, extract_task   # ← actual function names

logger = logging.getLogger(__name__)

# ── APScheduler SQLite jobstore path ──────────────────────────────────────────
_HERE         = Path(__file__).resolve().parent   # app/
_PROJECT_ROOT = _HERE.parent                      # project root
_DATA_DIR     = _PROJECT_ROOT / "data"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_APSCHED_URL  = f"sqlite:///{_DATA_DIR / 'apscheduler_jobs.db'}"

# ── Single shared scheduler instance ──────────────────────────────────────────
_scheduler = BackgroundScheduler(
    jobstores    = {"default": SQLAlchemyJobStore(url=_APSCHED_URL)},
    executors    = {"default": ThreadPoolExecutor(max_workers=10)},
    job_defaults = {
        "coalesce":           True,
        "max_instances":      1,
        "misfire_grace_time": 3600,  # fire up to 1 h late → survives short downtime
    },
    timezone="UTC",
)


def _reminder_callback(reminder_id: str, message: str) -> None:
    """Called by APScheduler when the reminder time arrives."""
    logger.info("🔔 REMINDER FIRED [%s]: %s", reminder_id, message)
    mark_fired(reminder_id)


def _on_job_event(event) -> None:
    if event.exception:
        logger.error("❌ Job %s failed: %s", event.job_id, event.exception)
    else:
        logger.info("✅ Job %s completed", event.job_id)


_scheduler.add_listener(_on_job_event, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)


# ── Startup / shutdown (called from api.py lifespan) ──────────────────────────

def start_scheduler() -> None:
    """Initialise DB, start APScheduler, reload any pending reminders."""
    init_db()
    if not _scheduler.running:
        _scheduler.start()
        logger.info("🚀 APScheduler started — jobstore: %s", _APSCHED_URL)
    _reload_pending_reminders()


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("🛑 APScheduler stopped")


def _reload_pending_reminders() -> None:
    """
    On startup, re-register any SQLite pending reminders whose APScheduler
    job was lost (e.g. apscheduler_jobs.db deleted or server hard-killed).
    """
    pending  = get_pending_reminders_db()
    reloaded = 0
    for rem in pending:
        jid = rem["id"]
        if _scheduler.get_job(jid):
            continue  # already in APScheduler jobstore — skip
        trigger_at = datetime.fromisoformat(rem["trigger_at"])
        _scheduler.add_job(
            _reminder_callback,
            trigger        = "date",
            run_date       = trigger_at,
            args           = [jid, rem["message"]],
            id             = jid,
            replace_existing = True,
        )
        reloaded += 1
        logger.info("♻️  Reloaded reminder %s → %s", jid, trigger_at)
    logger.info("ℹ️  %d pending reminder(s) reloaded on startup", reloaded)


# ── ActionRouter ──────────────────────────────────────────────────────────────

class ActionRouter:
    """Reminder CRUD — same interface as the original, now backed by SQLite."""

    def handle_action(self, intent: str, message: str) -> dict:
        if intent == "set_reminder":
            return self._set_reminder(message)
        elif intent == "cancel_reminder":
            return self._cancel_latest()
        elif intent == "list_reminders":
            return self._list_reminders()
        return {"reply": "I didn't understand that action."}

    # ── Set ───────────────────────────────────────────────────────────────────

    def _set_reminder(self, message: str) -> dict:
        trigger_at = parse_time(message)      # returns datetime or None
        if not trigger_at:
            return {
                "reply": (
                    "I couldn't figure out when to remind you. "
                    "Try: 'remind me in 30 minutes to call John'"
                )
            }

        clean_msg   = extract_task(message)   # strip time phrases from message
        reminder_id = str(uuid.uuid4())

        # 1 — Persist to SQLite FIRST (crash-safe)
        save_reminder(reminder_id, clean_msg, trigger_at)

        # 2 — Schedule with APScheduler
        _scheduler.add_job(
            _reminder_callback,
            trigger          = "date",
            run_date         = trigger_at,
            args             = [reminder_id, clean_msg],
            id               = reminder_id,
            replace_existing = True,
        )

        logger.info("➕ Reminder [%s] '%s' @ %s", reminder_id, clean_msg, trigger_at)

        # strftime format: use %I on Windows, %-I on Mac/Linux
        try:
            friendly = trigger_at.strftime("%-I:%M %p")
        except ValueError:
            friendly = trigger_at.strftime("%I:%M %p").lstrip("0")

        return {
            "reply":       f"✅ Reminder set for {friendly}: \"{clean_msg}\"",
            "reminder_id": reminder_id,
            "trigger_at":  trigger_at.isoformat(),
        }

    # ── Cancel latest ─────────────────────────────────────────────────────────

    def cancel_latest(self) -> dict:
        pending = get_all_reminders_db(status="pending")
        if not pending:
            return {"reply": "You have no pending reminders to cancel."}
        return self.cancel_by_id(pending[0]["id"])

    def _cancel_latest(self) -> dict:
        pending = get_all_reminders_db(status="pending")
        if not pending:
            return {"reply": "You have no pending reminders to cancel."}
        return self.cancel_by_id(pending[0]["id"])

    # ── List ──────────────────────────────────────────────────────────────────

    def _list_reminders(self) -> dict:
        pending = get_all_reminders_db(status="pending")
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

    # ── Cancel by ID (called from api.py DELETE /reminders/{id}) ─────────────

    def cancel_by_id(self, reminder_id: str) -> dict:
        job = _scheduler.get_job(reminder_id)
        if job:
            job.remove()
        updated = mark_cancelled(reminder_id)
        if updated:
            return {"reply": "🗑️ Reminder cancelled.", "cancelled_id": reminder_id}
        return {"error": f"Reminder '{reminder_id}' not found or already completed."}

    # ── Get all (called from api.py GET /reminders) ───────────────────────────

    def get_all_reminders(self, status: Optional[str] = None) -> list[dict]:
        return get_all_reminders_db(status=status)