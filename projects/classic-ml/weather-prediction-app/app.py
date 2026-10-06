import sys
from pathlib import Path

import altair as alt
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from weather.fetch import CITIES, fetch_recent
from weather.model import compare, forecast_next

st.set_page_config(page_title="Tomorrow's Max Temperature", layout="wide")
st.title("Tomorrow's max temperature")
st.caption("Trained on 10 years of daily history from the Open-Meteo archive. "
           "The archive trails real time by about a week, so the forecast is for the day after the latest archived day.")

city = st.sidebar.selectbox("City", list(CITIES))
show_days = st.sidebar.slider("Days to show", 30, 365, 90, step=15)


@st.cache_data(show_spinner=False)
def run(city: str):
    df = fetch_recent(*CITIES[city])
    res = compare(df)
    day, t = forecast_next(df, res["models"]["gbm"])
    return df, res["mae"], res["test"], day, t


if st.sidebar.button("Forecast", type="primary"):
    with st.spinner(f"Fetching {city} history and training…"):
        df, maes, test, day, t = run(city)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"Forecast max, {day:%a %d %b %Y}", f"{t:.1f} °C",
              f"{t - df['tmax'].iloc[-1]:+.1f} °C vs. {df.index[-1]:%d %b}")
    c2.metric("Model MAE (last 365 days)", f"{maes['gbm']:.2f} °C")
    c3.metric("Persistence MAE", f"{maes['persistence']:.2f} °C")
    c4.metric("Error reduction", f"{100 * (1 - maes['gbm'] / maes['persistence']):.0f}%")

    st.subheader("Held-out year: one-day-ahead predictions")
    recent = test.tail(show_days).reset_index(names="date")
    long = recent.melt("date", ["actual", "persistence", "gbm"], var_name="series", value_name="tmax")
    colors = alt.Scale(domain=["actual", "persistence", "gbm"], range=["#111111", "#bbbbbb", "#c0392b"])
    chart = alt.Chart(long).mark_line().encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("tmax:Q", title="max temperature (°C)", scale=alt.Scale(zero=False)),
        color=alt.Color("series:N", scale=colors, legend=alt.Legend(orient="top", title=None)),
        strokeDash=alt.condition(alt.datum.series == "persistence", alt.value([4, 3]), alt.value([1, 0])),
    ).properties(height=280)
    st.altair_chart(chart, use_container_width=True)

    st.caption(f"{len(df):,} days of data, {df.index[0]:%Y-%m-%d} to {df.index[-1]:%Y-%m-%d}. "
               f"Ridge MAE {maes['ridge']:.2f} °C. Persistence = 'tomorrow's max equals today's'.")
