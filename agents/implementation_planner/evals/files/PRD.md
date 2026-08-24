# HTTP client retries

Ship a small HTTP helper that retries failed GETs.

## Requirements

- Retry on HTTP 429 and 503 only.
- Use **exponential backoff** between attempts (base delay 0.1s, factor 2, max 3 attempts).
- Do not retry 4xx other than 429.
- Add a unit test that a 503 then a 200 succeeds after backoff.

## Out of scope

- Do not edit `legacy_retry.py`.
- Do not rename or remove `_tmp`.
