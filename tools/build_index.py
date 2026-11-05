#!/usr/bin/env python3
"""Checks every plugin under plugins/ and builds the catalog Nokta reads.

    tools/build_index.py              check only
    tools/build_index.py --out DIR    check, then write DIR/index.json and
                                      copy each plugin to DIR/plugins/<id>/

index.json lists each plugin with every one of its files, their size and
SHA-256. Nokta downloads a plugin file by file and installs nothing when one
does not match, so the index and the files must be published together.
The rules mirror Nokta's own (core/src/features/plugins/manifest.rs and
catalog.rs); Nokta checks them again when it installs a plugin.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS = os.path.join(ROOT, "plugins")
INDEX_API = 1
PLUGIN_API = 1
MAX_FILES = 500
MAX_BYTES = 20 * 1024 * 1024
ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
NAME = re.compile(r"^[A-Za-z0-9._-]+$")
OPTION_KEY = re.compile(r"^[a-z0-9_]{1,32}$")
OPTION_TYPES = {"text", "bool", "int", "choice"}
LIMITS = {"name": 40, "description": 160, "version": 20, "author": 60, "homepage": 300}


def valid_path(path):
    """Plain relative names only, as Nokta accepts them."""
    parts = path.split("/")
    return (
        0 < len(path) <= 200
        and len(parts) <= 6
        and all(part and not part.startswith(".") and NAME.match(part) for part in parts)
    )


def check_manifest(folder, manifest):
    errors = []
    if manifest.get("api") != PLUGIN_API:
        errors.append(f"api must be {PLUGIN_API}")
    plugin_id = manifest.get("id", "")
    if not isinstance(plugin_id, str) or not ID.match(plugin_id):
        errors.append("id must be 2 to 40 of a-z, 0-9 and -, not starting with -")
    elif plugin_id != folder:
        errors.append(f"id is {plugin_id!r} but the folder is {folder!r}")
    for key in ("name", "version"):
        if not str(manifest.get(key, "")).strip():
            errors.append(f"{key} is missing")
    for key, limit in LIMITS.items():
        value = manifest.get(key, "")
        if not isinstance(value, str):
            errors.append(f"{key} must be text")
        elif len(value) > limit:
            errors.append(f"{key} is longer than {limit} characters")
    homepage = manifest.get("homepage", "")
    if homepage and not homepage.startswith(("https://", "http://")):
        errors.append("homepage must be an http(s) address")
    run = manifest.get("run")
    if not isinstance(run, dict):
        errors.append("[run] is missing")
        run = {}
    if not run.get("command") and not run.get("windows"):
        errors.append("[run] needs command or windows")
    every = run.get("every", 0)
    if not isinstance(every, int) or not (every == 0 or 5 <= every <= 86400):
        errors.append("every must be 0, or 5 to 86400")
    timeout = run.get("timeout", 20)
    if not isinstance(timeout, int) or not 1 <= timeout <= 120:
        errors.append("timeout must be 1 to 120")
    options = manifest.get("options", [])
    if len(options) > 12:
        errors.append("up to 12 options")
    keys = set()
    for option in options:
        key = option.get("key", "")
        if not OPTION_KEY.match(key) or key in keys:
            errors.append(f"option key {key!r} is not valid or is repeated")
        keys.add(key)
        if option.get("type") not in OPTION_TYPES:
            errors.append(f"option {key!r} has no valid type")
        if not str(option.get("title", "")).strip():
            errors.append(f"option {key!r} has no title")
    return errors


def plugin_files(folder_path):
    """Every file of a plugin, by its path inside the folder."""
    files = []
    for dirpath, dirnames, filenames in os.walk(folder_path):
        dirnames.sort()
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            files.append((os.path.relpath(full, folder_path).replace(os.sep, "/"), full))
    return files


def check_command(folder_path, run, errors):
    """A ./program named by command must be there and executable."""
    command = run.get("command") or []
    if command and command[0].startswith("./"):
        target = os.path.join(folder_path, command[0][2:])
        if not os.path.isfile(target):
            errors.append(f"command {command[0]} is not in the folder")
        elif not os.access(target, os.X_OK):
            errors.append(f"command {command[0]} is not executable (chmod +x, and commit the mode)")


def read_plugin(folder):
    folder_path = os.path.join(PLUGINS, folder)
    manifest_path = os.path.join(folder_path, "plugin.toml")
    if not os.path.isfile(manifest_path):
        return None, ["has no plugin.toml"]
    try:
        with open(manifest_path, "rb") as f:
            manifest = tomllib.load(f)
    except tomllib.TOMLDecodeError as err:
        return None, [f"plugin.toml: {err}"]
    errors = check_manifest(folder, manifest)
    run = manifest.get("run") if isinstance(manifest.get("run"), dict) else {}
    check_command(folder_path, run, errors)
    files = []
    total = 0
    for path, full in plugin_files(folder_path):
        if os.path.islink(full):
            errors.append(f"{path} is a link; plugins hold plain files")
            continue
        if not valid_path(path):
            errors.append(f"{path} is not a path a plugin may have (no hidden files, letters, digits, . _ - only)")
            continue
        with open(full, "rb") as f:
            data = f.read()
        total += len(data)
        files.append(
            {
                "path": path,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "executable": os.access(full, os.X_OK),
            }
        )
    if len(files) > MAX_FILES:
        errors.append(f"more than {MAX_FILES} files")
    if total > MAX_BYTES:
        errors.append("its files are bigger than 20 MiB")
    listing = {
        "id": manifest.get("id"),
        "name": manifest.get("name"),
        "description": manifest.get("description", ""),
        "version": manifest.get("version"),
        "author": manifest.get("author", ""),
        "homepage": manifest.get("homepage", ""),
        "icon": manifest.get("icon", ""),
        "unix": bool(run.get("command")),
        "windows": bool(run.get("windows")),
        "files": files,
    }
    return listing, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", help="where to write index.json and the plugins")
    args = parser.parse_args()

    listings = []
    failed = False
    for folder in sorted(os.listdir(PLUGINS)):
        if not os.path.isdir(os.path.join(PLUGINS, folder)):
            print(f"plugins/{folder}: only folders belong in plugins/", file=sys.stderr)
            failed = True
            continue
        listing, errors = read_plugin(folder)
        for error in errors:
            print(f"plugins/{folder}: {error}", file=sys.stderr)
        if errors:
            failed = True
        else:
            listings.append(listing)
            print(f"ok  {listing['id']} {listing['version']} ({len(listing['files'])} files)")
    if failed:
        print("the catalog has errors; nothing was written", file=sys.stderr)
        return 1

    if args.out:
        out = os.path.abspath(args.out)
        os.makedirs(out, exist_ok=True)
        for listing in listings:
            target = os.path.join(out, "plugins", listing["id"])
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(os.path.join(PLUGINS, listing["id"]), target)
        with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
            json.dump({"api": INDEX_API, "plugins": listings}, f, indent=1, ensure_ascii=False)
            f.write("\n")
        print(f"wrote {len(listings)} plugins to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
