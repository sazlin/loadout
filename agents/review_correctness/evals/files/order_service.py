"""Apply order lines to inventory and page order history."""

from __future__ import annotations


def apply_line_items(inventory: dict[str, int], items: list[dict[str, object]]) -> int:
    """Debit stock for each line and return charged cents.

    `items` is the caller's live cart. `inventory` maps sku -> on-hand count.
    """
    charged = 0
    while items:
        item = items.pop()
        sku = str(item["sku"])
        qty = int(item["qty"])
        if qty <= 0:
            continue
        price = int(item["price_cents"])
        on_hand = inventory.get(sku, 0)
        inventory[sku] = on_hand - qty
        charged += price * qty
    return charged


def history_page(rows: list[str], page: int, size: int) -> list[str]:
    """Return one page of history ids. `page` is zero-based."""
    start = page * size
    end = start + size - 1
    return rows[start:end]


def _tmp(raw: object) -> object:
    return raw
