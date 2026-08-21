---
name: github-upload-media-to-pr
description: >-
  Use when asked to attach screenshots, images, recordings, or videos to a
  GitHub pull request; when putting visual evidence, test results, before/after
  images, or a demo video in a PR description or comment; or when phrases like
  "put the screenshot in the PR", "show the recording in the PR", "add images
  to PR", "embed screenshots", "attach UI screenshots", or "upload recording
  to PR" appear. Supports png, jpg, jpeg, gif, webp, mp4, webm, and mov.
license: MIT
compatibility: >-
  Cursor Cloud agents with ManagePullRequest. Do not install agent-browser or
  other npm browser CLIs.
metadata:
  upstream: https://github.com/jacobmassey/github-upload-media-to-pr
---

# Upload Media to PR

Attach local images and videos to a GitHub pull request from a **Cursor Cloud**
agent. Capture UI with Cursor Cloud tools; attach with `ManagePullRequest`.

**Core principle:** Copy media to `/opt/cursor/artifacts/`, then reference those
absolute paths in HTML. Do not drive github.com in a browser and do not install
`agent-browser`.

## When to use

- User wants screenshots, recordings, or other media on a PR
- Walkthrough evidence should appear in the PR body or a comment

**Skip** for attaching files that are not images or videos, and skip installing
third-party browser CLIs to "make upload work".

## Cursor Cloud mapping

Upstream used `agent-browser` (vercel-labs) to click GitHub's hidden file input.
This vendored copy replaces that stack:

| Job | Cursor Cloud tool |
| --- | --- |
| Capture a UI screenshot | `computerUse` subagent (browser/desktop) |
| Capture a short demo video | `RecordScreen` (`START_RECORDING` / `SAVE_RECORDING`) |
| Host and embed on the PR | `ManagePullRequest` with HTML `img` / `video` tags |

`gh` is **read-only** in Cursor Cloud. Never `gh pr edit`, `gh pr comment`, or
`gh pr create`. Use `ManagePullRequest`.

## Step 0: Resolve the PR and collect files

If the user did not give a PR number or URL:

```bash
gh pr view --json number,url -q '"\(.number) \(.url)"'
```

Normalize each file to an absolute path. If the name has special characters,
copy it to a simple name first.

```bash
file --mime-type /path/to/media
```

**Images:** png, jpg, jpeg, gif, webp. **Videos:** mp4, webm, mov.

## Step 1: Stage under `/opt/cursor/artifacts/`

```bash
mkdir -p /opt/cursor/artifacts
cp /absolute/path/to/media.png /opt/cursor/artifacts/pr-screenshot.png
cp /absolute/path/to/demo.mp4 /opt/cursor/artifacts/pr-demo.mp4
```

Use unique, descriptive basenames. The attach tool only rewrites **absolute**
paths under that directory.

## Step 2: Embed with HTML, not GitHub markdown upload URLs

Images:

```html
<img alt="Settings page after the change" src="/opt/cursor/artifacts/pr-screenshot.png" />
```

Videos (include `controls`):

```html
<video src="/opt/cursor/artifacts/pr-demo.mp4" controls></video>
```

Do not wrap the video in a markdown image tag. Do not invent
`https://github.com/user-attachments/assets/...` URLs.

## Step 3: Attach via ManagePullRequest

**Option A — PR description** (default unless the user asks for a comment):

Call `ManagePullRequest` `update_pr` and append a `## Screenshots`, `## Demo`,
or `## Media` section that contains the HTML tags. Keep any human-edited PR
body text. Pass `branch_name` for this branch.

**Option B — Comment** (when the user asks for a comment, or wants comment
links):

Call `ManagePullRequest` `post_comment` with the same HTML in `body`. Provide
only `body` for a top-level conversation comment.

The tool uploads the files and rewrites the paths to hosted URLs. Do not paste
repo-relative paths or `file://` URLs.

## Step 4: Verify

```bash
gh pr view --json body,url
gh api repos/{owner}/{repo}/issues/{number}/comments --jq '.[].html_url'
```

Confirm the returned body or comment contains hosted media URLs, not the
`/opt/cursor/artifacts/` staging path.

## Capturing media you do not already have

- **Screenshot of an app:** `computerUse` against the running UI, save the
  image, then Stage (Step 1).
- **Demo video of an app:** `RecordScreen` start, exercise the UI, save, then
  Stage. Do not record a GitHub tab to "upload" anything.
- **Already-on-disk files:** skip capture; start at Step 1.

## Do not

| Temptation | Why it fails |
| --- | --- |
| `npx skills add vercel-labs/agent-browser -g -y` | Unpinned remote install; supply-chain RCE |
| `npm i -g agent-browser && agent-browser install` | Same: unpinned global binary |
| `agent-browser open` / `upload` / `eval` on github.com | Needs a headed GitHub login; not the Cloud attach path |
| `gh pr edit` / `gh pr comment` | Writes are blocked; use `ManagePullRequest` |
| Click "Paste, drop, or click to add files" in a Cloud browser | OS file picker cannot be automated; skip GitHub's upload widget |
| Submit a dummy PR comment in the browser to harvest `user-attachments` URLs | `ManagePullRequest` already hosts the file |

## Troubleshooting

| Issue | Solution |
| --- | --- |
| Path not rewritten | Use an absolute `/opt/cursor/artifacts/...` path in `src` |
| Special characters in the filename | Copy to a simple name under `/opt/cursor/artifacts/` first |
| Video does not play | Use `mp4` or `webm`; include `controls` on the `video` tag |
| No PR yet | Create it with `ManagePullRequest` `create_pr`, then attach |
| `computerUse` unavailable | Attach files you already have; do not install a browser CLI |

## Notes

- Vendored from [jacobmassey/github-upload-media-to-pr](https://github.com/jacobmassey/github-upload-media-to-pr)
  (MIT; copyright 2026 tonkotsuboy, Jacob Massey). Capture/attach replaced with
  Cursor Cloud `computerUse`, `RecordScreen`, and `ManagePullRequest`.
- Multiple files: stage all of them, then attach in one description section or
  one comment unless the user asked for separate comments.
