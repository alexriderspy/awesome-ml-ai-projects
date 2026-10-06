import httpx

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "rime fog",
    51: "light drizzle", 53: "drizzle", 55: "dense drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "rain showers", 81: "rain showers", 82: "violent rain showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}


class WeatherError(RuntimeError):
    pass


def current_weather(city: str, client: httpx.Client | None = None) -> dict:
    own = client is None
    client = client or httpx.Client(timeout=15)
    try:
        geo = client.get(GEOCODE_URL, params={"name": city, "count": 1, "language": "en", "format": "json"})
        geo.raise_for_status()
        results = geo.json().get("results") or []
        if not results:
            raise WeatherError(f"no place called {city!r} found")
        place = results[0]
        fc = client.get(FORECAST_URL, params={
            "latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto",
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        })
        fc.raise_for_status()
        cur = fc.json()["current"]
    finally:
        if own:
            client.close()
    return {
        "city": place["name"],
        "country": place.get("country", ""),
        "local_time": cur["time"],
        "temperature_c": cur["temperature_2m"],
        "humidity_pct": cur["relative_humidity_2m"],
        "wind_kmh": cur["wind_speed_10m"],
        "conditions": WMO.get(cur["weather_code"], f"code {cur['weather_code']}"),
    }
