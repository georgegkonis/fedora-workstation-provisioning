inventory := "intentory.ini"
playbook := "local-setup.yml"

# Install dependencies
deps:
    sudo dnf install -y ansible git
    ansible-galaxy collection install -r requirements.yml

# Run full provisioning
run:
    sudo ansible-playbook -i {{ inventory }} {{ playbook }}

# Run a specific role/tag (e.g. `just tag base`)
tag TAG:
    sudo ansible-playbook -i {{ inventory }} {{ playbook }} --tags {{ TAG }}

# Update all system packages
update:
    sudo ansible-playbook -i {{ inventory }} {{ playbook }} --tags update

# Check syntax without provisioning
check:
    ansible-playbook -i {{ inventory }} {{ playbook }} --syntax-check
