export ANSIBLE_CONFIG := "ansible/ansible.cfg"
set positional-arguments

playbooks := "ansible/playbook.yml ansible/verify.yml ansible/playbooks/update.yml"

# Configure the workstation (e.g. `just run --yes --tags gnome`)
[arg('preset', long, help='Preset from config/presets')]
[arg('machine', long, help='Hardware definition from config/machines')]
[arg('local', long, help='Local overrides file')]
[arg('tags', long, help='Comma-separated feature tags')]
[arg('no_local', long='no-local', value='--no-local', help='Ignore saved overrides')]
[arg('yes', long, value='--yes', help='Skip configuration and confirmation prompts')]
[arg('configure', long, value='--configure', help='Edit saved selections interactively')]
[arg('show_config', long='show-config', value='--show-config', help='Print resolved configuration')]
[arg('validate', long, value='--validate', help='Validate configuration only')]
[arg('syntax_check', long='syntax-check', value='--syntax-check', help='Check Ansible syntax')]
[arg('check', long, value='--check', help='Ansible check mode and chezmoi dry run')]
[arg('verify', long, value='--verify', help='Verify installed state')]
[arg('diff', long, value='--diff', help='Show proposed changes')]
[arg('dotfiles', long, value='--dotfiles', help='Run only chezmoi')]
[arg('help', long, short='h', value='--help', help='Show bootstrap help')]
run preset='' machine='' local='' tags='' no_local='' yes='' configure='' show_config='' validate='' syntax_check='' check='' verify='' diff='' dotfiles='' help='':
    ./bootstrap.sh \
        {{ if preset == '' { '' } else { '--preset=' + quote(preset) } }} \
        {{ if machine == '' { '' } else { '--machine=' + quote(machine) } }} \
        {{ if local == '' { '' } else { '--local=' + quote(local) } }} \
        {{ if tags == '' { '' } else { '--tags=' + quote(tags) } }} \
        {{ no_local }} {{ yes }} {{ configure }} {{ show_config }} {{ validate }} {{ syntax_check }} {{ check }} {{ verify }} {{ diff }} {{ dotfiles }} {{ help }}

# Update installed RPM and system Flatpak packages
[arg('args', help='Ansible options, e.g. --check --diff --tags TAGS')]
update *args:
    ansible-playbook -K -i ansible/intentory.ini ansible/playbooks/update.yml "$@"

# Validate configuration, syntax, and tests without provisioning
check:
    ./bootstrap.sh --validate
    for playbook in {{ playbooks }}; do ansible-playbook -i ansible/intentory.ini "$playbook" --syntax-check || exit; done
    python3 -m unittest discover -s tests

# Run configuration and isolated dotfile tests
[arg('args', help='unittest options, e.g. -v -f -k PATTERN')]
test *args:
    python3 -m unittest discover -s tests "$@"

# Lint Ansible without provisioning
[arg('args', help='ansible-lint options, e.g. --offline --strict -v')]
lint *args:
    ansible-lint {{ playbooks }} "$@"
