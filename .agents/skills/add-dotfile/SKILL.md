---
name: add-dotfile
description: Add or change home-directory configuration managed by chezmoi, such as shell hooks, Git config, editor, CLI or application preferences. Use when the user wants a dotfile, ~/.config entry, shell alias/hook, Git identity or application preference managed in this repo.
---

# Add dotfile

Chezmoi (`chezmoi/`) owns home configuration. Ansible owns packages, services and custom systemd user units; do not put those here.

## Choose the file type

| Need | Use |
|---|---|
| Static file wholly owned by the repo | plain file, e.g. `chezmoi/dot_config/<app>/<file>` |
| Varies with selections | `.tmpl` reading `.workstation.<key>` (same shape as `config/defaults.yml`) |
| File the user or app also edits (`.bashrc`, `.zshrc`, `.gitconfig`) | `modify_` script that adds one owned include and preserves everything else |
| Mutating app state (e.g. Firefox prefs) | `run_after_` script that edits only managed keys |

Prefer an owned file included from the user's file (see `modify_dot_gitconfig.tmpl` → `~/.config/git/workstation.gitconfig`, `modify_dot_bashrc.tmpl` → `~/.config/shell/workstation.sh`) over rewriting the user's file. Shared helpers live in `chezmoi/.chezmoitemplates/`.

## Rules

- Use templates only where selections vary; otherwise a static file.
- Modification scripts must be idempotent and keep unrelated existing state; the retained include goes last so repo-owned defaults win.
- Work Git identity is separate from personal projects: `dot_config/git/work.gitconfig.tmpl` is the work identity, `workstation.gitconfig.tmpl` the shared one. Never put real names, emails or signing keys in the repo; they come from `git.*` in `.local.yml`.
- Never commit credentials or tokens. Paths for apps that are Flatpaks live under `dot_var/app/<app-id>/`.
- Skip files that selections disable via `chezmoi/.chezmoiignore`.

## Finish

Add or extend a profile in `tests/test_dotfiles.py` (it runs a real chezmoi against temporary homes and checks that unrelated content survives and a second apply converges). Then run `validate-change`. Commit with the `commit` skill, scope `dotfiles` or the app name.
