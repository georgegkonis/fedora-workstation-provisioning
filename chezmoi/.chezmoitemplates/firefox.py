"""Discover Firefox profiles and preserve unmanaged user.js content."""
import configparser
import os
from pathlib import Path
import re
import sqlite3

BEGIN = "// BEGIN CHEZMOI MANAGED FIREFOX"
END = "// END CHEZMOI MANAGED FIREFOX"


def profile_registries(home):
    home = home.resolve()
    roots = (
        home / ".config/mozilla/firefox",
        home / ".mozilla/firefox",
        home / ".var/app/org.mozilla.firefox/.config/mozilla/firefox",
        home / ".var/app/org.mozilla.firefox/.mozilla/firefox",
    )
    seen = set()
    for root in roots:
        registry = root / "profiles.ini"
        if not registry.is_file():
            continue
        registry = registry.resolve()
        if registry in seen:
            continue
        seen.add(registry)
        config = configparser.ConfigParser(interpolation=None)
        config.read(registry)
        yield registry.parent, config


def default_profiles(home):
    home = home.resolve()
    profiles = set()
    for root, config in profile_registries(home):
        # Installation defaults take precedence over the legacy Default=1 profile.
        defaults = [config[section]["Default"] for section in config.sections()
                    if section.startswith("Install") and config[section].get("Default")]
        if defaults:
            candidates = [root / value for value in defaults]
        else:
            candidates = []
            for section in config.sections():
                entry = config[section]
                if section.startswith("Profile") and entry.get("Default") == "1" and entry.get("Path"):
                    path = Path(entry["Path"])
                    candidates.append(root / path if entry.get("IsRelative", "1") == "1" else path)
        for candidate in candidates:
            profile = candidate.resolve()
            if profile.is_relative_to(home) and profile.is_dir():
                profiles.add(profile)
    return sorted(profiles)


def profile_targets(home, source, work_enabled=False):
    defaults = default_profiles(home)
    targets = {profile: source for profile in defaults}
    for root, config in profile_registries(home):
        for section in config.sections():
            entry = config[section]
            if not section.startswith("Profile") or not entry.get("Path"):
                continue
            profile = Path(entry["Path"])
            if entry.get("IsRelative", "1") == "1":
                profile = root / profile
            if profile.resolve() not in defaults:
                continue
            store = entry.get("StoreID", "")
            if not re.fullmatch(r"[0-9a-fA-F]+", store):
                continue
            database = root / "Profile Groups" / (store + ".sqlite")
            if not database.is_file():
                continue
            # Read only the names and paths in the selected profile group.
            try:
                connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
                try:
                    rows = connection.execute("SELECT name, path FROM Profiles").fetchall()
                finally:
                    connection.close()
            except sqlite3.Error as error:
                raise ValueError(f"Cannot read Firefox profile group {database}: {error}") from error
            for name, value in rows:
                if name.casefold() not in ("personal", "work"):
                    continue
                preferences = source.parent / (name.casefold() + ".js")
                target = (root / value).resolve()
                if name.casefold() == "work" and not work_enabled:
                    # A Work profile may also be the installation default.
                    # Remove its fallback rather than applying Personal settings.
                    targets.pop(target, None)
                    continue
                if preferences.is_file() and target.is_relative_to(home.resolve()) and target.is_dir():
                    targets[target] = preferences
    return targets


def merge_preferences(existing, preferences):
    lines = existing.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == BEGIN]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == END]
    block = BEGIN + "\n" + preferences.rstrip("\n") + "\n" + END + "\n"
    if not starts and not ends:
        return existing + ("\n" if existing and not existing.endswith("\n") else "") + block
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ValueError("Malformed managed Firefox block; repair its markers before reapplying")
    return "".join(lines[:starts[0]]) + block + "".join(lines[ends[0] + 1:])


def apply_preferences(home, source, work_enabled=False):
    profiles = profile_targets(home, source, work_enabled)
    if not profiles:
        print("Firefox preferences: no eligible profiles found; launch Firefox and check profile names before reapplying.")
    for profile, preferences_file in profiles.items():
        preferences = preferences_file.read_text()
        path = profile / "user.js"
        if not path.resolve().is_relative_to(home.resolve()):
            raise ValueError(f"Firefox user.js points outside the home directory: {path}")
        # Preserve newlines and unrelated content exactly, including CRLF files.
        existing = ""
        if path.exists():
            with path.open(newline="") as stream:
                existing = stream.read()
        content = merge_preferences(existing, preferences)
        if content != existing:
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", newline="") as stream:
                stream.write(content)
