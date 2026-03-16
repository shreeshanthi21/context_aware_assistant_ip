"""
auth.py
Temporary lightweight auth system for multi-user support.
"""

from fastapi import Header


def get_current_user(x_user_id: str | None = Header(default=None)):
    """
    Reads user ID from header.
    If missing, defaults to 'ridhu' so the frontend works immediately.
    """

    if not x_user_id:
        return "ridhu"

    return x_user_id


def create_token(user_id: str) -> dict:
    """
    Temporary token generator.
    """
    return {
        "user_id": user_id,
        "token": f"user-{user_id}"
    }