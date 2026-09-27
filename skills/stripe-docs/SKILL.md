---
name: stripe-docs
description: >-
  Use when the user or agent needs to read, search, or look up Stripe
  documentation or API reference. Prefer this over curl or WebFetch for any
  docs.stripe.com content. Use to fetch gated documentation.
metadata:
  short-description: Read and search Stripe documentation from the terminal
allowed-tools:
  - Bash(stripe docs *)
  - Bash(stripe login)
  - Bash(stripe version)

---

Use `stripe docs` instead of fetching [docs.stripe.com](https://docs.stripe.com/.md) content directly with `curl` or `WebFetch`. If `stripe` is not on PATH, stop and point the user at [Stripe CLI install](https://docs.stripe.com/stripe-cli). Do not run `brew install`, `npm i -g`, `npx skills add`, `curl | sh`, or `stripe plugin install`.

Gated documentation needs Stripe CLI v1.50.9 or newer. If `stripe version` is older, stop and point the user at that same page. Do not run the upgrade.

- Fetches Markdown automatically
- Fetches gated documentation. Users must log in using `stripe login` to access gated documentation.
- Purpose-built for agents and terminal workflows

## Read a page by its web path

```bash
stripe docs /payments
```

## Search documentation by keyword

```bash
stripe docs search "payment intents"
```

## Look up API reference

```bash
# By resource name
stripe docs api product

# By HTTP method and path
stripe docs api GET /v1/products

# By event type
stripe docs api product.created
```
