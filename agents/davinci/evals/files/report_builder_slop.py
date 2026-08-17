"""Sales report builder module for summarizing line-item revenue."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol


# ---------------------------------------------------------------------------
# Configuration & speculative options
# ---------------------------------------------------------------------------


@dataclass
class ReportBuilderOptions:
    """Speculative options bag for report generation behavior."""

    default_tax_rate: float = 0.0
    enable_pdf_export: bool = False  # not wired up yet
    enable_audit_trail: bool = False  # reserved for future compliance hooks
    plugin_hooks: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Abstract base / Protocol with a single concrete implementation
# ---------------------------------------------------------------------------


class ReportAggregatorProtocol(Protocol):
    """Protocol describing how line items are aggregated into totals."""

    def aggregate(self, rows: list[tuple[str, int, int]]) -> dict[str, object]: ...


class AbstractReportAggregator(ABC):
    """Base aggregator for sales row payloads."""

    @abstractmethod
    def aggregate(self, rows: list[tuple[str, int, int]]) -> dict[str, object]:
        raise NotImplementedError


class DefaultSalesAggregator(AbstractReportAggregator):
    """Concrete aggregator — the only implementation we ship today."""

    def aggregate(self, rows: list[tuple[str, int, int]]) -> dict[str, object]:
        # Walk each row and accumulate quantity and revenue in cents
        line_count = 0
        total_qty = 0
        subtotal_cents = 0
        for row in rows:
            sku, qty, price_cents = row
            line_count = line_count + 1
            total_qty = total_qty + qty
            line_revenue = qty * price_cents
            subtotal_cents = subtotal_cents + line_revenue
        result: dict[str, object] = {
            "line_count": line_count,
            "total_qty": total_qty,
            "subtotal_cents": subtotal_cents,
        }
        return result


# ---------------------------------------------------------------------------
# Strategy / Provider with a single format strategy
# ---------------------------------------------------------------------------


class ReportFormatterStrategy:
    """Formats aggregated totals into a final report dict."""

    def format(
        self,
        aggregates: dict[str, object],
        tax_rate: float,
    ) -> dict[str, object]:
        # Apply tax and assemble the canonical report shape
        subtotal = int(aggregates["subtotal_cents"])  # type: ignore[arg-type]
        tax_amount = int(subtotal * tax_rate)
        grand_total = subtotal + tax_amount
        formatted: dict[str, object] = {
            "line_count": aggregates["line_count"],
            "total_qty": aggregates["total_qty"],
            "subtotal_cents": subtotal,
            "tax_rate": tax_rate,
            "tax_cents": tax_amount,
            "total_cents": grand_total,
        }
        return formatted


class ReportFormatterProvider:
    """Strategy provider — only one format strategy is ever registered."""

    def __init__(self) -> None:
        self._strategies: dict[str, ReportFormatterStrategy] = {
            "summary": ReportFormatterStrategy(),
        }

    def get(self, name: str = "summary") -> ReportFormatterStrategy:
        return self._strategies[name]


# ---------------------------------------------------------------------------
# Core builder service
# ---------------------------------------------------------------------------


class SalesReportBuilder:
    """Builds a simple sales summary report from SKU/qty/price rows."""

    def __init__(self, options: ReportBuilderOptions | None = None) -> None:
        self._options = options or ReportBuilderOptions()
        self._aggregator: AbstractReportAggregator = DefaultSalesAggregator()
        self._formatter_provider = ReportFormatterProvider()

    def build(
        self,
        rows: list[tuple[str, int, int]],
        tax_rate: float | None = None,
    ) -> dict[str, object]:
        """Validate rows and produce a summary report dictionary."""
        try:
            if rows is not None:
                if len(rows) > 0:
                    effective_tax = (
                        tax_rate if tax_rate is not None else self._options.default_tax_rate
                    )
                    if effective_tax >= 0:
                        aggregates = self._aggregator.aggregate(rows)
                        formatter = self._formatter_provider.get("summary")
                        report = formatter.format(aggregates, effective_tax)
                        return report
                    else:
                        raise ValueError("tax_rate must be non-negative")
                else:
                    raise ValueError("rows must contain at least one line item")
            else:
                raise ValueError("rows are required")
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"unexpected report build failure: {exc}") from exc


def create_sales_report_builder(**options: object) -> SalesReportBuilder:
    """Builder-style entry point that only forwards to the constructor."""
    filtered = {k: v for k, v in options.items() if hasattr(ReportBuilderOptions, k)}
    return SalesReportBuilder(options=ReportBuilderOptions(**filtered))


if __name__ == "__main__":
    builder = create_sales_report_builder(
        default_tax_rate=0.1,
        enable_pdf_export=True,
        enable_audit_trail=True,
        plugin_hooks=["noop"],
    )
    report = builder.build(
        [("SKU-A", 2, 1000), ("SKU-B", 1, 500)],
        tax_rate=0.1,
    )
    assert report["line_count"] == 2
    assert report["total_qty"] == 3
    assert report["subtotal_cents"] == 2500
    assert report["tax_cents"] == 250
    assert report["total_cents"] == 2750
    assert report["tax_rate"] == 0.1

    untaxed = builder.build([("SKU-C", 4, 250)])
    assert untaxed["subtotal_cents"] == 1000
    assert untaxed["tax_cents"] == 100  # default_tax_rate=0.1
    assert untaxed["total_cents"] == 1100

    print("report_builder_slop: all assertions passed")
