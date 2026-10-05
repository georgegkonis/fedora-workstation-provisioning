export ANSIBLE_CONFIG := "ansible/ansible.cfg"

inventory := "ansible/intentory.ini"
setup_playbook := "ansible/playbooks/local-setup.yml"
update_playbook := "ansible/playbooks/update.yml"
verify_playbook := "ansible/playbooks/verify.yml"

# Install dependencies after cloning
deps:
    ./bootstrap.sh

# Run full provisioning
run:
    ansible-playbook -K -i {{ inventory }} {{ setup_playbook }}

# Run a selected feature (e.g. `just tag docker`)
tag TAG:
    ansible-playbook -K -i {{ inventory }} {{ setup_playbook }} --tags {{ TAG }}

# Update installed RPM and system Flatpak packages
update:
    ansible-playbook -K -i {{ inventory }} {{ update_playbook }}

# Check installed software and user settings without changing them
verify:
    ansible-playbook -i {{ inventory }} {{ verify_playbook }}

# Check syntax without provisioning
check:
    ansible-playbook -i {{ inventory }} {{ setup_playbook }} --syntax-check
    ansible-playbook -i {{ inventory }} {{ update_playbook }} --syntax-check
    ansible-playbook -i {{ inventory }} {{ verify_playbook }} --syntax-check

# Validate the profile without provisioning
validate:
    ansible-playbook -i {{ inventory }} {{ setup_playbook }} --tags profile_check
