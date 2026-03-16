from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, HTTPException, Depends

from pydantic import BaseModel

from .assistant_service import run_assistant, chat_history, router, memory
from .auth import get_current_user, create_token

app = FastAPI(title="Context-Aware Assistant API", version="4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class LoginRequest(BaseModel):
    user_id: str


# ── Login ─────────────────────────────

@app.post("/login")
def login(req: LoginRequest):

    token = create_token(req.user_id)

    return {
        "token": token,
        "user_id": req.user_id
    }


# ── Chat ─────────────────────────────

@app.post("/chat")
def chat(
    req: ChatRequest,
    user_id: str = Depends(get_current_user)
):

    if not req.message.strip():
        raise HTTPException(status_code=400)

    result = run_assistant(req.message, user_id)

    return {
        "reply": result
    }



# ── History ─────────────────────────────

@app.get("/history")
def get_history():
    return {"history": chat_history}


@app.delete("/history")
def clear_history():
    chat_history.clear()
    return {"message": "History cleared."}


# ── Reminders ─────────────────────────

@app.get("/reminders")
def get_reminders(
    status: str = None,
    user_id: str = Depends(get_current_user)
):

    reminders = router.get_all_reminders(user_id=user_id, status=status)

    return {"reminders": reminders}


@app.delete("/reminders/{reminder_id}")
def cancel_reminder(
    reminder_id: str,
    user_id: str = Depends(get_current_user)
):

    result = router.cancel_by_id(reminder_id)

    if "error" in result:
        raise HTTPException(status_code=400)

    return result


# ── Memory ─────────────────────────

@app.get("/memory/{memory_type}")
def get_memory(memory_type: str):

    valid = ("general", "preference", "habit")

    if memory_type not in valid:
        raise HTTPException(status_code=400)

    return {"entries": memory.get_all(memory_type)}