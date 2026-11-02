#!/usr/bin/env python3
"""Read a local project folder and write a stack inventory. Read-only."""

import argparse
import json
import re
import sys
from pathlib import Path


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def add_component(components, name, version, source):
    components.append({
        "name": name,
        "version": version or "UNKNOWN",
        "source": source,
    })


def inventory(root):
    root = Path(root)
    if not root.is_dir():
        return None
    components = []
    unknowns = []
    language = "UNKNOWN"
    managers = []

    composer = root / "composer.json"
    lock = root / "composer.lock"
    if composer.exists():
        managers.append("composer")
        data = read_json(composer) or {}
        php = (data.get("require") or {}).get("php")
        if php:
            language = php
        if lock.exists():
            locked = read_json(lock) or {}
            for package in locked.get("packages") or []:
                add_component(components, package.get("name"), package.get("version"), "composer.lock")
        else:
            unknowns.append("composer.lock")
            for name, version in (data.get("require") or {}).items():
                if name != "php":
                    add_component(components, name, version, "composer.json")
    else:
        unknowns.append("composer.json")

    package_json = root / "package.json"
    package_lock = root / "package-lock.json"
    if package_json.exists():
        managers.append("npm")
        if package_lock.exists():
            locked = read_json(package_lock) or {}
            packages = locked.get("packages") or {}
            for name, meta in packages.items():
                if name:
                    add_component(components, name, meta.get("version"), "package-lock.json")
        else:
            unknowns.append("package-lock.json")
            data = read_json(package_json) or {}
            for name, version in (data.get("dependencies") or {}).items():
                add_component(components, name, version, "package.json")
    else:
        unknowns.append("package.json")

    wordpress = root / "wp-includes" / "version.php"
    platform = "unknown"
    if wordpress.exists():
        platform = "wordpress"
        match = re.search(r"\$wp_version\s*=\s*'([^']+)'", wordpress.read_text(errors="replace"))
        add_component(components, "wordpress", match.group(1) if match else "UNKNOWN", "wp-includes/version.php")
    else:
        unknowns.append("wp-includes/version.php")

    php_version = root / ".php-version"
    if php_version.exists():
        language = php_version.read_text().strip() or language
    else:
        unknowns.append(".php-version")

    return {
        "platform": platform,
        "language": language,
        "package_manager": "+".join(managers) if managers else "none",
        "components": components,
        "unknowns": unknowns,
    }


def compare(report, advisory_text):
    text = advisory_text.lower()
    for component in report["components"]:
        name = component["name"].lower()
        component["advisory"] = "named" if name and name in text else "not-named"
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True)
    parser.add_argument("--advisory-file")
    parser.add_argument("--out", default="stack-inventory.json")
    args = parser.parse_args()
    report = inventory(args.path)
    if report is None:
        print("UNKNOWN: folder cannot be read")
        return 2
    if args.advisory_file:
        report = compare(report, Path(args.advisory_file).read_text(errors="replace"))
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['platform']}: {len(report['components'])} components, {len(report['unknowns'])} unknowns")
    return 0


if __name__ == "__main__":
    sys.exit(main())
