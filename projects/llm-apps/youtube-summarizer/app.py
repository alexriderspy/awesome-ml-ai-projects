import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from yt_summarizer import fetch_transcript, summarize
from yt_summarizer.llm import OpenAICompatible

st.set_page_config(page_title="YouTube Summarizer")
st.title("YouTube Summarizer")
url = st.text_input("YouTube URL")
max_words = st.slider("Max words", 100, 600, 300, step=50)

if st.button("Summarize", type="primary") and url:
    with st.spinner("Fetching transcript…"):
        segments = fetch_transcript(url)
    with st.spinner(f"Summarizing {len(segments)} transcript lines…"):
        st.markdown(summarize(segments, OpenAICompatible(), max_words=max_words))
