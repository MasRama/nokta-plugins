#!/usr/bin/env python3
"""Checks that rain-soon's two scripts agree: rain.py (Linux and macOS) and
rain.ps1 (Windows) must print the same card for the same forecast, options,
time zone and time. The forecasts are made up here, so nothing is asked of
the network.

    tools/check_rain_soon.py

PWSH is the command that runs PowerShell (default: pwsh).
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "plugins", "rain-soon")
START = 1793863800  # 2026-11-05 14:30 in Jakarta
STEP = 15 * 60
NOW = START + STEP + 7 * 60  # 7 minutes into the second step

CASES = [
    # Millimetres per step (the past one first), options, time zone.
    ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], {}, "Asia/Jakarta"),
    ([0, 0, 0, 0, 0, 0, 0, 0, 0, 0], {"show_dry": "false", "language": "English"}, "Asia/Jakarta"),
    ([0, 0, 0, 0.1, 0.3, 0, 0, 0, 0, 0], {}, "Asia/Jakarta"),
    ([0, 0, 0.4, 1.2, 2.5, 0.2, 0, 0, 0, 0], {"language": "English"}, "Asia/Jakarta"),
    ([0, 0, 0, 0, 0, 0, 0.6, 0.6, 0, 0], {}, "Asia/Jakarta"),
    ([0, 0, 0, 0, 0, 0, 0.6, 0.6, 0, 0], {"lead_minutes": "120", "badge": "false"}, "Asia/Jakarta"),
    ([0, 0, 0.2, 0, 0, 0, 0, 0, 0, 0], {"alert": "false"}, "Europe/London"),
    ([0.3, 0.5, 0.5, 0.2, 0, 0, 0, 0, 0, 0], {}, "Asia/Jakarta"),
    ([0, 2.4, 3.0, 2.1, 1.0, 0.8, 0.5, 0.4, 0.2, 0.1], {"language": "English"}, "America/New_York"),
    ([0, 0.1, None, 0, 0, 0, 0, 0, 0, 0], {}, "Asia/Jakarta"),
]


def run(command, tz, forecast, options, data):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "TZ": tz,
        "RAIN_NOW": str(NOW),
        "RAIN_FORECAST": forecast,
        "NOKTA_PLUGIN_DATA": data,
        "NOKTA_OPTION_LOCATION": "-6.2,106.85",
    }
    env.update({"NOKTA_OPTION_" + k.upper(): v for k, v in options.items()})
    done = subprocess.run(command, cwd=FOLDER, env=env, capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        sys.exit(f"{command[0]} failed: {done.stderr.strip()}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def main():
    pwsh = shlex.split(os.environ.get("PWSH", "pwsh"))
    failed = False
    with tempfile.TemporaryDirectory() as data:
        for i, (rain, options, tz) in enumerate(CASES):
            forecast = os.path.join(data, f"forecast-{i}.json")
            times = [START + n * STEP for n in range(len(rain))]
            with open(forecast, "w", encoding="utf-8") as f:
                json.dump({"minutely_15": {"time": times, "precipitation": rain}}, f)
            python = run(["python3", "rain.py"], tz, forecast, options, data)
            powershell = run([*pwsh, "-NoProfile", "-File", "rain.ps1"], tz, forecast, options, data)
            if python == powershell:
                print(f"ok   {rain} {options}: {python.get('title')} / {python.get('detail')}")
            else:
                failed = True
                print(f"FAIL {rain} {options}\n  python:     {json.dumps(python)}\n  powershell: {json.dumps(powershell)}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
