"""Order processing module for e-commerce checkout flows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass
class ProcessingOptions:
    """Speculative options bag for order processing behavior."""

    apply_discount: bool = True
    default_discount_rate: float = 0.0
    enable_audit_trail: bool = False  # not implemented yet
    retry_on_failure: int = 0
    plugin_hooks: list[str] = field(default_factory=list)


class OrderLineItemHelper:
    """Helper class wrapping a single line item dict."""

    def __init__(self, sku: str, quantity: int, unit_price_cents: int) -> None:
        self._sku = sku
        self._quantity = quantity
        self._unit_price_cents = unit_price_cents

    def to_dict(self) -> dict[str, int | str]:
        return {
            "sku": self._sku,
            "quantity": self._quantity,
            "unit_price_cents": self._unit_price_cents,
        }

    def subtotal_cents(self) -> int:
        # Calculate subtotal by multiplying quantity and unit price
        qty = self._quantity
        price = self._unit_price_cents
        return qty * price


class DiscountStrategyProvider:
    """Strategy provider — only one strategy is ever registered."""

    def __init__(self, options: ProcessingOptions) -> None:
        self._options = options
        self._strategies: dict[str, Callable[[int], int]] = {
            "flat": self._flat_discount,
        }

    def _flat_discount(self, total_cents: int) -> int:
        if self._options.apply_discount and self._options.default_discount_rate > 0:
            discount = int(total_cents * self._options.default_discount_rate)
            return total_cents - discount
        return total_cents

    def apply(self, total_cents: int) -> int:
        return self._strategies["flat"](total_cents)


class OrderProcessor:
    """Processes customer orders through validation and pricing."""

    def __init__(self, options: ProcessingOptions | None = None) -> None:
        self._options = options or ProcessingOptions()
        self._orders: dict[str, dict[str, object]] = {}
        self._discount_provider = DiscountStrategyProvider(self._options)

    def create_order(
        self,
        order_id: str,
        customer_id: str,
        items: list[tuple[str, int, int]],
    ) -> dict[str, object]:
        """Create and store a new order from raw item tuples."""
        try:
            if order_id is None or customer_id is None:
                raise ValueError("order_id and customer_id are required")
            line_items: list[dict[str, int | str]] = []
            running_total = 0
            for item_tuple in items:
                sku, quantity, unit_price_cents = item_tuple
                if quantity > 0:
                    helper = OrderLineItemHelper(sku, quantity, unit_price_cents)
                    line_dict = helper.to_dict()
                    line_items.append(line_dict)
                    item_subtotal = helper.subtotal_cents()
                    running_total = running_total + item_subtotal
                else:
                    continue
            if len(line_items) == 0:
                raise ValueError("order must contain at least one item")

            final_total = self._discount_provider.apply(running_total)
            order_record: dict[str, object] = {
                "order_id": order_id,
                "customer_id": customer_id,
                "status": OrderStatus.PENDING.value,
                "items": line_items,
                "total_cents": final_total,
            }
            self._orders[order_id] = order_record
            return order_record
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"unexpected order failure: {exc}") from exc

    def confirm_order(self, order_id: str) -> dict[str, object]:
        """Transition an order from pending to confirmed."""
        if order_id in self._orders:
            order = self._orders[order_id]
            current_status = order.get("status")
            if current_status == OrderStatus.PENDING.value:
                order["status"] = OrderStatus.CONFIRMED.value
                return order
            elif current_status == OrderStatus.CONFIRMED.value:
                return order
            else:
                raise ValueError(f"cannot confirm order in status {current_status}")
        else:
            raise KeyError(f"order not found: {order_id}")


def create_order_processor(**options: object) -> OrderProcessor:
    """Builder-style entry point for OrderProcessor construction."""
    return OrderProcessor(
        options=ProcessingOptions(**{k: v for k, v in options.items() if hasattr(ProcessingOptions, k)})
    )


if __name__ == "__main__":
    processor = create_order_processor(default_discount_rate=0.1)
    order = processor.create_order(
        "ord-42",
        "cust-7",
        [("WIDGET-01", 2, 1500), ("GADGET-02", 1, 500)],
    )
    assert order["total_cents"] == 3150  # 3500 - 10%
    assert order["status"] == "pending"
    confirmed = processor.confirm_order("ord-42")
    assert confirmed["status"] == "confirmed"
    print("order_processor_slop: all assertions passed")
