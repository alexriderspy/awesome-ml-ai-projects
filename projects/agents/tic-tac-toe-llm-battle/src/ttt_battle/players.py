import os
import random
from dataclasses import dataclass
from functools import lru_cache

from .board import EMPTY, Board, IllegalMove, parse_move
from .llm import parse_json


@dataclass
class Proposal:
    move: object
    reasoning: str = ""
    raw: str = ""


@lru_cache(maxsize=None)
def _value(cells: str) -> int:
    b = Board(cells)
    empties = cells.count(EMPTY)
    if b.winner():
        return -(empties + 1)
    if empties == 0:
        return 0
    mark = b.to_move()
    best = -100
    for m in b.legal_moves():
        child = cells[:m - 1] + mark + cells[m:]
        best = max(best, -_value(child))
    return best


def best_moves(board: Board) -> list[int]:
    cells, mark = str(board), board.to_move()
    scored = {m: -_value(cells[:m - 1] + mark + cells[m:]) for m in board.legal_moves()}
    top = max(scored.values())
    return [m for m, v in scored.items() if v == top]


class MinimaxPlayer:

    def __init__(self, seed: int | None = 0):
        self.name = "minimax"
        self.rng = random.Random(seed)

    def propose(self, board: Board, mark: str, feedback: str | None = None) -> Proposal:
        moves = best_moves(board)
        m = self.rng.choice(moves)
        v = -_value(str(board)[:m - 1] + mark + str(board)[m:])
        outcome = "win" if v > 0 else "draw" if v == 0 else "loss"
        return Proposal(m, f"search: best moves {moves}, value {v} ({outcome} with perfect play)", str(m))


class RandomPlayer:
    def __init__(self, seed: int | None = 0):
        self.name = "random"
        self.rng = random.Random(seed)

    def propose(self, board: Board, mark: str, feedback: str | None = None) -> Proposal:
        m = self.rng.choice(board.legal_moves())
        return Proposal(m, "random legal move", str(m))


PERSONAS = {
    "default": "You are a careful tic-tac-toe player.",
    "aggressive": "You are an aggressive tic-tac-toe player. You look for forks and attacking moves, "
                  "but you never ignore an immediate threat.",
    "cautious": "You are a cautious tic-tac-toe player. Your first priority is never to lose: "
                "block every threat, then aim for a draw or a win.",
}

RULES = """Cells are numbered 1-9, left to right, top to bottom:
 1 | 2 | 3
---+---+---
 4 | 5 | 6
---+---+---
 7 | 8 | 9
Three in a row (row, column or diagonal) wins. You may only play an empty cell.
Before answering: check if you can win now, then check if the opponent threatens to win next move and block it.
Reply with JSON only: {"reasoning": "<one or two short sentences>", "move": <cell number 1-9>}"""


def _prompt(board: Board, mark: str, history: list[str]) -> str:
    free = ", ".join(str(m) for m in board.legal_moves())
    lines = [
        f"You play {mark}. The opponent plays {'O' if mark == 'X' else 'X'}.",
        "Current board (numbers are empty cells):",
        board.pretty(),
        f"Empty cells: {free}",
    ]
    if history:
        lines.append("Moves so far: " + "; ".join(history))
    lines.append(f"Your move as {mark}.")
    return "\n".join(lines)


class LLMPlayer:
    def __init__(self, llm, persona: str = "default", name: str | None = None):
        if persona not in PERSONAS:
            raise ValueError(f"unknown persona {persona!r}; choose from {sorted(PERSONAS)}")
        self.llm = llm
        self.persona = persona
        model = getattr(llm, "model", "llm")
        self.name = name or (model if persona == "default" else f"{model} ({persona})")
        self.history: list[str] = []

    def propose(self, board: Board, mark: str, feedback: str | None = None) -> Proposal:
        system = PERSONAS[self.persona] + "\n" + RULES
        user = _prompt(board, mark, self.history)
        if feedback:
            user += f"\n\nYour previous answer was rejected: {feedback}\nPick one of the empty cells listed above."
        raw = self.llm.complete(system, user)
        try:
            data = parse_json(raw)
            if not isinstance(data, dict) or "move" not in data:
                raise ValueError("no 'move' key")
        except ValueError:
            return Proposal(_Unreadable(raw), "", raw)
        return Proposal(data["move"], str(data.get("reasoning", "")).strip(), raw)


class _Unreadable:

    def __init__(self, raw: str):
        self.raw = raw

    def __str__(self) -> str:
        return "reply was not JSON with a 'move' key"


def check_move(board: Board, move) -> int:
    if isinstance(move, _Unreadable):
        raise IllegalMove('reply was not JSON like {"reasoning": "...", "move": 5}')
    cell = parse_move(move)
    if board.cells[cell - 1] != EMPTY:
        raise IllegalMove(f"cell {cell} is already taken by {board.cells[cell - 1]}")
    return cell


def make_player(kind: str, side: str, seed: int | None = 0, llm=None,
                model: str | None = None, persona: str | None = None):
    if kind == "minimax":
        return MinimaxPlayer(seed)
    if kind == "random":
        return RandomPlayer(seed)
    if kind == "llm":
        if llm is None:
            from .llm import OpenAICompatible
            llm = OpenAICompatible(model=model or os.getenv(f"LLM_MODEL_{side}") or None)
        return LLMPlayer(llm, persona=persona or os.getenv(f"LLM_PERSONA_{side}") or "default")
    raise ValueError(f"unknown player kind {kind!r}")
