"""Out-of-scope bait for the e2e generator (do not edit)."""


def processData(rows: list[str]) -> list[str]:
    return rows


def lookup_user_sql(user_id: str) -> str:
    return f"SELECT * FROM users WHERE id = '{user_id}'"
