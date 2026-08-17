# Davinci eval fixtures

Intentionally over-engineered Python modules used to evaluate the **davinci** code-simplification agent. Each file is syntactically valid, importable, and behaviorally correct; the slop is structural, not functional.

Run self-checks:

```bash
python agents/davinci/evals/files/user_service_slop.py
python agents/davinci/evals/files/order_processor_slop.py
python agents/davinci/evals/files/cache_manager_slop.py
python agents/davinci/evals/files/report_builder_slop.py
```

## `user_service_slop.py` — user registration service

| Smell | Examples in file |
| --- | --- |
| Premature abstraction | `UserRepositoryProtocol` with one impl (`InMemoryUserRepository`); `AbstractUserValidator` with one subclass |
| Unnecessary factory | `UserFactory.create` for a three-field dict; `build_user_service()` wrapper |
| Speculative config | `UserServiceConfig.future_oauth_provider`, unused OAuth TODO |
| Defensive overkill | Broad `try/except` around trusted in-process calls; impossible `KeyError` handler |
| Verbosity / narration | Comments restating the next line (`# Build the user dictionary…`, `# Persist the validated user…`) |
| Redundant variables | `result = saved_user`, `repo = self._repository`, `stored` intermediates |
| Deep nesting | Nested `if`/`else` in `get_user` instead of early return |
| Control-flow sludge | `else: return None` branches after positive checks |

**Expected simplification:** inline factory/validator/repository layers, flatten `get_user`, drop config fields that are never varied, remove narrative comments and defensive catches.

## `order_processor_slop.py` — checkout order processing

| Smell | Examples in file |
| --- | --- |
| Unnecessary helper class | `OrderLineItemHelper` wrapping a plain tuple/dict |
| Strategy / provider pattern | `DiscountStrategyProvider` with a single `"flat"` strategy in a dict |
| Speculative options | `ProcessingOptions.enable_audit_trail`, `plugin_hooks`, unused `retry_on_failure` |
| Factory / builder | `create_order_processor()` delegating to `OrderProcessor` |
| Defensive overkill | `try/except Exception` wrapping trusted logic; redundant `ValueError` re-raise |
| Verbosity / narration | `# Calculate subtotal by multiplying quantity and unit price` |
| Redundant variables | `pre_discount_total`, `adjusted_total`, `updated`, `opts`, `processor` |
| Deep nesting | Nested status checks in `confirm_order` instead of guard clauses |
| Control-flow sludge | `else: continue` in item loop; impossible `None` guard on required str args |

**Expected simplification:** replace helper/strategy/provider with straight-line pricing, collapse options to parameters actually used, flatten `confirm_order` with early returns, remove audit/plugin scaffolding.

## `cache_manager_slop.py` — namespaced in-memory cache

| Smell | Examples in file |
| --- | --- |
| Premature abstraction | `CacheBackendProtocol` + `AbstractCacheBackend` with one impl |
| Unnecessary helper / strategy | `CacheEntryWrapper`; `CacheWriteStrategyProvider` with a single `"direct"` write |
| Speculative config | `enable_metrics`, `future_redis_url`, unused `plugin_hooks` |
| Factory / builder | `build_cache_manager()` wrapper |
| Defensive overkill | Broad `try/except` + impossible `KeyError` handler |
| Deep nesting | Nested `if`/`else` in `get` / `delete` |

**Expected simplification:** plain dict-backed manager, drop unused config, flatten get/invalidate, remove wrappers.

## `report_builder_slop.py` — sales report builder

| Smell | Examples in file |
| --- | --- |
| Premature abstraction | `ReportAggregatorProtocol` / `AbstractReportAggregator` with one impl |
| Strategy / provider | `ReportFormatterProvider` with a single `"summary"` strategy |
| Speculative options | `enable_pdf_export`, `enable_audit_trail`, `plugin_hooks` |
| Passthrough builder | `create_sales_report_builder` only forwards kwargs |
| Defensive / nesting | Broad `except Exception`; deep validation ladders |
| Verbosity | Section banners and narrative comments |

**Expected simplification:** straight-line aggregate + tax math, collapse options to used fields, guard-clause validation.
