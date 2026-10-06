import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from house_price.model import ARTIFACT, load_model, train_and_save

PLACES = {
    "Palo Alto": (37.44, -122.14),
    "San Francisco (Mission)": (37.76, -122.42),
    "Los Angeles (Downtown)": (34.05, -118.25),
    "San Diego": (32.72, -117.16),
    "Sacramento": (38.58, -121.49),
    "Fresno": (36.74, -119.79),
    "Bakersfield": (35.37, -119.02),
}

st.set_page_config(page_title="California House Price", layout="wide")


@st.cache_resource
def get_model():
    if not ARTIFACT.exists():
        with st.spinner("No saved model yet, training one (about 15 s)…"):
            train_and_save()
    return load_model()


model = get_model()
stats = model.train_stats_

st.title("California house price predictor")
st.caption("Median home value of a census block group (1990 California census). Gradient boosting with a conformal 80% band.")

sb = st.sidebar
place = sb.selectbox("Location", list(PLACES))
lat, lon = PLACES[place]
inc = sb.slider("Median income (x $10k)", 0.5, 15.0, 5.0, 0.1)
age = sb.slider("Median house age (years)", 1, 52, 25)
rooms = sb.slider("Average rooms per home", 2.0, 10.0, 5.5, 0.1)
beds = sb.slider("Average bedrooms per home", 0.5, 3.0, 1.05, 0.05)
pop = sb.slider("Block population", 100, 5000, 1200, 50)
occ = sb.slider("Average occupants per home", 1.0, 6.0, 2.8, 0.1)


def frame(**over):
    row = dict(MedInc=inc, HouseAge=age, AveRooms=rooms, AveBedrms=beds, Population=pop,
               AveOccup=occ, Latitude=lat, Longitude=lon)
    row.update(over)
    return pd.DataFrame([row])


if sb.button("Predict price", type="primary"):
    lo, p, hi = (v[0] for v in model.predict_interval(frame()))
    c1, c2, c3 = st.columns(3)
    c1.metric("Predicted median value", f"${p * 1e5:,.0f}")
    c2.metric("80% band, low", f"${lo * 1e5:,.0f}")
    c3.metric("80% band, high", f"${hi * 1e5:,.0f}")
    if p >= 4.8:
        st.info("The training data caps values at $500,001, so predictions near the top are underestimates.")

    grid = np.round(np.linspace(1, 15, 57), 2)
    X = pd.concat([frame(MedInc=g) for g in grid], ignore_index=True)
    glo, gp, ghi = model.predict_interval(X)
    df = pd.DataFrame({"income": grid * 1e4, "low": glo * 1e5, "price": gp * 1e5, "high": ghi * 1e5})
    base = alt.Chart(df).encode(x=alt.X("income:Q", title="median household income ($)", axis=alt.Axis(format="$,.0f")))
    band = base.mark_area(opacity=0.2, color="#111111").encode(y=alt.Y("low:Q", title="predicted value ($)", axis=alt.Axis(format="$,.0f")), y2="high:Q")
    line = base.mark_line(color="#111111").encode(y="price:Q")
    dot = alt.Chart(pd.DataFrame({"income": [inc * 1e4], "price": [p * 1e5]})).mark_point(size=120, filled=True, color="#c0392b").encode(x="income:Q", y="price:Q")
    st.subheader(f"Price vs. income in {place}")
    st.altair_chart((band + line + dot).properties(height=320), use_container_width=True)

    out_of_range = [f for f, v in frame().iloc[0].items() if not stats.loc[f, "min"] <= v <= stats.loc[f, "max"]]
    if out_of_range:
        st.warning(f"Outside the training range: {', '.join(out_of_range)}")
