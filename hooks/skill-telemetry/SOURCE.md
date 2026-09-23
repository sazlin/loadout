# skill-telemetry hook

Fail-open Cursor and Claude Code hook that emits the same three OpenTelemetry
metrics as [sazlin/skill-telemetry](https://github.com/sazlin/skill-telemetry)
(`skill.reads`, `skill.turns`, `skill.discovered_on_session_start`) over
OTLP/HTTP protobuf.

Compose it. Do not add it to `base`:

```yaml
loadouts:
  - python   # or typescript, github, ...
  - telemetry
```

The hook is a no-op unless `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_SERVICE_NAME`
are set. Missing python3, a down collector, a corrupt state file, or a bug in
the script prints allow JSON and exits 0.

## Metric contract

| Instrument | Type | Unit | When |
| --- | --- | --- | --- |
| `skill.reads` | Counter (monotonic sum) | `{read}` | A skill body was hydrated into context |
| `skill.turns` | Counter (monotonic sum) | `{turn}` | A turn ended in a session where at least one skill was offered |
| `skill.discovered_on_session_start` | UpDownCounter (non-monotonic sum) | `{skill}` | Once per root session, value = number of discovered skills |

Query, same as the plugin:

```promql
rate(skill_reads_total{skill_name="x"}) / rate(skill_turns_total)
```

Never put `skill.name` on turns or discovered. Read attributes also include
`skill.invocation_kind` (`model` or `user`; `autoload` is reserved and never
emitted on Cursor) and `skill.provider`.

Shared attributes on every series: `agent.session.id`, `gen_ai.request.model`,
`vcs.repository.name`, `agent.is_subagent`.

Instrumentation scope is `cursor.skill-telemetry` or `claude.skill-telemetry`
(`otel_scope_name` distinguishes sources). The plugin uses `omp.skill-telemetry`.

## Temporality

Each hook invocation is a new process, so delta points do not chain under the
collector `prometheusexporter`. The hook keeps running counts per
`(instrument, attribute set)` in a session state file and exports **cumulative**
points:

- `start_time_unix_nano` = first-seen time for the session
- `time_unix_nano` = now
- value = running count

Every export is a full snapshot of that session's series. A dropped export
self-heals on the next event.

## Export configuration

| Var | Default | Behavior |
| --- | --- | --- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | none | Missing/blank: no-op. Base URL; `/v1/metrics` is appended |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | none | If set, used verbatim and takes precedence |
| `OTEL_SERVICE_NAME` | none | Missing: no-op |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` | Anything else: no-op |
| `OTEL_EXPORTER_OTLP_HEADERS` | none | `k=v,k=v`, URL-decoded |
| `OTEL_EXPORTER_OTLP_TIMEOUT` | `2000` | Milliseconds, connect and read |
| `SKILL_TELEMETRY_ENABLED` | `true` | `false`/`0`: no-op |
| `SKILL_TELEMETRY_DEBUG` | unset | `1`: append to `debug.log` in the state dir |
| `SKILL_TELEMETRY_STATE_DIR` | cache dir | Override; never the project tree |
| `SKILL_TELEMETRY_ASSUME_ROOT` | unset | `1`: treat unknown sessions as cloud roots |
| `SKILL_TELEMETRY_SYNC_EXPORT` | unset | `1`: POST inline (tests) |

Never defaults the endpoint to `localhost:4318`.

State lives in `${SKILL_TELEMETRY_STATE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/skill-telemetry}`,
falling back to `$TMPDIR/skill-telemetry`. Cloud agents commit the working tree;
this hook must not write there.

## Skill roots and providers

A read path is classified by the longest matching root.

| Root | `skill.provider` |
| --- | --- |
| `<ws>/.cursor/skills`, `<ws>/.agents/skills`, nested `**/.cursor/skills`, `**/.agents/skills` | `workspace` |
| `~/.cursor/skills`, `~/.agents/skills` | `user` |
| `$CURSOR_PLUGIN_ROOT/**/skills`, `~/.cursor/plugins/**/skills` | `plugin` |
| `<ws>/.claude/skills`, `~/.claude/skills` | `claude` |
| `<ws>/.codex/skills`, `~/.codex/skills` | `codex` |
| anything else | ignored (not a skill load) |

Loadout's `Manifest.skills_dir` defaults to `.claude/skills`, so on loadout-managed
repos nearly every read reports `provider=claude`. That is the same meaning the
omp plugin gives the label.

A `SKILL.md` outside every root (for example `skills/foo/SKILL.md` in this
source repo) is not counted. `foo/references/x.md` is not a body load.

## Repository name

Walk up from the first workspace root to `.git`. Parse `.git/config` for
`[remote "origin"] url` and take the last path segment minus `.git`. Fall back
to the git root's basename, else `none`. omp uses the directory basename only;
reconcile in PromQL with `vcs_repository_name` if a checkout directory is
generically named (cloud VMs often are).

## Surface matrix (Phase 0)

Re-verified 2026-09-18 against Cursor docs plus this cloud agent environment.
Desktop and CLI rows that are not marked "live" are reconstructed from the
public hook payload schema (common envelope + event-specific fields) and
committed as redacted fixtures. Live capture of those surfaces still belongs
in a follow-up on a laptop with Cursor desktop and `agent -p`.

| Event | Desktop | CLI (`agent -p`) | Cloud | Notes |
| --- | --- | --- | --- | --- |
| `sessionStart` | Docs: new root chats | Docs: yes | **No** (deferred, read-only start) | `session_id`, `is_background_agent`, `composer_mode`; may return `env` |
| `sessionEnd` | Docs: yes | Docs: yes | **No** | End reason and duration |
| `beforeReadFile` | Docs: yes | Docs: yes | Docs: yes | `file_path`, `content`, `attachments[{type: file\|rule}]`. Output `permission` |
| `preToolUse` (`Read`) | Docs: yes | Docs: yes | Docs: yes | Same read as `beforeReadFile`; not registered (would double-count) |
| `beforeSubmitPrompt` | Docs: yes | Forum: no | Docs: yes | `prompt`, `attachments[{type: file\|rule}]`. No `skill` attachment type is documented |
| `stop` | Docs: yes | Forum: no | Docs: yes | `status`, `loop_count`. Not live-captured this run |
| `afterAgentResponse` | Docs: yes | Forum: no | Docs: yes | Not registered in v1; docs currently list `stop` as supported on cloud |
| `subagentStart` / `subagentStop` | Instance-dependent on 3.18 | Unknown | Docs: yes | `subagent_id`, `parent_conversation_id`, `subagent_model` |

Also verified this run:

1. `/skill-name` attach shape in `beforeSubmitPrompt` is still unobserved. v1
   parses `/name` in `prompt` text and any `attachments[].file_path` whose
   basename is `SKILL.md` under a skill root. If neither fires, `invocation_kind=user`
   is not counted (same class of gap as CLI). Transcript parsing is not in v1.
2. Custom Mode (sticky) reattach every turn is unobserved. If Cursor re-sends
   the body, that is a read; there is no `sticky` set.
3. Whether `subagentStart.subagent_id` equals the child's `conversation_id` is
   unobserved. The hook indexes `subagent_id` anyway. A child is only marked
   `agent.is_subagent=true` when its session id is in that index.
4. Whether every skill body load goes through native `beforeReadFile` (including
   the first load after `/` attach) is unobserved. v1 counts `beforeReadFile` of
   `SKILL.md` under a root and does not register `preToolUse`.
5. Cloud `conversation_id` uses a `bc-` prefix (`CURSOR_CONVERSATION_ID=bc-…`
   on the 2026-09-18 cloud image). `stop` is documented as supported; this run
   did not capture a live `stop` payload.
6. Cursor docs list `permission` on `beforeReadFile` output. The bash
   `allow()` helper and Python `_allow_payload` must stay aligned: Cursor
   `beforeReadFile` → `{"permission":"allow"}`, `beforeSubmitPrompt` →
   `{"continue":true}`, other events → `{}`.
7. Plugin skill roots on the cloud image are
   `~/.cursor/plugins/cache/cursor-public/<id>/<sha>/skills/<name>/SKILL.md`.
8. `python3` is present on the default cloud image (3.12).

## Documented gaps (v1)

- `invocation_kind=autoload` on Cursor. Not observable from hooks.
- `agent.is_subagent` on Claude Code, and on Cursor when `subagentStart` is not
  delivered (instance-dependent on 3.18) or when `subagent_id` ≠ child
  `conversation_id`.
- Failed reads: `beforeReadFile` fires before the read, so a later failure is
  not correlated.
- Desktop resumed root chats: no `sessionStart`, so discovered is not
  re-emitted; reads and turns still count once lazy init runs.
- Cloud: reads during early read-only turns before hooks load are missed.
  `sessionStart` / `sessionEnd` do not fire.
- CLI: `beforeSubmitPrompt` does not fire, so `invocation_kind=user` is not
  counted there. `sessionEnd` with `stops_seen == 0` emits the one turn.
- Live desktop/CLI stdin captures were not taken in the cloud implementation
  environment. Fixtures are redacted reconstructions of the documented schema.

## Collector notes

Manual check, once a collector is reachable:

1. Run `otel/opentelemetry-collector` with the `debug` exporter. Confirm the
   three metric names, cumulative temporality, and attributes.
2. Point the same hook at a collector with the `prometheus` exporter. Confirm
   `increase(skill_reads_total[5m])` rises within one session. Do not add a
   collector-side processor; the hook already exports cumulative per-session
   sums so Prometheus can `rate()` / `increase()` them.
