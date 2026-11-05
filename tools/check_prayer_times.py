#!/usr/bin/env python3
"""Checks that prayer-times' two scripts agree: prayer.py (Linux and macOS)
and prayer.ps1 (Windows) must print the same card for the same place,
options, time zone and time.

    tools/check_prayer_times.py

PWSH is the command that runs PowerShell (default: pwsh). Coordinates only,
so nothing is looked up on the network.
"""

import json
import os
import shlex
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "plugins", "prayer-times")

CASES = [
    # Time zone, place, options, the time now.
    ("Asia/Jakarta", "-6.1754,106.8272", {}, "2026-11-05T14:50"),
    ("Asia/Jakarta", "-6.1754,106.8272", {"language": "English"}, "2026-11-05T14:56"),
    ("Asia/Jakarta", "-6.1754,106.8272", {"remind_minutes": "15"}, "2026-11-05T17:40"),
    ("Asia/Jakarta", "-6.1754,106.8272", {}, "2026-11-05T21:30"),
    ("Asia/Jakarta", "-6.1754,106.8272", {"badge_minutes": "180"}, "2026-11-05T15:00"),
    ("Asia/Makassar", "-5.1477,119.4327", {"asr": "Hanafi"}, "2026-03-20T12:00"),
    ("Asia/Kuala_Lumpur", "3.139,101.6869", {"method": "JAKIM (Malaysia)"}, "2026-06-21T05:00"),
    ("Asia/Riyadh", "21.4225,39.8262", {"method": "Umm al-Qura (Makkah)"}, "2026-12-21T18:00"),
    ("Africa/Cairo", "30.0444,31.2357", {"method": "Egypt", "badge_minutes": "0"}, "2026-08-01T12:00"),
    ("Europe/London", "51.5074,-0.1278", {"method": "Muslim World League", "language": "English"}, "2026-11-05T13:59"),
    ("America/New_York", "40.7128,-74.006", {"method": "ISNA (North America)", "alert": "false"}, "2026-07-04T20:30"),
]


def run(command, tz, place, options, now):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "TZ": tz,
        "PRAYER_NOW": now,
        "NOKTA_OPTION_LOCATION": place,
    }
    env.update({"NOKTA_OPTION_" + k.upper(): v for k, v in options.items()})
    done = subprocess.run(command, cwd=FOLDER, env=env, capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        sys.exit(f"{command[0]} failed: {done.stderr.strip()}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def main():
    pwsh = shlex.split(os.environ.get("PWSH", "pwsh"))
    failed = False
    for tz, place, options, now in CASES:
        python = run(["python3", "prayer.py"], tz, place, options, now)
        powershell = run([*pwsh, "-NoProfile", "-File", "prayer.ps1"], tz, place, options, now)
        if python == powershell:
            print(f"ok   {tz} {now}: {python['title']}")
        else:
            failed = True
            print(f"FAIL {tz} {now} {options}\n  python:     {json.dumps(python)}\n  powershell: {json.dumps(powershell)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
