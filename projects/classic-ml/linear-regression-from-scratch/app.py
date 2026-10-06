import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from linreg.__main__ import run
from linreg.plots import fit_line, loss_curve

st.set_page_config(page_title="Linear Regression from Scratch", layout="wide")
st.title("Linear regression from scratch")
st.caption("Synthetic salary vs. years of experience. Closed form and gradient descent in NumPy, checked against scikit-learn.")

sb = st.sidebar
n = sb.number_input("Samples", 20, 5000, 200, step=20)
noise = sb.number_input("Noise (salary std)", 0, 50_000, 6000, step=1000)
lr = sb.number_input("Learning rate", 0.001, 1.0, 0.1, step=0.01, format="%.3f")
epochs = sb.number_input("Epochs", 1, 5000, 200, step=50)
seed = sb.number_input("Seed", 0, 10_000, 0)

if sb.button("Fit models", type="primary"):
    try:
        res = run(int(n), float(noise), int(seed), float(lr), int(epochs))
    except FloatingPointError as e:
        st.error(str(e))
        st.stop()
    df = pd.DataFrame(res["rows"])
    df["slope (per year)"] = df.pop("coef").str[0]
    left, right = st.columns(2)
    gd = res["models"]["gradient descent"]
    left.pyplot(loss_curve(gd.loss_history_, res["closed_form_train_mse"]))
    right.pyplot(fit_line(*res["data"], res["models"]))
    st.subheader("Held-out results")
    st.dataframe(df.style.format({"intercept": "{:,.1f}", "slope (per year)": "{:,.1f}", "test_r2": "{:.4f}", "test_rmse": "{:,.1f}"}),
                 hide_index=True, use_container_width=True)
