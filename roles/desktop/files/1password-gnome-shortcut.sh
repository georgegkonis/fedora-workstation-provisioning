#!/bin/bash
# 1Password GNOME Shortcuts Setup

# Define shortcuts: path, name, command, binding
declare -A shortcuts
shortcuts["show,path"]="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/1pass-show/"
shortcuts["show,name"]="1Password Show"
shortcuts["show,command"]="1password --show"
shortcuts["show,binding"]="<Ctrl><Shift>O"

shortcuts["quick,path"]="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/1pass-quick/"
shortcuts["quick,name"]="1Password Quick Access"
shortcuts["quick,command"]="1password --quick-access"
shortcuts["quick,binding"]="<Ctrl><Shift>space"

shortcuts["lock,path"]="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/1pass-lock/"
shortcuts["lock,name"]="1Password Lock"
shortcuts["lock,command"]="1password --lock"
shortcuts["lock,binding"]="<Ctrl><Shift>L"

shortcuts["fill,path"]="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/1pass-fill/"
shortcuts["fill,name"]="1Password Fill in Browser"
shortcuts["fill,command"]="1password --fill"
shortcuts["fill,binding"]="<Ctrl><Shift>F"

# Get current custom-keybindings and strip @as prefix
current=$(gsettings get org.gnome.settings-daemon.plugins.media-keys custom-keybindings | sed "s/^@as //")
current_clean=$(echo "$current" | tr -d '[]' | tr -d "'" | tr -d ' ')

add_paths=()

# Loop through each shortcut
for key in quick show lock fill; do
  path="${shortcuts["$key,path"]}"
  name="${shortcuts["$key,name"]}"
  command="${shortcuts["$key,command"]}"
  binding="${shortcuts["$key,binding"]}"

  echo "Updating properties for: $name"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$path name "'$name'"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$path command "'$command'"
  gsettings set org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:$path binding "'$binding'"

  # Check if the path is already in the array
  if [[ ",$current_clean," != *",$path,"* ]]; then
    add_paths+=("'$path'")
  fi
done

# If any new paths, append them cleanly
if [ ${#add_paths[@]} -gt 0 ]; then
  new_elements=$(IFS=, ; echo "${add_paths[*]}")

  if [[ "$current" == "[]" || -z "$current" ]]; then
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "[$new_elements]"
  else
    base_array=$(echo "$current" | sed "s/]$//")
    gsettings set org.gnome.settings-daemon.plugins.media-keys custom-keybindings "$base_array, $new_elements]"
  fi
  echo "CHANGED: Added new paths to GNOME settings."
else
  echo "NO CHANGE: Paths are already in the GNOME shortcut list."
fi