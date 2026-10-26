# Backend releases

Mapping of SemVer ↔ git tag ↔ deploy.

| Version | Git tag | Date | Notes |
|---------|---------|------|-------|
| 0.1.0 | — | 2026-10-24 | Baseline `VERSION`; CI: `main`→prod, `staging`→staging, `develop` no deploy |

## Who writes what

| Artifact | Owner |
|----------|--------|
| Root `VERSION` | Humans on release (bump before tag) |
| `CHANGELOG.md` | Humans — move `[Unreleased]` → `[X.Y.Z]` when cutting a release |
| Git tag | Prefer `backend/vX.Y.Z` (annotated); helper scripts historically used `vX.Y.Z` — align when tagging |
| Deploy | **CI only**: push/merge to `main` → prod host; `staging` → staging Docker. Tags do **not** auto-deploy by themselves |

Helpers (manual Git Flow): `scripts/git_flow_release.sh`, `scripts/git_flow_hotfix.sh` — update CHANGELOG before `finish`.

Source of truth for “what’s live”: branch on the host/staging clone + [OPS.md](OPS.md), not the SemVer table alone until releases are cut regularly.
