import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from ppt_agent import build_pptx, generate_deck
from ppt_agent.llm import OpenAICompatible

st.set_page_config(page_title="PPT Generator")
st.title("PPT Generator")
topic = st.text_input("Topic")
audience = st.text_input("Audience", "software engineers")
n = st.slider("Content slides", 3, 15, 6)
with_images = st.checkbox("Add images from Wikimedia Commons")

if st.button("Generate deck", type="primary") and topic:
    with st.spinner("Planning outline and writing slides…"):
        deck, stats = generate_deck(topic, OpenAICompatible(), n_slides=n, audience=audience)
    images = {}
    tmp = Path(tempfile.mkdtemp())
    if with_images:
        from ppt_agent.images import fetch_images

        with st.spinner("Finding images…"):
            images = fetch_images(deck, tmp / "images")
    path = build_pptx(deck, tmp / "deck.pptx", images)
    st.success(f"{len(deck.content_slides())} content slides · {stats.calls} LLM calls · "
               f"{stats.first_try_valid}/{stats.steps} steps valid on first try")
    st.download_button("Download .pptx", path.read_bytes(), file_name="deck.pptx")
    st.header(deck.title)
    st.caption(deck.subtitle)
    for i, sec in enumerate(deck.sections, 1):
        st.subheader(f"{i:02d} · {sec.title}")
        for s in sec.slides:
            with st.expander(s.title, expanded=i == 1):
                st.markdown("\n".join(f"- {b}" for b in s.bullets))
                st.caption("Speaker notes: " + s.notes)
