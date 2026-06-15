import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

LOCATION = "Princeton, TX"
BASE_TEMP_F = 32.0
LOG_PATH = Path("data/gdd-log.json")
TIMEZONE = ZoneInfo("America/Chicago")


def get_yesterday_date_string() -> str:
    today_local = datetime.now(TIMEZONE).date()
    yesterday = today_local - timedelta(days=1)
    return yesterday.isoformat()


def fetch_weatherapi_history(api_key: str, date_str: str) -> dict:
    query = urllib.parse.urlencode({
        "key": api_key,
        "q": LOCATION,
        "dt": date_str,
    })

    url = f"https://api.weatherapi.com/v1/history.json?{query}"

    with urllib.request.urlopen(url, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"WeatherAPI returned HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def calculate_gdd_base32_f(high_f: float, low_f: float) -> float:
    gdd = ((high_f + low_f) / 2.0) - BASE_TEMP_F
    return max(0.0, gdd)


def load_log() -> list:
    if not LOG_PATH.exists():
        return []

    with LOG_PATH.open("r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:
            return []
        return json.loads(content)


def save_log(log: list) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with LOG_PATH.open("w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)
        f.write("\n")


def main() -> None:
    api_key = os.environ.get("WEATHERAPI_KEY")
    if not api_key:
        raise RuntimeError("Missing WEATHERAPI_KEY environment variable")

    date_str = get_yesterday_date_string()
    data = fetch_weatherapi_history(api_key, date_str)

    day = data["forecast"]["forecastday"][0]["day"]

    high_f = float(day["maxtemp_f"])
    low_f = float(day["mintemp_f"])
    gdd = calculate_gdd_base32_f(high_f, low_f)

    new_entry = {
        "date": date_str,
        "location": LOCATION,
        "high_f": round(high_f, 2),
        "low_f": round(low_f, 2),
        "base_temp_f": BASE_TEMP_F,
        "gdd_base32_f": round(gdd, 2),
    }

    log = load_log()

    # Prevent duplicate rows if the workflow is run manually or twice in one day.
    log = [entry for entry in log if entry.get("date") != date_str]

    log.append(new_entry)

    # Sort by date and keep only the newest 30 entries.
    log = sorted(log, key=lambda entry: entry["date"])[-30:]

    save_log(log)

    rolling_total = round(
        sum(float(entry["gdd_base32_f"]) for entry in log),
        2,
    )

    print(f"Logged {date_str}: {gdd:.2f} GDD")
    print(f"High: {high_f:.2f} F")
    print(f"Low: {low_f:.2f} F")
    print(f"Rolling log count: {len(log)}")
    print(f"Rolling logged total: {rolling_total:.2f} GDD")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise