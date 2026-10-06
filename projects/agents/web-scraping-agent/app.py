import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from scrape_agent import run_agent
from scrape_agent.llm import OpenAICompatible

st.set_page_config(page_title="Web Scraping Agent")
st.title("Web Scraping Agent")
url = st.text_input("Start URL")
description = st.text_input("What to extract", placeholder="all product names and prices")
schema_text = st.text_area("Record schema (optional JSON Schema for one record)", height=100)
max_pages = st.slider("Max pages", 1, 10, 5)

if st.button("Extract", type="primary") and url and description:
    schema = json.loads(schema_text) if schema_text.strip() else None
    with st.spinner("Agent is fetching and extracting…"):
        res = run_agent(url, description, OpenAICompatible(), schema=schema, max_pages=max_pages)
    st.markdown(f"**{len(res.records)} records** from {len(res.pages)} page(s) in {res.steps} steps · stop: {res.stop_reason}")
    st.dataframe(pd.DataFrame(res.records, columns=list(res.schema["properties"])), use_container_width=True)
    st.download_button("Download JSON", json.dumps(res.records, indent=2), "records.json", "application/json")
    with st.expander("Schema"):
        st.json(res.schema)
    with st.expander("Tool calls"):
        st.dataframe(pd.DataFrame(res.log), use_container_width=True)
