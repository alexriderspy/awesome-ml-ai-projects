import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from pdf_chat import answer, chunk_pages, load_pages, make_retriever
from pdf_chat.llm import OpenAICompatible

SAMPLE = Path(__file__).parent / "eval/practice/observatory-handbook.pdf"


@st.cache_resource(show_spinner="Reading and indexing the PDF…")
def index(data: bytes):
    chunks = chunk_pages(load_pages(data))
    return chunks, make_retriever(chunks)


st.set_page_config(page_title="Chat with PDF", layout="wide")
st.title("Chat with PDF")
left, right = st.columns([2, 3], gap="large")
with left:
    up = st.file_uploader("PDF", type="pdf")
    data, name = (up.getvalue(), up.name) if up else (SAMPLE.read_bytes(), SAMPLE.name + " (sample)")
    chunks, retriever = index(data)
    st.caption(f"{name} · {max(c.page for c in chunks)} pages · {len(chunks)} chunks · retriever: {retriever.name}")
    question = st.text_input("Question")
    k = st.slider("Chunks to retrieve", 2, 8, 4)
    ask = st.button("Ask", type="primary")

if "history" not in st.session_state:
    st.session_state.history = []
if ask and question:
    with st.spinner("Thinking…"):
        st.session_state.history.insert(0, (question, answer(question, retriever, OpenAICompatible(), k=k)))

with right:
    for i, (q, a) in enumerate(st.session_state.history):
        st.markdown(f"**{q}**")
        st.markdown(a.text)
        if a.bad_citations:
            st.warning(f"Cited pages that were not in the retrieved excerpts: {a.bad_citations}")
        with st.expander(f"Sources: pages {', '.join(map(str, sorted({c.page for c in a.sources})))}", expanded=i == 0):
            for c in a.sources:
                st.markdown(f"**p. {c.page}** — {c.text}")
        st.divider()
