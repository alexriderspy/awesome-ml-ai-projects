import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from stock_research import DISCLAIMER, FixtureSource, YFinanceSource, run
from stock_research.agent import trace_markdown
from stock_research.llm import OpenAICompatible

st.set_page_config(page_title="Stock Research Agent")
st.title("Stock Research Agent")
st.caption(DISCLAIMER)
tickers = st.text_input("Tickers (space separated)", "KO PEP")
focus = st.text_input("Focus (optional)", "")
offline = st.checkbox("Use saved fixtures instead of live yfinance data", value=False)

if st.button("Compare", type="primary") and tickers.strip():
    source = FixtureSource(Path(__file__).parent / "eval" / "fixtures") if offline else YFinanceSource()
    log: list[str] = []
    with st.spinner("Agent is calling tools…"):
        res = run(tickers.split(), OpenAICompatible(), source, request=focus, log=log.append)
    st.markdown(res.report)
    with st.expander(f"Tool calls ({len(res.trace)}) · repairs {res.repairs} · tokens {res.prompt_tokens + res.completion_tokens}"):
        st.markdown(trace_markdown(res))
        st.code("\n".join(log))
