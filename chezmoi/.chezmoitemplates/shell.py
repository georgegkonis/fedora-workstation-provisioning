#!/usr/bin/env python3
"""Manage only the workstation shell hook, preserving unrelated startup code."""
import re
import sys

content = sys.stdin.read()
for marker in ("ANSIBLE MANAGED PERSONAL CLI PATH", "ANSIBLE MANAGED CONDA",
               "CHEZMOI MANAGED WORKSTATION"):
    content = re.sub(r"(?m)^# BEGIN " + marker + r"\n[\s\S]*?^# END " + marker + r"\n?", "", content)
hook = '''# BEGIN CHEZMOI MANAGED WORKSTATION
if [ -f "$HOME/.config/shell/workstation.sh" ]; then
    . "$HOME/.config/shell/workstation.sh"
fi
# END CHEZMOI MANAGED WORKSTATION
'''
sys.stdout.write(content.rstrip("\n") + "\n\n" + hook if content.strip() else hook)
