---
name: add-feature
description: Add a new feature toggle, option, preference, role, or service to the provisioning (config keys in defaults.yml, validation, playbook wiring, verification, tests). Use when the user wants a new selectable capability, a new Ansible role, a new systemd unit, or a new config key in this repo.
---

# Add feature

Configuration flows `config/defaults.yml` → preset → `.local.yml`, resolved only by `scripts/configuration.py`. Mappings merge; lists and scalars replace. Never add precedence logic elsewhere.

## Workflow

```
- [ ] 1. Decide the home (see below)
- [ ] 2. Declare the key in config/defaults.yml
- [ ] 3. Validate it in scripts/configuration.py
- [ ] 4. Consume it in Ansible
- [ ] 5. Verify it in ansible/tasks/verify.yml
- [ ] 6. Expose it in scripts/bootstrap.py (if user-selectable)
- [ ] 7. Add tests, then run validate-change
```

1. **Home.** Extend an existing role when the state fits it. Create `ansible/roles/<name>/` only for substantive machine state, never an empty role. Selections, hardware options and implementation preferences stay independent; a parent feature disabled makes children inactive.
2. **Defaults.** `defaults.yml` is the reference shape: `validate_shape` rejects unknown keys and wrong types, so every new key must exist there with its default. Keep ordinary software in lists, add options only for meaningful choices.
3. **Validation.** Add checks to `validate()` (`string_list`, `records`, `require`, regex patterns for versions). Cross-field rules belong here. If it changes what is installed, extend `select()` so `expected_rpms`/`flatpaks` stay correct.
4. **Ansible.** Role order lives in `ansible/playbook.yml` with `when: workstation.features...` and tags; add the role there. Repositories before packages. Fully qualified native modules, explicit file modes, guards on `command`/`shell`.
5. **Services.** Declare in `services.system`, `services.user` or `hardware.services` (`name`, optional `enabled`, `state`, `unit`). A custom unit file goes in `systemd/system/` or `systemd/user/` and is deployed by Ansible with the service; the validator checks it exists.
6. **Verify.** Add expected paths/CLIs to `verify.yml`; services declared above are verified automatically.
7. **UI.** `scripts/bootstrap.py` only emits configuration; add the key to its prompts, never install from it.
8. **Tests.** Add cases to `tests/test_configuration.py` (valid, invalid, precedence/selection). Add a profile to `tests/test_dotfiles.py` if chezmoi templates consume the key.

Skip any step that does not apply. Commit with the `commit` skill.
