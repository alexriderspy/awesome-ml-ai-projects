from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DAILY = [
    "temperature_2m_max", "temperature_2m_min", "temperature_2m_mean", "precipitation_sum",
    "wind_speed_10m_max", "shortwave_radiation_sum", "pressure_msl_mean", "relative_humidity_2m_mean",
]
RENAME = {
    "temperature_2m_max": "tmax", "temperature_2m_min": "tmin", "temperature_2m_mean": "tmean",
    "precipitation_sum": "precip", "wind_speed_10m_max": "wind", "shortwave_radiation_sum": "radiation",
    "pressure_msl_mean": "pressure", "relative_humidity_2m_mean": "humidity",
}

CITIES = {
    "London": (51.51, -0.13),
    "New York": (40.71, -74.01),
    "Delhi": (28.61, 77.21),
    "Bengaluru": (12.97, 77.59),
    "Tokyo": (35.68, 139.69),
    "Sydney": (-33.87, 151.21),
    "Chicago": (41.88, -87.63),
    "Berlin": (52.52, 13.41),
}


def parse_response(payload: dict) -> pd.DataFrame:
    df = pd.DataFrame(payload["daily"]).rename(columns=RENAME)
    df["date"] = pd.to_datetime(df.pop("time"))
    return df.set_index("date").astype(float)


def fetch_daily(lat: float, lon: float, start: str, end: str, cache_dir: Path = DATA_DIR) -> pd.DataFrame:
    cache = Path(cache_dir) / f"{lat:.2f}_{lon:.2f}_{start}_{end}.csv"
    if cache.exists():
        return pd.read_csv(cache, index_col="date", parse_dates=["date"])
    import time

    import requests

    params = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
              "daily": ",".join(DAILY), "timezone": "auto"}
    for attempt in range(4):
        r = requests.get(ARCHIVE_URL, params=params, timeout=60)
        if r.status_code != 429:
            break
        time.sleep(30 * (attempt + 1))
    r.raise_for_status()
    df = parse_response(r.json())
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache)
    return df


def fetch_recent(lat: float, lon: float, years: int = 10, lag_days: int = 7, cache_dir: Path = DATA_DIR) -> pd.DataFrame:
    end = date.today() - timedelta(days=lag_days)
    start = end.replace(year=end.year - years)
    return fetch_daily(lat, lon, start.isoformat(), end.isoformat(), cache_dir).dropna(subset=["tmax"])
