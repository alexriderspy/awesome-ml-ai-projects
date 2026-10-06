import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from extractor import SCHEMAS, extract
from extractor.llm import OpenAICompatible

SAMPLE = Path(__file__).parent / "eval/practice/receipt-supermarket-berlin.json"

st.set_page_config(page_title="Structured Extraction", layout="wide")
st.title("Structured Extraction")
inp, out = st.columns([2, 3], gap="large")
with inp:
    schema = st.selectbox("Schema", sorted(SCHEMAS), index=sorted(SCHEMAS).index("receipt"))
    text = st.text_area("Messy text", json.loads(SAMPLE.read_text())["text"], height=380)
    samples = st.slider("Extra samples for confidence", 0, 4, 2)
    go = st.button("Extract", type="primary")

if go and text.strip():
    with out:
        with st.spinner("Extracting…"):
            res = extract(text, schema, OpenAICompatible(), samples=samples)
        if not res.valid:
            st.error("No valid JSON after retries")
            st.code("\n".join(res.errors))
            st.stop()
        st.success(f"Valid {schema} after {res.attempts} attempt(s)")
        if res.errors:
            with st.expander("Validation errors the model fixed"):
                st.code("\n".join(res.errors))
        left, right = st.columns([3, 2])
        left.code(json.dumps(res.data, indent=2, ensure_ascii=False), language="json")
        right.markdown("**Field confidence**")
        right.dataframe(
            [{"field": k, "confidence": "–" if v is None else f"{v:.2f}"} for k, v in res.confidence.items()],
            hide_index=True, use_container_width=True, height=36 * (len(res.confidence) + 1),
        )
