# Fedora Workstation Provisioning (Personal)

This is my internal Ansible setup for provisioning a fresh Fedora Linux workstation with my preferred tools and development environments. It automates installation and configuration so I can get up and running quickly after a reinstall.

## What It Does

- Installs core system tools (Git, Zsh, Podman, Tmux, Curl, Make)
- Sets up development IDEs (Visual Studio Code, JetBrains Toolbox)
- Installs Docker Engine (CLI) and Docker Desktop (GUI)
- Installs 1Password and Postman (via Flatpak)

## Installation

1. Install Ansible and Git:
	```bash
	sudo dnf install -y ansible git
	```
2. Run the playbook from this directory:
	```bash
	sudo ansible-playbook -i intentory.ini playbook.yml
	```
	*(Make sure to use `intentory.ini` as the inventory file name.)*

## Structure

- `playbook.yml`: Main playbook
- `intentory.ini`: Local inventory (localhost)
- `tasks/`: Task files for each tool or group

## License

MIT License. See LICENSE for details.