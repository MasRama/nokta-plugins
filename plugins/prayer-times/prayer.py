"""The five daily prayer times, worked out on this computer from where you are.

Nokta runs it every minute. The times come from the sun's position (the
method of praytimes.org): Fajr and Isha by the sun's angle under the
horizon, which differs by method, Asr by the length of a shadow. Only a
city name is looked up, once, on open-meteo.com; coordinates need nothing.
prayer.ps1 is the same for Windows: change both together. PRAYER_NOW
(YYYY-MM-DDTHH:MM) stands in for the time now, for the check that both
scripts agree.
"""

import datetime
import json
import math
import os
import urllib.parse
import urllib.request

# Fajr angle, Isha angle (or minutes after Maghrib), minutes added to each time.
METHODS = {
    "Kemenag (Indonesia)": (20.0, 18.0, None, 2),
    "JAKIM (Malaysia)": (20.0, 18.0, None, 0),
    "Muslim World League": (18.0, 17.0, None, 0),
    "Umm al-Qura (Makkah)": (18.5, None, 90, 0),
    "Egypt": (19.5, 17.5, None, 0),
    "ISNA (North America)": (15.0, 15.0, None, 0),
}
DEFAULT_METHOD = "Kemenag (Indonesia)"
NAMES = {
    "Indonesia": ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"],
    "English": ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"],
}
# Late by up to this much (the computer slept), the alert still comes.
LATE_MINUTES = 10


def option(key, default):
    return os.environ.get("NOKTA_OPTION_" + key.upper(), default)


def number(key, default):
    try:
        return int(option(key, str(default)))
    except ValueError:
        return default


def sin(d):
    return math.sin(math.radians(d))


def cos(d):
    return math.cos(math.radians(d))


def tan(d):
    return math.tan(math.radians(d))


def asin(x):
    return math.degrees(math.asin(x))


def acos(x):
    return math.degrees(math.acos(x))


def atan2(y, x):
    return math.degrees(math.atan2(y, x))


def sun(jd):
    """The sun's declination and the equation of time (hours) on Julian day jd."""
    d = jd - 2451545.0
    g = (357.529 + 0.98560028 * d) % 360
    q = (280.459 + 0.98564736 * d) % 360
    ecl = (q + 1.915 * sin(g) + 0.020 * sin(2 * g)) % 360
    e = 23.439 - 0.00000036 * d
    ra = (atan2(cos(e) * sin(ecl), cos(ecl)) / 15) % 24
    return asin(sin(e) * sin(ecl)), q / 15 - ra


def julian(day):
    y, m = day.year, day.month
    if m <= 2:
        y, m = y - 1, m + 12
    a = y // 100
    b = 2 - a + a // 4
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + day.day + b - 1524.5


def times(day, lat, lng, method, hanafi):
    """The five times on `day`, as hours after midnight UTC (may be under 0)."""
    fajr_angle, isha_angle, isha_minutes, extra = METHODS[method]
    jd = julian(day) - lng / 360

    def noon(hour):
        return (12 - sun(jd + hour / 24)[1]) % 24

    def angle_time(angle, hour, before_noon):
        decl = sun(jd + hour / 24)[0]
        cos_t = (-sin(angle) - sin(decl) * sin(lat)) / (cos(decl) * cos(lat))
        t = acos(max(-1.0, min(1.0, cos_t))) / 15
        return noon(hour) + (-t if before_noon else t)

    def asr(hour):
        decl = sun(jd + hour / 24)[0]
        angle = -math.degrees(math.atan(1 / ((2 if hanafi else 1) + tan(abs(lat - decl)))))
        return angle_time(angle, hour, False)

    fajr = angle_time(fajr_angle, 5, True)
    dhuhr = noon(12)
    asr_time = asr(13)
    maghrib = angle_time(0.833, 18, False)
    isha = maghrib + isha_minutes / 60 if isha_minutes else angle_time(isha_angle, 18, False)
    return [t - lng / 15 + extra / 60 for t in (fajr, dhuhr, asr_time, maghrib, isha)]


def moments(day, lat, lng, method, hanafi):
    """The five times on `day` as this computer's local datetimes, to the minute."""
    midnight = datetime.datetime(day.year, day.month, day.day, tzinfo=datetime.timezone.utc)
    out = []
    for hours in times(day, lat, lng, method, hanafi):
        at = midnight + datetime.timedelta(minutes=round(hours * 60))
        out.append(at.astimezone().replace(tzinfo=None))
    return out


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
    cache = os.path.join(os.environ.get("NOKTA_PLUGIN_DATA", "."), "place.json")
    try:
        with open(cache, encoding="utf-8") as f:
            saved = json.load(f)
        if saved.get("query") == text:
            return saved["latitude"], saved["longitude"], saved["name"]
    except (OSError, ValueError, KeyError):
        pass
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": text, "count": 1, "format": "json"}
    )
    with urllib.request.urlopen(url, timeout=10) as answer:
        found = json.load(answer).get("results") or []
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


def until(minutes, english):
    h, m = divmod(minutes, 60)
    if english:
        return f"in {h} h {m} min" if h else f"in {m} min"
    return f"{h} jam {m} menit lagi" if h else f"{m} menit lagi"


def card(now, lat, lng, city):
    language = option("language", "Indonesia")
    english = language == "English"
    names = NAMES["English" if english else "Indonesia"]
    method = option("method", DEFAULT_METHOD)
    if method not in METHODS:
        method = DEFAULT_METHOD
    hanafi = option("asr", "Shafi'i") == "Hanafi"
    today = moments(now.date(), lat, lng, method, hanafi)
    tomorrow = moments(now.date() + datetime.timedelta(days=1), lat, lng, method, hanafi)
    upcoming = [(n, t) for n, t in zip(names, today) if t > now] or [(names[0], tomorrow[0])]
    name, at = upcoming[0]
    left = math.ceil((at - now).total_seconds() / 60)
    clock = at.strftime("%H:%M")
    out = {
        "title": f"{name} {clock} · {until(left, english)}",
        "detail": " · ".join(f"{n} {t:%H:%M}" for n, t in zip(names, today)),
        "icon": "nokta-alarm",
        "tone": "teal",
        "items": [{"title": n, "detail": f"{t:%H:%M}"} for n, t in zip(names, today)],
    }
    badge_minutes = number("badge_minutes", 30)
    if 0 < left <= badge_minutes:
        out["badge"] = f"{left // 60}h{left % 60:02d}" if left >= 60 else f"{left}m"
    # The time just came: once per prayer and day.
    if option("alert", "true") == "true":
        for n, t in zip(names, today):
            late = (now - t).total_seconds() / 60
            if 0 <= late < LATE_MINUTES:
                title = f"Time for {n}" if english else f"Waktunya {n}"
                out["alert"] = {"id": f"{t:%Y-%m-%d}-{n}", "title": title, "detail": f"{t:%H:%M} · {city}"}
    remind = number("remind_minutes", 0)
    if "alert" not in out and 0 < remind and left <= remind:
        title = f"{name} {until(left, english)}"
        out["alert"] = {"id": f"{at:%Y-%m-%d}-{name}-soon", "title": title, "detail": f"{clock} · {city}"}
    return out


def main():
    text = option("location", "Jakarta").strip()
    english = option("language", "Indonesia") == "English"
    try:
        found = place(text) if text else None
    except OSError:
        print(json.dumps({"title": "Cannot look up the city" if english else "Kota tidak bisa dicari",
                          "detail": "No connection; or set coordinates like -6.2,106.8" if english
                          else "Tidak ada koneksi; atau isi koordinat seperti -6.2,106.8", "tone": "orange"}))
        return
    if not found:
        print(json.dumps({"title": "Set your city" if english else "Atur kotamu",
                          "detail": f"{text} was not found" if text and english
                          else f"{text} tidak ditemukan" if text
                          else "A city, or coordinates like -6.2,106.8" if english
                          else "Nama kota, atau koordinat seperti -6.2,106.8", "tone": "orange"}))
        return
    lat, lng, city = found
    fixed = os.environ.get("PRAYER_NOW")
    now = datetime.datetime.strptime(fixed, "%Y-%m-%dT%H:%M") if fixed else datetime.datetime.now()
    print(json.dumps(card(now.replace(second=0, microsecond=0), lat, lng, city)))


if __name__ == "__main__":
    main()
