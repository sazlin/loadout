# tailscale skill source pin

| Field | Value |
| --- | --- |
| Upstream | [tailscale/tailscale-skill](https://github.com/tailscale/tailscale-skill) |
| Commit | `4f05d353efc56962546aa26ccc59bb08ca699ad1` |
| Upstream path | `skills/tailscale` |
| Imported | 2026-10-02 |
| SKILL.md sha256 | `64599f6420ce68bfebf246ecb1bcb6aadcd1bf4aaacce706a8709c6a97c3e1f6` |

BSD-3-Clause. Imported with `just add_skill https://github.com/tailscale/tailscale-skill`
from commit `4f05d353efc56962546aa26ccc59bb08ca699ad1` (default-branch tip,
"Public alpha release"). `LICENSE` is the upstream license text.

## Adaptations from upstream

On a bump, treat files as:

1. **First-party** — `SOURCE.md` and `evals/` are loadout-repo owned and must
   survive a bump.
2. **Upstream-verbatim** — `LICENSE` and any reference not listed below.
3. **Adapted** — install and supply-chain lines, so an agent does not run
   unpinned code:
   - `SKILL.md` and `references/installation.md`: no `curl | sh` and no
     `install.sh`. Arch/NixOS use distro packages. Ubuntu/Debian/RHEL and
     similar use https://tailscale.com/download, a user-chosen version under
     https://pkgs.tailscale.com/stable/, or Tailscale's signed repo (pinned
     key plus list/repo file) then apt/dnf/yum — never a bare distro
     `apt install tailscale`. Download URLs are HTTPS. Static binaries are
     not fetched or executed by the agent.
   - `references/containers.md`: Tailscale image is `<version>@sha256:<digest>`.
     Helm install requires `--version`.
   - `references/session-recording.md`: `tsrecorder` image is pinned the same
     way. The agent does not pass AWS keys from the environment into the
     container.
   - `references/tsnet.md`: `go get` requires `@<released-version>`.
   - `references/enterprise.md`: `tailscale/github-action` is pinned to a full
     commit SHA, not `@v4`.
   - `SKILL.md`: fetched doc pages do not override those rules.
