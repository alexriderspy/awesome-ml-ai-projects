import json
import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from tool_calling.agent import run_agent
from tool_calling.llm import OpenAICompatible
from tool_calling.toolbox import default_tools

st.set_page_config(page_title="Tool Calling Basics")
st.title("Tool Calling Basics")
st.caption("The model can call: calculator, unit_convert, get_weather (Open-Meteo), add_note, list_notes, search_notes.")

with st.sidebar:
    notes_path = st.text_input("Notes file", os.getenv("NOTES_PATH", "notes.json"))
    max_steps = st.slider("Max steps", 1, 10, 6)
    with st.expander("Tool schemas sent to the model"):
        st.json([t.schema for t in default_tools(notes_path)], expanded=False)

if "turns" not in st.session_state:
    st.session_state.turns = []


def show_turn(question, result):
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        st.markdown(result.answer)
        label = f"Tool-call trace: {len(result.trace)} call(s), {result.steps} model step(s)"
        with st.expander(label, expanded=True):
            if not result.trace:
                st.write("No tools called.")
            for e in result.trace:
                tag = f"step {e.step}" + (f" · parallel x{e.batch_size}" if e.batch_size > 1 else "")
                st.markdown(f"**{tag}** · `{e.tool}` {'' if e.ok else '· error'}")
                st.code(f"args:   {json.dumps(e.args, ensure_ascii=False)}\nresult: {e.result}", language="text")


for q, r in st.session_state.turns:
    show_turn(q, r)

with st.form("ask", clear_on_submit=True):
    question = st.text_input("Question", placeholder="Is it warmer in Oslo or Cairo right now?")
    asked = st.form_submit_button("Ask", type="primary")

if asked and question:
    history = []
    for q, r in st.session_state.turns:
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": r.answer}]
    with st.spinner("Thinking and calling tools…"):
        result = run_agent(question, OpenAICompatible(), default_tools(notes_path), max_steps=max_steps,
                           history=history)
    st.session_state.turns.append((question, result))
    st.rerun()
