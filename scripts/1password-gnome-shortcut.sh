#!/bin/bash
# 1Password GNOME Quick Access Shortcut Setup

path="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/1pass/"

# 1. Define the shortcut's name, command, and keybind
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$path name '1Password Quick Access'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$path command '1password --quick-access'
gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$path binding '<Ctrl><Shift>space'

# 2. Add it to your active custom shortcuts list
current=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings | sed "s/@as //; s/\[//; s/\]//; s/^ *//; s/ *$//")
if [ -z "$current" ]; then
  gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "['$path']"
else
  gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "[$current, '$path']"
fi
