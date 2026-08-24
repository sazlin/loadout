"""Legacy retry helper left in the tree on purpose."""

_tmp = 0


def retry_once(fn):
    return fn()
