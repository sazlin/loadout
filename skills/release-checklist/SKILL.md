---
name: release-checklist
description: Use this skill before every release; drive the release through versioning, verification, changelog review, and rollback readiness without skipping checks.
---

# Release checklist

1. Confirm the intended version, release scope, and target branch.
2. Review the complete diff and changelog for accurate user-facing release notes.
   - If the package version changed but `CHANGELOG.md` lacks a matching `## X.Y.Z` section, run `just changelog` (or let the version-change automation / CI workflow add it).
   - Prefer concise user-facing bullets; do not invent changes.
3. Run the full required lint, test, build, and packaging checks from a clean state.
4. Verify configuration, migrations, feature flags, and compatibility notes needed for deployment.
5. Prepare rollback instructions, publish only after all checks pass, and record the release version and verification evidence.
