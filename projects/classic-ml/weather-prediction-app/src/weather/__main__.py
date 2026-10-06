import argparse

from .fetch import CITIES, fetch_recent
from .model import compare, forecast_next


def main() -> None:
    ap = argparse.ArgumentParser(description="Next-day max temperature from Open-Meteo history")
    ap.add_argument("city", choices=sorted(CITIES))
    ap.add_argument("--years", type=int, default=10)
    args = ap.parse_args()

    df = fetch_recent(*CITIES[args.city], years=args.years)
    print(f"{args.city}: {len(df)} days, {df.index[0].date()} .. {df.index[-1].date()}")
    res = compare(df)
    print("MAE on the last 365 days (°C):")
    for k, v in res["mae"].items():
        print(f"  {k:12s} {v:.2f}")
    day, t = forecast_next(df, res["models"]["gbm"])
    print(f"\nlatest archived day {df.index[-1].date()}: max {df['tmax'].iloc[-1]:.1f} °C")
    print(f"forecast max for {day.date()}: {t:.1f} °C (gbm)")


if __name__ == "__main__":
    main()
