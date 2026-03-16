"""
Central orchestrator.

Flow
────
1. Detect intent
2. If reminder → ActionRouter
3. If preference → extract + save to memory + acknowledge
4. If habit → extract + save to memory
5. If recall → pull memory → LLM answers using it
6. General chat → pull relevant memory → LLM
"""

from .intent import IntentDetector
from .llm_engine import LLMEngine
from .context_builder import ContextBuilder
from .action_router import ActionRouter
from .memory import MemoryManager
from .memory_extractor import extract_preference, extract_habit
from .habit_suggester import suggest_from_habits

# ── Core singletons ─────────────────────────────────────────
detector = IntentDetector()
llm = LLMEngine()
memory = MemoryManager()
router = ActionRouter()

chat_history: list[str] = []
MAX_HISTORY = 8

_surfaced_suggestions: set[str] = set()


# ── Main entry point ─────────────────────────────────────────

def run_assistant(msg: str, user_id: str = "default") -> dict:

    intent = detector.detect_intent(msg)
    print(f"[Assistant] Intent: {intent}")

    action = None
    reply = ""
    memory_saved = None
    proactive_suggestion = None

    # Build user-specific context
    context = ContextBuilder(memory)

    # ── Reminder intents ─────────────────────────
    if intent in ("set_reminder", "cancel_reminder", "list_reminders"):

        action = router.handle_action(intent, msg, user_id)

        reply = action.get(
            "reply", "Sorry, something went wrong."
        )

    # ── Save positive preference ─────────────────
    elif intent == "save_preference_positive":

        clean = extract_preference(msg, sentiment="positive")

        saved = memory.save_preference(user_id, clean, sentiment="positive")
        memory_saved = {
            "type": "preference",
            "text": clean,
            "sentiment": "positive",
            "stored": saved,
        }

        reply = f"Got it! I'll remember that. ✓\n\"{clean}\""

    # ── Save negative preference ─────────────────
    elif intent == "save_preference_negative":

        clean = extract_preference(msg, sentiment="negative")

        saved = memory.save_preference(clean, sentiment="negative")

        memory_saved = {
            "type": "preference",
            "text": clean,
            "sentiment": "negative",
            "stored": saved,
        }

        reply = f"Noted — I'll keep that in mind. ✓\n\"{clean}\""

    # ── Save habit ─────────────────────────
    elif intent == "save_habit":

        clean, time_hint = extract_habit(msg)

        saved = memory.save_habit(user_id, clean, time_hint=time_hint)

        memory_saved = {
            "type": "habit",
            "text": clean,
            "time_hint": time_hint,
            "stored": saved,
        }

        reply = f"Got it, I've noted your routine. ✓\n\"{clean}\""

        if time_hint:
            proactive_suggestion = {
                "activity": clean,
                "time_hint": time_hint,
                "message": f"Want me to set a daily reminder at {time_hint}?",
            }

    # ── Recall memory ─────────────────────────
    elif intent == "recall_memory":

        ctx = context.get_context(msg, intent)

        h_txt = "\n".join(chat_history[-MAX_HISTORY:])

        full = "\n\n".join(filter(None, [h_txt, ctx]))

        reply = llm.generate_response(msg, intent, full or None)

    # ── General chat ─────────────────────────
    else:

        ctx = context.get_context(msg, intent)

        h_txt = "\n".join(chat_history[-MAX_HISTORY:])

        full = "\n\n".join(filter(None, [h_txt, ctx]))

        reply = llm.generate_response(msg, intent, full or None)

    # ── Habit suggestions ─────────────────────────
    if not proactive_suggestion:

        habits = memory.retrieve_habits(user_id)
        
        suggestions = suggest_from_habits(habits)

        for s in suggestions:

            key = s["time_hint"]

            if key not in _surfaced_suggestions:

                _surfaced_suggestions.add(key)

                proactive_suggestion = {
                    "activity": s["activity"],
                    "time_hint": s["time_hint"],
                    "message": s["suggestion"],
                }

                break

    # ── Save conversation history ─────────────────────────

    chat_history.append(f"User: {msg}")
    chat_history.append(f"Assistant: {reply}")

    if len(chat_history) > MAX_HISTORY * 2:

        chat_history[:] = chat_history[-(MAX_HISTORY * 2):]

    return {
        "reply": reply,
        "intent": intent,
        "system": action,
        "memory_saved": memory_saved,
        "proactive_suggestion": proactive_suggestion,
    }