import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from blog_writer import httpx_fetch, write_post
from blog_writer.llm import OpenAICompatible
from blog_writer.swarm import format_event

st.set_page_config(page_title="Multi-Agent Blog Writer", layout="wide")
st.title("Multi-Agent Blog Writer")
st.caption("Admin → Researcher → Planner → Writer ⇄ Editor → Admin")
topic = st.text_input("Topic")
words = st.slider("Word budget", 300, 1200, 600, step=50)
fetch = st.checkbox("Let the Researcher read full pages", value=False)

if st.button("Write post", type="primary") and topic:
    trace: list[str] = []
    with st.status("Agents at work…", expanded=False) as status:
        res = write_post(topic, OpenAICompatible(), word_budget=words, fetch=httpx_fetch if fetch else None,
                         on_event=lambda e: (trace.append(format_event(e)), status.write(format_event(e))))
        status.update(label=f"Done: {res.stopped} after {res.steps} steps, {len(res.state['sources'])} sources, "
                            f"{res.state['revisions']} revision(s)", state="complete")
    left, right = st.columns([3, 2])
    with left:
        st.markdown(res.state.get("final") or res.state.get("draft") or "_No draft produced._")
    with right:
        st.subheader("Handoff trace")
        st.code("\n".join(trace), language="text", wrap_lines=True)
