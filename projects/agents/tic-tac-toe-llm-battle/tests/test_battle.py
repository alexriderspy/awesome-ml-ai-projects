import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from run_eval import load_practice, run_games, solve_position, summarize
from ttt_battle.board import Board, IllegalMove, parse_move
from ttt_battle.game import format_game, play_game
from ttt_battle.players import LLMPlayer, MinimaxPlayer, RandomPlayer, best_moves


class FakeLLM:

    model = "fake"

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, user):
        self.calls.append((system, user))
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


class FirstFreeLLM:

    model = "first-free"

    def complete(self, system, user):
        free = user.split("Empty cells: ")[1].split("\n")[0].split(", ")
        return json.dumps({"reasoning": "lowest free cell", "move": int(free[0])})


@pytest.mark.parametrize("cells,winner", [
    ("XXX......", "X"), ("...OOO...", "O"), ("X..X..X..", "X"), ("..O.O.O..", "O"),
    ("X...X...X", "X"), ("XOXXOOOXX", None), (".........", None),
])
def test_win_detection(cells, winner):
    assert Board(cells).winner() == winner


def test_full_board_draw():
    b = Board("XOXXOOOXX")
    assert b.full() and b.over() and b.winner() is None and b.legal_moves() == []


@pytest.mark.parametrize("raw,cell", [
    (5, 5), ("5", 5), ("cell 7", 7), ("row 2 col 3", 6), ("Row: 3, Column: 1", 7),
    ("(1, 2)", 2), ({"row": 3, "col": 3}, 9), ({"cell": "4"}, 4), (8.0, 8),
])
def test_parse_move(raw, cell):
    assert parse_move(raw) == cell


@pytest.mark.parametrize("raw", [0, 10, -1, "row 4 col 1", "(0, 2)", "between 3 and 4", "", True, {"x": 1}])
def test_parse_move_rejects(raw):
    with pytest.raises(IllegalMove):
        parse_move(raw)


def test_play_rejects_occupied_and_after_win():
    b = Board("X........")
    with pytest.raises(IllegalMove, match="taken"):
        b.play(1)
    b = Board("XXX.OO...")
    with pytest.raises(IllegalMove, match="over"):
        b.play(9, "O")


def _all_games_vs(minimax_mark: str):
    def rec(b: Board):
        if b.over():
            yield b
            return
        mark = b.to_move()
        moves = best_moves(b) if mark == minimax_mark else b.legal_moves()
        for m in moves:
            nb = b.copy()
            nb.play(m, mark)
            yield from rec(nb)
    yield from rec(Board())


@pytest.mark.parametrize("mark", ["X", "O"])
def test_minimax_never_loses_exhaustive(mark):
    finals = list(_all_games_vs(mark))
    assert len(finals) > 100
    other = "O" if mark == "X" else "X"
    assert all(b.winner() != other for b in finals)


def test_minimax_vs_minimax_is_draw():
    for seed in range(5):
        rec = play_game(MinimaxPlayer(seed), MinimaxPlayer(seed + 100))
        assert rec.winner is None


def test_minimax_beats_random_often():
    wins = sum(play_game(MinimaxPlayer(s), RandomPlayer(s)).winner == "X" for s in range(30))
    assert wins >= 20


def test_practice_positions_have_one_right_answer():
    for case in load_practice():
        assert best_moves(Board(case["board"])) == [case["answer"]], case["id"]


def test_llm_reply_parsed_with_reasoning():
    llm = FakeLLM(['```json\n{"reasoning": "take the centre", "move": 5}\n```'])
    p = LLMPlayer(llm)
    prop = p.propose(Board(), "X")
    assert prop.move == 5 and prop.reasoning == "take the centre"
    assert "Empty cells: 1, 2, 3" in llm.calls[0][1]


def test_retry_with_feedback_then_legal():
    llm = FakeLLM(['{"reasoning": "x", "move": 1}', "I think 2", '{"reasoning": "ok", "move": 2}',
                   '{"move": 2}'])
    rec = play_game(MinimaxPlayer(0), LLMPlayer(llm), max_retries=2, start="X........")
    first_o = rec.moves[0]
    assert first_o.mark == "O" and first_o.cell == 2 and len(first_o.attempts) == 3
    assert "taken" in first_o.attempts[0].error and "JSON" in first_o.attempts[1].error
    assert "rejected: cell 1 is already taken" in llm.calls[1][1]


def test_forfeit_after_all_retries_fail():
    llm = FakeLLM(['{"reasoning": "nope", "move": 12}'])
    rec = play_game(LLMPlayer(llm), MinimaxPlayer(0), max_retries=2)
    assert rec.winner == "O" and rec.reason.startswith("forfeit")
    assert len(rec.moves) == 1 and rec.moves[0].illegal == 3 and len(llm.calls) == 3
    assert "forfeits" in format_game(rec)


def test_random_fallback_policy_keeps_game_going():
    llm = FakeLLM(['{"move": "row 9 col 9"}'])
    rec = play_game(LLMPlayer(llm), RandomPlayer(1), max_retries=1, policy="random")
    assert rec.reason in ("three in a row", "draw")
    assert all(m.fallback for m in rec.moves if m.mark == "X")


def test_llm_vs_llm_with_personas():
    px = LLMPlayer(FirstFreeLLM(), persona="aggressive")
    po = LLMPlayer(FirstFreeLLM(), persona="cautious")
    rec = play_game(px, po)
    assert rec.x == "first-free (aggressive)" and rec.o == "first-free (cautious)"
    assert rec.winner == "X"
    with pytest.raises(ValueError):
        LLMPlayer(FirstFreeLLM(), persona="nonsense")


def test_eval_pipeline_offline():
    games = run_games(lambda: LLMPlayer(FirstFreeLLM()), games_per_side=2, retries=2, workers=2)
    assert len(games) == 4 and all(g["illegal"] == 0 for g in games)
    positions = [solve_position(LLMPlayer(FirstFreeLLM()), c) for c in load_practice()]
    s = summarize(games, positions)
    assert s["loss_rate"] == 1.0 and s["legal"] == 1.0
    assert 0 <= s["overall"] <= 100


def test_summary_weights():
    games = [{"result": "draw", "attempts": 5, "illegal": 0, "forfeit": False}] * 2
    pos = [{"correct": True}, {"correct": False}]
    s = summarize(games, pos)
    assert s["overall"] == pytest.approx(100 * (0.6 * 1 + 0.2 * 1 + 0.2 * 0.5))
