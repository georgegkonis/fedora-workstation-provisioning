---
name: update-pins
description: Update the pinned upstream versions, revisions and checksums in ansible/vars/catalog.yml (Typst, Git Credential Manager, MoreWaita, Anaconda). Use whenever the user asks to bump, update, upgrade, refresh or check for newer pins/versions/releases/checksums in this repo, or says a pinned tool is outdated, even if they don't name catalog.yml.
---

# Update pins

`ansible/vars/catalog.yml` is the only place upstream versions are pinned; tasks consume it by variable name. A bump is a data edit. `scripts/update_pins.py` does the lookup, checksum computation and edit deterministically (Python stdlib, network access required); do not hand-edit versions or hashes.

## Workflow

1. Baseline: run `just lint` before changing anything and note any existing failures. They are not caused by the bump; do not fix them here, but report them.
2. Dry run (writes nothing): `python3 .agents/skills/update-pins/scripts/update_pins.py [typst|gcm|morewaita|anaconda ...]`. No names = all pins. `--json` for machine-readable output. `GITHUB_TOKEN` avoids API rate limits. The script retries network calls itself; if it still exits with a network error, rerun once before reporting.
3. Show current → latest. Nothing changed: stop. If the user only asked to check, stop here. Otherwise continue without asking again, restricted to the pins they named (default all).
4. Apply: same command plus `--apply`.
5. Verify: `just check` (must pass) and `just lint` (must not be worse than the baseline). Never run `just run` or otherwise provision. On a new failure, revert with `git checkout ansible/vars/catalog.yml` and report.
6. Review `git diff ansible/vars/catalog.yml`: only the intended pins changed.
7. Commit with the repo's commit workflow, staging only `ansible/vars/catalog.yml`. One commit per run, subject scoped to what moved, e.g. `chore(development): bump Typst to 0.15.1` or `chore: bump Typst and MoreWaita pins` for several; list old → new in the body for multiple pins. Leave unrelated working-tree changes uncommitted and mention them. Do not push.

## What the script guarantees

- Only stable releases (GitHub `releases/latest`); Anaconda picks the newest release that has both x86_64 and aarch64 installers.
- GCM sha256s are computed by downloading each architecture's tarball and cross-checked against GitHub's asset digest; a mismatch aborts.
- Anaconda sha256s come from the vendor's archive index (installers are ~1 GB; not downloaded).
- Version and checksum map are written together, other lines/comments untouched, hashes validated as 64 lowercase hex.
- Typst has no checksum pin; do not add one. MoreWaita tracks upstream `HEAD` as a full commit SHA.

## When the script stops

If it aborts because an expected upstream asset is missing or renamed, the task's URL template (`ansible/roles/development/tasks/{typst,git_credential_manager,anaconda}.yml`, `ansible/roles/gnome/tasks/icons.yml`) needs updating first. Report that to the user rather than editing the task silently. For major jumps (e.g. Typst 0.x → 1.0), skim release notes for breaking changes and flag them.

A new pin needs the script entry (`PINS` in `update_pins.py`) and a consuming task with a validating `assert` (see `anaconda.yml`).
