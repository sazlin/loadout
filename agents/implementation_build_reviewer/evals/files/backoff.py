"""Retry helper. Delays are linear, not exponential."""

import time

_tmp = 0


def retry_get(call, *, attempts: int = 3):
    last = None
    for _ in range(attempts):
        last = call()
        if last is not None:
            return last
        time.sleep(1)
    return last
