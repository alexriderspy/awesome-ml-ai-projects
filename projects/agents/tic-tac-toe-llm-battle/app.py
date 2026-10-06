import os
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent / "src"))
from ttt_battle.game import play_game
from ttt_battle.players import PERSONAS, make_player

KINDS = ["llm", "minimax", "random"]


def grid(cells: str, last: int | None = None, size: int = 64) -> str:
    tds = []
    for i, c in enumerate(cells):
        bg = "#111111" if last == i + 1 else "#FFFFFF"
        fg = "#FFFFFF" if last == i + 1 else ("#111111" if c != "." else "#BBBBBB")
        txt = c if c != "." else str(i + 1)
        weight = 700 if c != "." else 400
        tds.append(f"<td style='width:{size}px;height:{size}px;text-align:center;border:2px solid #111;"
                   f"background:{bg};color:{fg};font-size:{size // 2}px;font-weight:{weight}'>{txt}</td>")
    rows = "".join("<tr>" + "".join(tds[r * 3:r * 3 + 3]) + "</tr>" for r in range(3))
    return f"<table style='border-collapse:collapse;margin:4px 0'>{rows}</table>"


def player_controls(side: str, default_kind: str):
    kind = st.selectbox(f"Player {side}", KINDS, index=KINDS.index(default_kind), key=f"kind_{side}")
    model = persona = None
    if kind == "llm":
        model = st.text_input(f"Model {side}", os.getenv(f"LLM_MODEL_{side}") or os.getenv("LLM_MODEL", "llama3.2"),
                              key=f"model_{side}")
        persona = st.selectbox(f"Persona {side}", list(PERSONAS), key=f"persona_{side}")
    return kind, model, persona


st.set_page_config(page_title="Tic-Tac-Toe LLM Battle", layout="wide")
st.title("Tic-Tac-Toe LLM Battle")
st.caption("Two players take turns. Illegal LLM moves get feedback and a retry; after all retries fail, that player forfeits.")

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    kx, mx, px_persona = player_controls("X", "llm")
with c2:
    ko, mo, po_persona = player_controls("O", "minimax")
with c3:
    retries = st.number_input("Retries per turn", 0, 5, 2)
    seed = st.number_input("Seed (minimax / random tie-breaks)", 0, 10_000, 7)

if st.button("Play game", type="primary"):
    px = make_player(kx, "X", seed=int(seed), model=mx, persona=px_persona)
    po = make_player(ko, "O", seed=int(seed) + 1, model=mo, persona=po_persona)
    live = st.empty()

    def show_live(rec, move):
        live.markdown(f"**Move {move.ply}: {move.mark} -> {move.cell}**" + grid(move.board_after, move.cell),
                      unsafe_allow_html=True)

    with st.spinner(f"{px.name} (X) vs {po.name} (O)…"):
        st.session_state.rec = play_game(px, po, max_retries=int(retries), seed=int(seed), on_move=show_live)
    live.empty()

rec = st.session_state.get("rec")
if rec:
    result = "Draw" if rec.winner is None else f"{rec.winner} wins ({rec.reason})"
    left, right = st.columns([1, 2])
    with left:
        st.subheader(f"Result: {result}")
        st.markdown(f"**X** = {rec.x}  \n**O** = {rec.o}")
        st.markdown(grid(rec.final, rec.moves[-1].cell if rec.moves else None, size=56), unsafe_allow_html=True)
        illegal = sum(m.illegal for m in rec.moves)
        st.caption(f"{len(rec.moves)} moves · {illegal} rejected attempts")
    with right:
        st.subheader("Move log")
        for m in rec.moves:
            a, b = st.columns([1, 4])
            with a:
                st.markdown(grid(m.board_after, m.cell, size=28), unsafe_allow_html=True)
            with b:
                if m.cell is None:
                    st.markdown(f"**{m.ply}. {m.mark}** ({m.player}) forfeits after {m.illegal} illegal attempts")
                else:
                    tag = " · random fallback" if m.fallback else ""
                    st.markdown(f"**{m.ply}. {m.mark} → {m.cell}** · {m.player} · {m.seconds}s{tag}")
                    if m.attempts[-1].reasoning:
                        st.markdown(f"_{m.attempts[-1].reasoning}_")
                for att in m.attempts:
                    if att.error:
                        st.markdown(f"rejected: `{att.raw.strip()[:120]}` → {att.error}")
                with st.expander("raw reply"):
                    st.code(m.attempts[-1].raw, language="json")
