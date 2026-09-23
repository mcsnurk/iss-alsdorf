from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import hashlib
import math

from skyfield.api import EarthSatellite, load, wgs84

# Alsdorf (Städteregion Aachen), city centre
LAT = 50.876725
LON = 6.163991
ELEVATION_M = 160
TIMEZONE = ZoneInfo("Europe/Berlin")

LOOKAHEAD_DAYS = 14
MIN_ALTITUDE_DEG = 10.0
SUN_ALTITUDE_MAX_DEG = -6.0  # civil twilight or darker
SAMPLE_SECONDS = 10

TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"
OUTPUT = Path("docs/iss-alsdorf.ics")


@dataclass
class VisiblePass:
    start_utc: datetime
    end_utc: datetime
    max_utc: datetime
    start_az: float
    end_az: float
    max_alt: float
    max_az: float


def fetch_tle() -> tuple[str, str, str]:
    req = Request(TLE_URL, headers={"User-Agent": "iss-alsdorf-calendar/1.0"})
    with urlopen(req, timeout=30) as response:
        lines = [line.strip() for line in response.read().decode("utf-8").splitlines() if line.strip()]
    if len(lines) < 3:
        raise RuntimeError("CelesTrak returned no usable TLE data")
    return lines[0], lines[1], lines[2]


def direction(azimuth_deg: float) -> str:
    names = ["N", "NNO", "NO", "ONO", "O", "OSO", "SO", "SSO", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names[int((azimuth_deg + 11.25) // 22.5) % 16]


def sf_time_to_datetime(t) -> datetime:
    return t.utc_datetime().replace(tzinfo=timezone.utc)


def visible_passes() -> list[VisiblePass]:
    name, line1, line2 = fetch_tle()

    ts = load.timescale()
    satellite = EarthSatellite(line1, line2, name, ts)
    observer = wgs84.latlon(LAT, LON, elevation_m=ELEVATION_M)
    eph = load("de421.bsp")
    earth = eph["earth"]
    sun = eph["sun"]

    now = datetime.now(timezone.utc)
    # Start a little in the past so a currently running pass is not missed.
    search_start = now - timedelta(minutes=15)
    search_end = now + timedelta(days=LOOKAHEAD_DAYS)
    t0 = ts.from_datetime(search_start)
    t1 = ts.from_datetime(search_end)

    times, events = satellite.find_events(observer, t0, t1, altitude_degrees=MIN_ALTITUDE_DEG)

    passes: list[VisiblePass] = []
    current_rise = None
    current_culm = None

    for t, event in zip(times, events):
        if event == 0:
            current_rise = t
            current_culm = None
        elif event == 1 and current_rise is not None:
            current_culm = t
        elif event == 2 and current_rise is not None:
            set_t = t
            rise_dt = sf_time_to_datetime(current_rise)
            set_dt = sf_time_to_datetime(set_t)
            if set_dt <= now:
                current_rise = None
                current_culm = None
                continue

            duration = max(1, int((set_dt - rise_dt).total_seconds()))
            sample_count = max(2, math.ceil(duration / SAMPLE_SECONDS) + 1)
            offsets = [min(i * SAMPLE_SECONDS, duration) for i in range(sample_count)]
            if offsets[-1] != duration:
                offsets.append(duration)
            sample_dts = [rise_dt + timedelta(seconds=o) for o in offsets]
            sample_times = ts.from_datetimes(sample_dts)

            topo = (satellite - observer).at(sample_times)
            alt, az, _ = topo.altaz()
            sunlit = satellite.at(sample_times).is_sunlit(eph)
            sun_alt, _, _ = (earth + observer).at(sample_times).observe(sun).apparent().altaz()

            mask = (alt.degrees >= MIN_ALTITUDE_DEG) & sunlit & (sun_alt.degrees <= SUN_ALTITUDE_MAX_DEG)
            visible_indices = [i for i, ok in enumerate(mask) if bool(ok)]

            if visible_indices:
                i0, i1 = visible_indices[0], visible_indices[-1]
                visible_slice = visible_indices
                imax = max(visible_slice, key=lambda i: float(alt.degrees[i]))
                start = sample_dts[i0]
                end = sample_dts[i1] + timedelta(seconds=SAMPLE_SECONDS)
                if end > set_dt:
                    end = set_dt

                # Ensure a useful minimum event duration for calendar clients.
                if end <= start:
                    end = start + timedelta(seconds=SAMPLE_SECONDS)

                passes.append(
                    VisiblePass(
                        start_utc=start,
                        end_utc=end,
                        max_utc=sample_dts[imax],
                        start_az=float(az.degrees[i0]),
                        end_az=float(az.degrees[i1]),
                        max_alt=float(alt.degrees[imax]),
                        max_az=float(az.degrees[imax]),
                    )
                )

            current_rise = None
            current_culm = None

    return passes


def ical_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_ical_line(line: str, limit: int = 73) -> str:
    # Fold using characters, sufficient here because our values are mostly ASCII.
    chunks = []
    while len(line) > limit:
        chunks.append(line[:limit])
        line = " " + line[limit:]
    chunks.append(line)
    return "\r\n".join(chunks)


def fmt_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def stable_uid(p: VisiblePass) -> str:
    # Rounding the culmination to 10 minutes keeps the UID stable across small TLE corrections.
    epoch = int(p.max_utc.timestamp())
    rounded = epoch - (epoch % 600)
    raw = f"iss-alsdorf-{rounded}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{raw}-{digest}@iss-alsdorf"


def make_ics(passes: list[VisiblePass]) -> str:
    generated = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ISS Alsdorf//Visible Pass Calendar//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:ISS über Alsdorf",
        "X-WR-CALDESC:Sichtbare ISS-Überflüge über Alsdorf (automatisch aktualisiert)",
        "X-WR-TIMEZONE:Europe/Berlin",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]

    for p in passes:
        start_local = p.start_utc.astimezone(TIMEZONE)
        end_local = p.end_utc.astimezone(TIMEZONE)
        max_local = p.max_utc.astimezone(TIMEZONE)
        duration_min = max(1, round((p.end_utc - p.start_utc).total_seconds() / 60))

        summary = f"🛰️ ISS sichtbar – ca. {duration_min} Min."
        description = (
            f"Sichtbarer ISS-Überflug über Alsdorf\\n"
            f"Sichtbar: {start_local:%H:%M}–{end_local:%H:%M} Uhr\\n"
            f"Höchster Punkt: {max_local:%H:%M} Uhr bei {p.max_alt:.0f}° Richtung {direction(p.max_az)}\\n"
            f"Beginn: {direction(p.start_az)} ({p.start_az:.0f}°)\\n"
            f"Ende: {direction(p.end_az)} ({p.end_az:.0f}°)\\n\\n"
            f"Berechnet für Alsdorf-Stadtmitte. Sichtbarkeit kann durch Wolken und lokale Hindernisse eingeschränkt sein."
        )

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{stable_uid(p)}",
            f"DTSTAMP:{fmt_utc(generated)}",
            f"DTSTART:{fmt_utc(p.start_utc)}",
            f"DTEND:{fmt_utc(p.end_utc)}",
            f"SUMMARY:{ical_escape(summary)}",
            f"DESCRIPTION:{description}",
            "LOCATION:Alsdorf, Nordrhein-Westfalen",
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            "TRIGGER:-PT10M",
            "ACTION:DISPLAY",
            "DESCRIPTION:ISS ist in 10 Minuten sichtbar",
            "END:VALARM",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_ical_line(line) for line in lines) + "\r\n"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    passes = visible_passes()
    OUTPUT.write_text(make_ics(passes), encoding="utf-8", newline="")
    print(f"Wrote {OUTPUT} with {len(passes)} visible passes")


if __name__ == "__main__":
    main()
