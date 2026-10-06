import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from issue_triage import Snapshot, cost_usd, default_prices, triage
from issue_triage.llm import OpenAICompatible

st.set_page_config(page_title="Issue Triage Agent", layout="wide")
st.title("Issue Triage Agent")
st.caption("Runs against a frozen snapshot of 60 issues for `tinsel`, a fictional static site generator. "
           "Labels, duplicates and replies are recorded locally, never sent to GitHub.")

snap = Snapshot.load()
new = snap.untriaged()
number_text = st.text_input("Issue number", "37")
st.caption(f"Issues #1-#{new[0] - 1} were triaged before; #{new[0]}-#{new[-1]} are new and unlabeled.")
try:
    number = int(number_text.strip().lstrip("#"))
    issue = snap.issues[number]
except (ValueError, KeyError):
    st.error("Pick an issue number from 1 to 60.")
    st.stop()

clicked = st.button("Triage", type="primary")
left, right = st.columns([1, 1])
with left:
    st.subheader(f"#{number} {issue['title']}")
    st.caption(f"{issue['author']} · {issue['created_at'][:10]} · {issue['state']}")
    st.markdown(issue["body"])

if clicked:
    with st.spinner("Agent is working…"):
        r = triage(number, snap, OpenAICompatible())
    pin, pout = default_prices()
    usd = cost_usd(r.prompt_tokens, r.completion_tokens, pin, pout)
    with right:
        st.subheader("Agent result")
        st.markdown("**Labels:** " + (" ".join(f"`{lb}`" for lb in r.labels) or "-"))
        if r.duplicate_of:
            st.markdown(f"**Duplicate of:** #{r.duplicate_of} {snap.issues[r.duplicate_of]['title']}")
        else:
            st.markdown("**Duplicate of:** -")
        st.markdown("**Draft reply** (saved, not posted)")
        st.info(r.reply or "(no reply drafted)")
        st.caption(f"{r.steps} steps ({r.stopped}) · {r.prompt_tokens:,} prompt + {r.completion_tokens:,} "
                   f"completion tokens · \\${usd:.4f} at \\${pin}/M in, \\${pout}/M out · {r.seconds}s")
    with left:
        st.subheader("Tool trace")
        st.code("\n".join(f"[{t['step']}] {t['tool']}({json.dumps(t['args'], ensure_ascii=False)[:60]})\n      -> {t['result']}"
                          for t in r.trace), language=None)
