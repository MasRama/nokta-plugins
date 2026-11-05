#!/usr/bin/env python3
"""Runs each plugin's Linux command once, as Nokta would, and checks it
prints a card: a JSON object as its last line that is one.

    tools/run_once.py [id...]

A plugin that keeps running (every = 0) is started, given a second to print
its first card, and stopped. Options get their defaults.
"""

import json
import os
import subprocess
import sys
import tempfile
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGINS = os.path.join(ROOT, "plugins")


def environment(plugin_id, folder, manifest, data):
    env = dict(os.environ)
    env.update(
        {
            "NOKTA_API": "1",
            "NOKTA_PLUGIN": plugin_id,
            "NOKTA_PLUGIN_DIR": folder,
            "NOKTA_PLUGIN_DATA": data,
        }
    )
    for option in manifest.get("options", []):
        value = option.get("default", "")
        if isinstance(value, bool):
            value = "true" if value else "false"
        env[f"NOKTA_OPTION_{option['key'].upper()}"] = str(value)
    return env


def last_card(output):
    """The whole output when it is one object, else its last line that is."""
    for text in [output, *reversed(output.strip().splitlines())]:
        try:
            card = json.loads(text)
        except ValueError:
            continue
        if isinstance(card, dict):
            return card
    return None


def run(plugin_id):
    folder = os.path.join(PLUGINS, plugin_id)
    with open(os.path.join(folder, "plugin.toml"), "rb") as f:
        manifest = tomllib.load(f)
    command = manifest["run"].get("command")
    if not command:
        print(f"skip {plugin_id}: no Linux command")
        return True
    every = manifest["run"].get("every", 0)
    timeout = manifest["run"].get("timeout", 20)
    with tempfile.TemporaryDirectory() as data:
        env = environment(plugin_id, folder, manifest, data)
        if every == 0:
            proc = subprocess.Popen(command, cwd=folder, env=env, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                out, err = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
        else:
            try:
                done = subprocess.run(command, cwd=folder, env=env, capture_output=True,
                                      text=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                print(f"FAIL {plugin_id}: ran longer than its timeout of {timeout} s", file=sys.stderr)
                return False
            out, err = done.stdout, done.stderr
    card = last_card(out)
    if card is None:
        print(f"FAIL {plugin_id}: printed no card\n{out}{err}", file=sys.stderr)
        return False
    print(f"ok   {plugin_id}: {card.get('title', '(no title)')}")
    return True


def main():
    ids = sys.argv[1:] or sorted(os.listdir(PLUGINS))
    results = [run(plugin_id) for plugin_id in ids]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
