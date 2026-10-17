export ANSIBLE_CONFIG := "ansible/ansible.cfg"
set positional-arguments

playbooks := "ansible/playbook.yml ansible/verify.yml"

# Configure the workstation (e.g. `just run --yes --tags gnome`)
[arg('preset', long, help='Preset from config/presets')]
[arg('local', long, help='Local overrides file')]
[arg('tags', long, help='Comma-separated feature tags')]
[arg('no_local', long='no-local', value='--no-local', help='Ignore saved overrides')]
[arg('yes', long, value='--yes', help='Skip configuration and confirmation prompts')]
[arg('configure', long, value='--configure', help='Edit saved selections interactively')]
[arg('diff', long, value='--diff', help='Show applied changes')]
[arg('upgrade', long, value='--upgrade', help='Also upgrade RPMs and system Flatpaks first')]
[arg('help', long, short='h', value='--help', help='Show bootstrap help')]
run preset='' local='' tags='' no_local='' yes='' configure='' diff='' upgrade='' help='':
    ./bootstrap.sh \
        {{ if preset == '' { '' } else { '--preset=' + quote(preset) } }} \
        {{ if local == '' { '' } else { '--local=' + quote(local) } }} \
        {{ if tags == '' { '' } else { '--tags=' + quote(tags) } }} \
        {{ no_local }} {{ yes }} {{ configure }} {{ diff }} {{ upgrade }} {{ help }}

# Dry run: Ansible check mode and chezmoi diff
[arg('args', help='bootstrap options, e.g. --preset=work --tags gnome')]
plan *args:
    ./bootstrap.sh --check --diff "$@"

# Verify installed state against selections
[arg('args', help='bootstrap options, e.g. --preset=work')]
verify *args:
    ./bootstrap.sh --verify "$@"

# Print the resolved configuration
[arg('args', help='bootstrap options, e.g. --preset=minimal --no-local')]
config *args:
    ./bootstrap.sh --show-config "$@"

# Apply only chezmoi dotfiles
[arg('args', help='bootstrap options, e.g. --check')]
dotfiles *args:
    ./bootstrap.sh --yes --dotfiles "$@"

# Upgrade installed RPMs and system Flatpaks only
[arg('args', help='bootstrap options, e.g. --check --diff')]
update *args:
    ./bootstrap.sh --yes --tags upgrade "$@"

# Validate configuration, syntax, and tests without provisioning
check:
    ./bootstrap.sh --validate
    for playbook in {{ playbooks }}; do ansible-playbook -i ansible/inventory.ini "$playbook" --syntax-check || exit; done
    python3 -m unittest discover -s tests

# Run configuration and isolated dotfile tests
[arg('args', help='unittest options, e.g. -v -f -k PATTERN')]
test *args:
    python3 -m unittest discover -s tests "$@"

# Lint Ansible without provisioning
[arg('args', help='ansible-lint options, e.g. --offline --strict -v')]
lint *args:
    ansible-lint {{ playbooks }} "$@"
