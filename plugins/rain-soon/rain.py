"""Says when rain is coming in the next two hours, from open-meteo.com's
forecast in 15-minute steps for where you are.

Nokta runs it every 10 minutes. It sends open-meteo.com your coordinates
(and a city name, looked up once). The last alert's time is kept in the
plugin's data folder, so one shower brings one alert. rain.ps1 is the same
for Windows: change both together. RAIN_FORECAST (a saved answer) and
RAIN_NOW (Unix seconds) stand in for the network and the time now, for the
check that both scripts agree.
"""

import datetime
import json
import math
import os
import urllib.parse
import urllib.request

# Millimetres in 15 minutes: at least this much is rain.
WET = 0.1
# Up to these, light and then moderate rain; above, heavy.
LIGHT = 0.5
MODERATE = 2.0
# After an alert, none for the same shower for this long.
QUIET_MINUTES = 90
WORDS = {
    "Indonesia": {
        "kinds": ["Gerimis", "Hujan", "Hujan lebat"],
        "now": "{kind} sekarang",
        "stops": "Reda sekitar {clock}",
        "stays": "Belum reda 2 jam ke depan",
        "soon": "{kind} ±{minutes} lagi",
        "about": "Sekitar {clock}",
        "dry": "Tidak hujan 2 jam ke depan",
        "offline": "Prakiraan hujan tidak bisa dimuat",
        "city": "Atur kotamu",
        "missing": "{text} tidak ditemukan",
        "hint": "Nama kota, atau koordinat seperti -6.2,106.8",
    },
    "English": {
        "kinds": ["Drizzle", "Rain", "Heavy rain"],
        "now": "{kind} now",
        "stops": "Stops around {clock}",
        "stays": "Not stopping in the next 2 hours",
        "soon": "{kind} in about {minutes}",
        "about": "Around {clock}",
        "dry": "No rain for 2 hours",
        "offline": "Cannot load the rain forecast",
        "city": "Set your city",
        "missing": "{text} was not found",
        "hint": "A city, or coordinates like -6.2,106.8",
    },
}


def option(key, default):
    return os.environ.get("NOKTA_OPTION_" + key.upper(), default)


def number(key, default):
    try:
        return int(option(key, str(default)))
    except ValueError:
        return default


def data_file(name):
    return os.path.join(os.environ.get("NOKTA_PLUGIN_DATA", "."), name)


def fetch(url):
    with urllib.request.urlopen(url, timeout=10) as answer:
        return json.load(answer)


def place(text):
    """(latitude, longitude, name) for "lat,lon" or a city looked up once."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) == 2:
        try:
            lat, lng = float(parts[0]), float(parts[1])
            if -90 <= lat <= 90 and -180 <= lng <= 180:
                return lat, lng, f"{lat:.2f}, {lng:.2f}"
        except ValueError:
            pass
    cache = data_file("place.json")
    try:
        with open(cache, encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("query") == text:
            return saved["latitude"], saved["longitude"], saved["name"]
    except (OSError, ValueError, KeyError):
        pass
    query = urllib.parse.urlencode({"name": text, "count": 1, "format": "json"})
    found = fetch("https://geocoding-api.open-meteo.com/v1/search?" + query).get("results") or []
    if not found:
        return None
    hit = found[0]
    saved = {"query": text, "latitude": hit["latitude"], "longitude": hit["longitude"], "name": hit["name"]}
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(saved, f)
    except OSError:
        pass
    return saved["latitude"], saved["longitude"], saved["name"]


def forecast(lat, lng):
    """[(start in Unix seconds, millimetres)] for the last 15 minutes and the next two hours."""
    saved = os.environ.get("RAIN_FORECAST")
    if saved:
        with open(saved, encoding="utf-8") as f:
            body = json.load(f)
    else:
        query = urllib.parse.urlencode(
            {
                "latitude": lat,
                "longitude": lng,
                "minutely_15": "precipitation",
                "past_minutely_15": 1,
                "forecast_minutely_15": 9,
                "timeformat": "unixtime",
            }
        )
        body = fetch("https://api.open-meteo.com/v1/forecast?" + query)
    steps = body["minutely_15"]
    return [(int(t), float(mm or 0)) for t, mm in zip(steps["time"], steps["precipitation"])]


def span(minutes, english):
    h, m = divmod(minutes, 60)
    if english:
        return f"{h} h {m} min" if h else f"{m} min"
    return f"{h} jam {m} menit" if h else f"{m} menit"


def kind(words, millimetres):
    return words["kinds"][0 if millimetres < LIGHT else 1 if millimetres < MODERATE else 2]


def clock(seconds):
    return datetime.datetime.fromtimestamp(seconds).strftime("%H:%M")


def last_alert():
    try:
        with open(data_file("alert.json"), encoding="utf-8") as f:
            return int(json.load(f)["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return 0


def card(words, steps, now, city):
    current = [s for s in steps if s[0] <= now][-1:] or steps[:1]
    ahead = [s for s in steps if s[0] > now]
    out = {"icon": "nokta-weather", "tone": "blue"}
    if current and current[0][1] >= WET:
        wet = [current[0]]
        for step in ahead:
            if step[1] < WET:
                break
            wet.append(step)
        dry = next((s for s in ahead if s[1] < WET), None)
        out["title"] = words["now"].format(kind=kind(words, max(mm for _, mm in wet)))
        out["detail"] = words["stops"].format(clock=clock(dry[0])) if dry else words["stays"]
        return out, None
    start = next((i for i, s in enumerate(ahead) if s[1] >= WET), None)
    if start is None:
        out.update({"title": words["dry"], "detail": city, "tone": "gray"})
        if option("show_dry", "true") != "true":
            out["hidden"] = True
        return out, None
    shower = []
    for step in ahead[start:]:
        if step[1] < WET:
            break
        shower.append(step)
    at = ahead[start][0]
    minutes = max(1, math.ceil((at - now) / 60))
    heaviest = kind(words, max(mm for _, mm in shower))
    out["title"] = words["soon"].format(kind=heaviest, minutes=span(minutes, words is WORDS["English"]))
    out["detail"] = f"{words['about'].format(clock=clock(at))} · {city}"
    lead = number("lead_minutes", 30)
    if minutes > lead:
        return out, None
    if option("badge", "true") == "true":
        out["badge"] = f"{minutes // 60}h{minutes % 60:02d}" if minutes >= 60 else f"{minutes}m"
    if option("alert", "true") == "true" and now - last_alert() >= QUIET_MINUTES * 60:
        out["alert"] = {"id": f"rain-{at}", "title": out["title"], "detail": out["detail"]}
        return out, now
    return out, None


def main():
    language = option("language", "Indonesia")
    words = WORDS["English" if language == "English" else "Indonesia"]
    text = option("location", "Jakarta").strip()
    try:
        found = place(text) if text else None
        if not found:
            detail = words["missing"].format(text=text) if text else words["hint"]
            print(json.dumps({"title": words["city"], "detail": detail, "tone": "orange"}))
            return
        lat, lng, city = found
        steps = forecast(lat, lng)
    except (OSError, ValueError, KeyError):
        print(json.dumps({"title": words["offline"], "icon": "nokta-weather", "tone": "gray"}))
        return
    now = int(os.environ.get("RAIN_NOW") or datetime.datetime.now().timestamp())
    out, alerted = card(words, steps, now, city)
    if alerted is not None and not os.environ.get("RAIN_FORECAST"):
        try:
            with open(data_file("alert.json"), "w", encoding="utf-8") as f:
                json.dump({"at": alerted}, f)
        except OSError:
            pass
    print(json.dumps(out))


if __name__ == "__main__":
    main()
