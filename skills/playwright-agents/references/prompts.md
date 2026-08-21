# Prompts

Use these shapes when dispatching the vendored agents. Replace the seed path with the project's seed file.

## Plan

Create a test plan for "add to cart".

- Seed file: `tests/seed.spec.ts`
- Test plan: `specs/add-to-cart.md`

## Generate

Generate tests for the test plan's bullet 1.1 Add item to cart.

Test plan: `specs/add-to-cart.md`

## Heal

Run the failing tests only and fix locator or wait issues in test files. Do not modify production code. If the product is broken, stop and report; do not skip to green.

## Coverage loop

1. Call `playwright_planner` with the plan prompt (one feature).
2. After a human reviews `specs/`, call `playwright_generator` for each bullet **sequentially** (1.1, 1.2, …), not in parallel.
3. Run the new specs.
4. Call `playwright_healer` only on failures, with the heal prompt.
