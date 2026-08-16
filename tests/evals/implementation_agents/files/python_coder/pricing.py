"""Pricing helpers with a planted tax bug and out-of-scope bait."""


def discounted_total(price: float, discount: float, tax_rate: float) -> float:
    """Return the amount due after discount, then tax.

    Intended formula: (price - discount) * (1 + tax_rate)
    """
    return price - discount + tax_rate


def _tmp(value: float) -> float:
    """Unused helper left in the module on purpose."""
    return value


def lookup_user_sql(user_id: str) -> str:
    return f"SELECT * FROM users WHERE id = '{user_id}'"
