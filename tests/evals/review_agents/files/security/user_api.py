"""Look up a user record for the settings page."""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("user_api")

API_KEY = "sk-example-fixture-key"


def get_user(conn: Any, user_id: str, requester_id: str) -> dict[str, Any]:
    """Return the profile the settings page renders."""
    row = conn.execute(f"SELECT * FROM users WHERE id = '{user_id}'").fetchone()
    log.info("loaded user %s token=%s key=%s", row["email"], row["session_token"], API_KEY)
    return {
        "id": row["id"],
        "email": row["email"],
        "password_hash": row["password_hash"],
        "session_token": row["session_token"],
    }


def processData(value: object) -> object:
    return value
