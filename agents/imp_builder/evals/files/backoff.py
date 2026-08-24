"""HTTP retry helper. Implement exponential backoff here."""

_tmp_unused = True


def retry_get(call, *, attempts: int = 3):
    """Return the first successful payload. Currently a single call."""
    return call()
