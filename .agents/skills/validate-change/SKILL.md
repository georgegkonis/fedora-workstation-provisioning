---
name: validate-change
description: Validate a change to this provisioning repo without provisioning the workstation. Runs configuration validation, Ansible syntax checks, tests and lint, check-mode where applicable, and reviews the diff for local or generated state. Use before committing or when asked to check, lint, test or review changes here.
---

# Validate change

Never run `just run`, `just update`, `just dotfiles` without `--check`, `./bootstrap.sh --yes`, or anything else that provisions, installs bootstrap dependencies, saves selections or executes installers.

## Workflow

```
- [ ] 1. Baseline lint on a clean tree (only if not already known)
- [ ] 2. just check
- [ ] 3. just lint
- [ ] 4. Check-mode (only for task behavior changes)
- [ ] 5. Diff review
```

1. `just lint` before editing, when starting fresh; note pre-existing failures and do not fix them here.
2. `just check`: `--validate`, `ansible-playbook --syntax-check` for `playbook.yml` and `verify.yml`, and the unit tests. Must pass.
3. `just lint` (`ansible-lint`). Must be no worse than the baseline.
4. If task behavior changed: `just plan` (add `--preset=work` or `--tags <tag>` to cover the path). Check mode does not install or save anything. In a restricted environment redirect Ansible temp paths first:
   ```bash
   export ANSIBLE_LOCAL_TEMP=/tmp/ansible-local ANSIBLE_REMOTE_TEMP=/tmp/ansible-remote
   ```
   For chezmoi-only changes: `just dotfiles --check`. For profile logic, `./bootstrap.sh --show-config --preset=<name>` prints the resolved configuration.
5. `git status` and `git diff`: confirm only intended files changed. Nothing from `.local.yml`, `.workstation/`, `__pycache__`, credentials, or personal Git identity may be staged.

On failure, fix the cause and rerun the failing step, then `just check` again. Report failures with output; do not claim success past a failing step.

## Selected tests

`just test -k PATTERN` runs a subset of `tests/` (`-v -f` also accepted).
