#!/usr/bin/env python3
"""Check (default) or apply (--apply) upstream pin updates in ansible/vars/catalog.yml.

Stdlib only. Checksums come from the real artifact (GCM: downloaded and hashed,
cross-checked against the GitHub asset digest) or the vendor's published index
(Anaconda, whose installers are ~1 GB). Nothing is written unless --apply.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

CATALOG = Path(__file__).resolve().parents[4] / "ansible/vars/catalog.yml"
ARCHES = ("x86_64", "aarch64")
GCM_ARCH = {"x86_64": "x64", "aarch64": "arm64"}


def fetch(url, accept=None):
    for attempt in range(3):
        try:
            return _open(url, accept)
        except (OSError, urllib.error.URLError) as exc:
            if attempt == 2:
                raise SystemExit(f"network error fetching {url}: {exc}")


def _open(url, accept=None):
    headers = {"User-Agent": "update-pins"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    if accept:
        headers["Accept"] = accept
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60)


def latest_release(repo):
    with fetch(f"https://api.github.com/repos/{repo}/releases/latest") as r:
        return json.load(r)  # /latest already excludes drafts and pre-releases


def sha256_of_url(url):
    for attempt in range(3):
        h = hashlib.sha256()
        try:
            with fetch(url) as r:
                for chunk in iter(lambda: r.read(1 << 20), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError as exc:
            if attempt == 2:
                raise SystemExit(f"network error downloading {url}: {exc}")


def typst():
    return {"provision_typst_version": latest_release("typst/typst")["tag_name"].removeprefix("v")}


def gcm():
    rel = latest_release("git-ecosystem/git-credential-manager")
    version = rel["tag_name"].removeprefix("v")
    assets = {a["name"]: a for a in rel["assets"]}
    sums = {}
    for arch in ARCHES:
        name = f"gcm-linux-{GCM_ARCH[arch]}-{version}.tar.gz"
        if name not in assets:
            raise SystemExit(f"gcm: expected asset {name} missing; update the task before the pin")
        sums[arch] = sha256_of_url(assets[name]["browser_download_url"])
        digest = (assets[name].get("digest") or "").removeprefix("sha256:")
        if digest and digest != sums[arch]:
            raise SystemExit(f"gcm: {name} download hash {sums[arch]} != GitHub digest {digest}")
    return {"provision_gcm_version": version, "provision_gcm_sha256": sums}


def morewaita():
    out = subprocess.run(
        ["git", "ls-remote", "https://github.com/somepaulo/MoreWaita.git", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout
    return {"provision_morewaita_revision": out.split()[0]}


def anaconda():
    with fetch("https://repo.anaconda.com/archive/") as r:
        html = r.read().decode()
    rows = re.findall(
        r'<a href="Anaconda3-(\d{4}\.\d{2}-\d+)-Linux-(x86_64|aarch64)\.sh">.*?'
        r"<td>([0-9a-f]{64})</td>", html, re.S)
    by_release = {}
    for release, arch, sha in rows:
        by_release.setdefault(release, {})[arch] = sha
    complete = [r for r, s in by_release.items() if set(s) == set(ARCHES)]
    if not complete:
        raise SystemExit("anaconda: no release with both architectures in the archive index")
    release = max(complete, key=lambda r: tuple(int(x) for x in re.split(r"[.-]", r)))
    return {"provision_anaconda_release": release,
            "provision_anaconda_sha256": by_release[release]}


PINS = {"typst": typst, "gcm": gcm, "morewaita": morewaita, "anaconda": anaconda}


def current(text, key):
    m = re.search(rf"^{key}:[ \t]*(\S.*)?$", text, re.M)
    if not m:
        raise SystemExit(f"{key} not found in {CATALOG}")
    if m.group(1):
        return m.group(1).strip()
    block = re.search(rf"^{key}:\n((?:[ \t]+\S.*\n?)+)", text, re.M).group(1)
    return dict(re.findall(r"^\s+(\w+):\s*(\S+)", block, re.M))


def set_value(text, key, value):
    if isinstance(value, dict):
        for arch, sha in value.items():
            if not re.fullmatch(r"[0-9a-f]{64}", sha):
                raise SystemExit(f"{key}.{arch}: not a sha256: {sha}")
        block = re.search(rf"^{key}:\n(?:[ \t]+\S.*\n?)+", text, re.M)
        new = f"{key}:\n" + "".join(f"  {a}: {value[a]}\n" for a in ARCHES)
        return text[:block.start()] + new + text[block.end():]
    return re.sub(rf"^({key}:[ \t]*).*$", lambda m: m.group(1) + value, text, flags=re.M)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pins", nargs="*", choices=list(PINS), help="default: all")
    ap.add_argument("--apply", action="store_true", help="write catalog.yml")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args()

    text = CATALOG.read_text()
    report = []
    for name in args.pins or PINS:
        for key, new in PINS[name]().items():
            old = current(text, key)
            report.append({"pin": name, "key": key, "old": old, "new": new, "changed": old != new})
            if old != new and args.apply:
                text = set_value(text, key, new)
    if args.apply:
        CATALOG.write_text(text)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for r in report:
            mark = "UPDATE" if r["changed"] else "ok    "
            print(f"{mark} {r['key']}: {r['old']} -> {r['new']}" if r["changed"]
                  else f"{mark} {r['key']}: {r['old']}")
        if any(r["changed"] for r in report):
            print("applied" if args.apply else "dry run; re-run with --apply to write")


if __name__ == "__main__":
    sys.exit(main())
