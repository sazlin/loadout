# demo-tool

Launch CLI coding agents inside guest VMs.

## Features

- **Least-privilege mounts.** `/work` stays executable; staged state has a `256M` guest-write quota.
- **Layered config.** `tool.yaml`, then profile, then variant; launch flags override every file.
- **Tight guest mounts.** The work dir is executable. Clipboard is `ro,noexec`.
- **One launcher for Cursor or any CLI agent.** `demo` plus the zsh shim `demo-sb` share the same argv.
- **Throwaway guest state.** Config is copied into a temp dir and removed on exit.

## Installation

Requires Node.js 22+ and just.

```bash
git clone git@github.com:example/demo-tool.git
cd demo-tool
just install
just build
```

<details>
<summary>Without just, and extra images</summary>

```bash
# CLI only
cd packages/demo && npm ci && npm run build

# Build images
just images
```

</details>

## Quick start

```bash
node packages/demo/dist/cli.js --version
```

```text
0.1.0
```

```bash
node packages/demo/dist/cli.js --help
```

```text
Usage:
  demo <profile> [variant] [work]
  demo --help | --version
```

Put `packages/demo/dist/cli.js` on your PATH as `demo`, then:

```bash
demo cursor ts
```

Optional zsh autoload for the same launches:

```bash
fpath=(/path/to/demo-tool/zsh/functions $fpath)
autoload -U demo-sb
```
