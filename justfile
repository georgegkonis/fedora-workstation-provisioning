export ANSIBLE_CONFIG := "ansible/ansible.cfg"

inventory := "ansible/intentory.ini"
setup_playbook := "ansible/playbook.yml"
update_playbook := "ansible/playbooks/update.yml"
verify_playbook := "ansible/verify.yml"

# Interactive setup
deps:
    ./bootstrap.sh

# Install the minimal preset, ignoring saved overrides (e.g. `just minimal --show-config`)
minimal *ARGS:
    ./bootstrap.sh --preset minimal --no-local {{ ARGS }}

# Run full provisioning
run:
    ./bootstrap.sh --yes

# Run a selected feature (e.g. `just tag docker`)
tag TAG:
    ./bootstrap.sh --yes --tags {{ TAG }}

# Update installed RPM and system Flatpak packages
update:
    ansible-playbook -K -i {{ inventory }} {{ update_playbook }}

# Check installed software and user settings without changing them
verify:
    ./bootstrap.sh --verify

# Validate configuration, syntax, and tests without provisioning
check:
    ./bootstrap.sh --validate
    ansible-playbook -i {{ inventory }} {{ setup_playbook }} --syntax-check
    ansible-playbook -i {{ inventory }} {{ update_playbook }} --syntax-check
    ansible-playbook -i {{ inventory }} {{ verify_playbook }} --syntax-check
    python3 -m unittest discover -s tests

# Run configuration and isolated dotfile tests
test:
    python3 -m unittest discover -s tests

# Lint Ansible without provisioning
lint:
    ansible-lint {{ setup_playbook }} {{ verify_playbook }} {{ update_playbook }}

# Validate the profile without provisioning
validate:
    ./bootstrap.sh --validate

# Ansible check mode and chezmoi dry run
dry-run:
    ./bootstrap.sh --check

# Show proposed changes without applying them
diff:
    ./bootstrap.sh --check --diff

# Show the full resolved configuration
config:
    ./bootstrap.sh --show-config

# Apply only user dotfiles
dotfiles:
    ./bootstrap.sh --yes --dotfiles
