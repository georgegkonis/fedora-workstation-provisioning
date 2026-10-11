---
name: update-pins
description: Update the pinned upstream versions, revisions and checksums in ansible/vars/catalog.yml (Typst, Git Credential Manager, MoreWaita, Anaconda). Use whenever the user asks to bump, update, upgrade, refresh or check for newer pins/versions/releases/checksums in this repo, or says a pinned tool is outdated, even if they don't name catalog.yml.
---

# Update pins

`ansible/vars/catalog.yml` is the only place upstream versions are pinned; tasks consume it by variable name. A bump is a data edit. `scripts/update_pins.py` does the lookup, checksum computation and edit deterministically (Python stdlib, network access required); do not hand-edit versions or hashes.

## Workflow

1. Dry run (writes nothing): `python3 .agents/skills/update-pins/scripts/update_pins.py [typst|gcm|morewaita|anaconda ...]`. No names = all pins. Add `--json` for machine-readable output. Set `GITHUB_TOKEN` if rate-limited.
2. Show the user current → latest. If nothing changed, stop.
3. Apply, restricted to what the user wants bumped: same command plus `--apply`.
4. Verify: `just check`, then `just lint`. Never run `just run` or otherwise provision.
5. Show `git diff ansible/vars/catalog.yml`. Commit only if asked, using the repo's commit workflow, scoped by what was bumped (e.g. `chore(development): bump Typst to 0.15.1`).

## What the script guarantees

- Only stable releases (GitHub `releases/latest`); Anaconda picks the newest release that has both x86_64 and aarch64 installers.
- GCM sha256s are computed by downloading each architecture's tarball and cross-checked against GitHub's asset digest; a mismatch aborts.
- Anaconda sha256s come from the vendor's archive index (installers are ~1 GB; not downloaded).
- Version and checksum map are written together, other lines/comments untouched, hashes validated as 64 lowercase hex.
- Typst has no checksum pin; do not add one. MoreWaita tracks upstream `HEAD` as a full commit SHA.

## When the script stops

If it aborts because an expected upstream asset is missing or renamed, the task's URL template (`ansible/roles/development/tasks/{typst,git_credential_manager,anaconda}.yml`, `ansible/roles/gnome/tasks/icons.yml`) needs updating first. Report that to the user rather than editing the task silently. For major jumps (e.g. Typst 0.x → 1.0), skim release notes for breaking changes and flag them.

A new pin needs the script entry (`PINS` in `update_pins.py`) and a consuming task with a validating `assert` (see `anaconda.yml`).
