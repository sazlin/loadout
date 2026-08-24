# README best practices

Researched from GitHub's README guide and widely cited public READMEs
(uv, FastAPI, Oh My Zsh, ripgrep, othneildrew/Best-README-Template).
Apply these when generating or rewriting `README.md`.

## What a README is for

GitHub treats the root `README.md` as the project's front door. It should
answer, in order:

1. What is this?
2. Why would I use it?
3. How do I try it in the next few minutes?
4. Where do I go next (docs, help, contributing)?
5. Who maintains it, and under what license?

Keep the README as the on-ramp. Put long references in `docs/`, a wiki, or
linked guides **unless the README already is the user manual** (demo + install
matrix + evidence + footguns, typical of CLIs like ripgrep/fd). In that case
keep those sections in the README; fold packager lists into `<details>` if you
must shorten, do not delete them. GitHub truncates rendered READMEs past
500 KiB.

## Section order (decreasing urgency)

Use this spine. Omit a section that has nothing true to say. Do not invent.

| # | Section | Purpose |
| --- | --- | --- |
| 1 | Visual (banner, logo, or demo) | Identity in one glance |
| 2 | Title | Exact project name as an `h1` |
| 3 | Badges | 3–5 trust signals: CI, version, license, runtime |
| 4 | One-sentence pitch | What it is, who it is for, why it is different |
| 5 | Short "why / gist" | Problem and payoff. Scannable bullets beat a paragraph |
| 6 | Quick start | Fewest copy-paste commands to a working result |
| 7 | Core catalog / features | Tables or labeled bullets, not prose walls |
| 8 | Usage / next workflows | Day-two tasks after the happy path |
| 9 | Caveats | Footguns that waste hours if buried |
| 10 | Contributing / local dev | How maintainers work in this repo |
| 11 | License and credits | Legal + provenance |

GitHub already renders an Outline from headings. Do **not** put a table of
contents above the pitch. If the file is long, a short contents list may
follow Quick start.

## Style

- **Show, then tell.** A working command, screenshot, or 10-line example
  beats a feature essay. uv, FastAPI, and ripgrep all lead with something
  you can run or see.
- **Scannable.** Bold lead-ins, numbered steps, tables. One idea per bullet.
- **Copy-paste truth.** Install commands must work on a clean machine.
  Pin the real runner (`uvx`, `uv`, a release tag). Do not assume local state.
- **Second person, present tense.** "Run sync" not "the user should run sync."
- **Relative links** to in-repo files (`LICENSE`, `docs/...`). GitHub rewrites
  them per branch; absolute GitHub URLs rot for clones.
- **Alt text** on images that describes the scene, not "banner."
- **Stable heading names** when other docs or tests deep-link to them.

## Badges

- Place immediately under the title.
- Keep 3–5 high-signal badges: CI status, latest release, language/runtime,
  license. uv-style "how you run this" is useful for a CLI.
- One consistent badge host (Shields.io / GitHub Actions). Same height.
- Drop badges that are always green, always broken, or decorative (star
  counts, "made with love," social follow).

## Tables

Use tables for catalogs (loadouts, flags, recipes) where every row is the
same shape. Link names in backticks so they are searchable. Keep "what you
get" to one line that names distinctive artifacts.

## This repo

- Keep `docs/assets/loadout-banner.jpg` as the opening visual. Do not swap
  it for a badge wall or a generic logo.
- The **Available loadouts** table is generated. Never hand-maintain it.
- Quick start must use `uvx --from git+https://github.com/sazlin/loadout@…`
  so a stranger can run it without cloning this repo first.
- Opinionated voice ("The Gist") is allowed. Do not flatten it into
  corporate boilerplate.
- Warnings that prevent real damage (Superpowers plugin + loadout) stay
  near the top of "later" content, not in an appendix nobody opens.

## Anti-patterns

| Anti-pattern | Why it fails | Do this instead |
| --- | --- | --- |
| Pitch buried under ToC / 15 badges | Reader never learns what the project is | Title, 3–5 badges, one sentence |
| Install before the one-liner | Commands without a reason | Pitch, then three steps |
| Feature dump with no command | Reader must imagine the value | One copy-paste path that works |
| Hand-written artifact catalogs | Drift the day a YAML file changes | Generate from source of truth |
| Walls of undifferentiated prose | Nobody scans it | Bullets, tables, `<details>` for asides |
| Broken or machine-specific install | Immediate distrust | Clean-machine commands; pin versions |
| Absolute `github.com/.../blob/main` links to own files | Wrong on forks and tags | Relative paths |
| "Contributions welcome" with no path | Empty invitation | Point at tests, lint, and the real workflow |
| Screenshots without alt text | Useless when images fail | Describe the image |
| Stale version numbers in prose | Trust decays faster than silence | Badges and tags, not hardcoded versions in sentences |
| Copying this repo's banner into another project | Identity theft, broken path | Only use that project's own visual |
| Flattening a CLI README that already is the manual | Drops demo, install matrix, evidence, footguns | Start from the existing README; fold, don't delete |
| Invented features / loadouts | README lies | Only facts from YAML, code, or tests |

## Sources

- [GitHub: About READMEs](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [uv README](https://github.com/astral-sh/uv) — one-liner, highlights, install that works, then features
- [FastAPI README](https://github.com/fastapi/fastapi) — slogan, labeled benefits, copy-paste example
- [Oh My Zsh README](https://github.com/ohmyzsh/ohmyzsh) — screenshot, install, usage
- [ripgrep README](https://github.com/BurntSushi/ripgrep) — demo, comparison evidence, install matrix
- [Best-README-Template](https://github.com/othneildrew/Best-README-Template) — modular section checklist
