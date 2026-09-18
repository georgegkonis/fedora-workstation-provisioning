# Personal Laptop Settings Inventory

Source: current work laptop, Fedora 44. Selected preferences are captured in `roles/preferences/files/` and applied by the `preferences` role. This is not a complete configuration backup.

## Desktop Preferences

| Setting | Current value |
| --- | --- |
| Color scheme | Prefer dark |
| GTK theme | Adwaita |
| Icon theme | MoreWaita |
| Interface font | Adwaita Sans 11 |
| Window buttons | `appmenu:minimize,close` |
| Touchpad tap-to-click | Enabled |
| Keyboard layouts | US International with AltGr (`us+altgr-intl`), Greek (`gr`) |

The preferences role installs MoreWaita at the source laptop's Git revision before applying the icon preference.

## Enabled GNOME Extensions

- `advanced-media-controller@sanjai.com`
- `clipboard-indicator@tudmotu.com`
- `dynamic-music-pill@andbal`
- `weatheroclock@CleoMenezesJr.github.io`
- `caffeine@patapon.info`
- `docker-manager@omerfarukgungor`

The desktop role installs compatible releases and enables the source selection in `group_vars/all.yml`. Additional extensions from the existing repository list remain available; unavailable releases are reported and skipped.

## Preference Files Located

- `~/.bashrc`
- `~/.config/Code/User/settings.json`

Selected VS Code settings and 29 extensions have been exported. Cloud project selections and extension runtime state are excluded. Bash receives only a portable PATH block; the source startup file contains a work credential and must not be copied into the repository.

## Captured Software and Preferences

- 238 dconf values: desktop, input devices, keyboard shortcuts, extension preferences, and Ptyxis.
- 28 installed Flatpak app IDs, recorded in `roles/preferences/files/installed-flatpaks.yml`; the desktop app list covers these and preserves existing repository choices.
- Node.js 22/npm, Python/pip, GCC/C++, Ninja, GitHub CLI, git-subtree, jq, bat, ripgrep, Neovim, Terraform, Azure CLI, and Typst 0.15.0.
- Existing .NET SDK, PowerShell, Docker, Podman, Toolbox, and CLI installer tasks remain part of provisioning.
- Selected JetBrains editor and appearance XML components, excluding registry state, company code styles, accounts, and project data.

## Destination Steps

- Install and authenticate JetBrains IDEs through Toolbox; use `personal_jetbrains_versions` to restore preferences into the installed versions (see README).
- Authenticate applications and configure personal cloud accounts separately.
- Choose personal wallpapers and custom sounds; their source files are not transferred.
- Validate full provisioning on the personal laptop. Checks here do not establish that every external repository or installer works on a fresh system.

Keep credentials, SSH keys, VPN profiles, company certificates, and employer configuration outside this repository.
