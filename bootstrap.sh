#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ ! -e profile.local.yml && ! -L profile.local.yml ]]; then
    cp -- profile.yml profile.local.yml
fi

sudo dnf install -y ansible git just
ansible-galaxy collection install -r ansible/requirements.yml

printf '\nBootstrap complete. Edit profile.local.yml, then run: just run\n'
