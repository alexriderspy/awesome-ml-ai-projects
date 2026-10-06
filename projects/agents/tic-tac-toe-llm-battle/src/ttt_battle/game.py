import random
import time
from dataclasses import asdict, dataclass, field

from .board import Board, IllegalMove, other
from .players import check_move


@dataclass
class Attempt:
    raw: str
    reasoning: str
    error: str | None = None


@dataclass
class Move:
    ply: int
    mark: str
    player: str
    cell: int | None
    attempts: list[Attempt] = field(default_factory=list)
    fallback: bool = False
    board_after: str = ""
    seconds: float = 0.0

    @property
    def illegal(self) -> int:
        return sum(1 for a in self.attempts if a.error)


@dataclass
class GameRecord:
    x: str
    o: str
    moves: list[Move] = field(default_factory=list)
    winner: str | None = None
    reason: str = ""
    final: str = ""

    def result_for(self, mark: str) -> str:
        if self.winner is None:
            return "draw"
        return "win" if self.winner == mark else "loss"

    def to_dict(self) -> dict:
        return asdict(self)


def play_game(px, po, max_retries: int = 2, policy: str = "forfeit", start: str = "",
              seed: int | None = 0, on_move=None) -> GameRecord:
    if policy not in ("forfeit", "random"):
        raise ValueError("policy must be 'forfeit' or 'random'")
    board = Board(start) if start else Board()
    rec = GameRecord(px.name, po.name)
    rng = random.Random(seed)
    players = {"X": px, "O": po}
    history: list[str] = []

    while not board.over():
        mark = board.to_move()
        player = players[mark]
        if hasattr(player, "history"):
            player.history = list(history)
        move = Move(len(rec.moves) + 1, mark, player.name, None)
        feedback = None
        t0 = time.time()
        for _ in range(1 + max_retries):
            prop = player.propose(board.copy(), mark, feedback)
            att = Attempt(prop.raw, prop.reasoning)
            move.attempts.append(att)
            try:
                move.cell = check_move(board, prop.move)
                break
            except IllegalMove as e:
                att.error = feedback = str(e)
        move.seconds = round(time.time() - t0, 2)

        if move.cell is None:
            if policy == "forfeit":
                move.board_after = str(board)
                rec.moves.append(move)
                rec.winner, rec.reason = other(mark), "forfeit (illegal moves)"
                rec.final = str(board)
                if on_move:
                    on_move(rec, move)
                return rec
            move.cell, move.fallback = rng.choice(board.legal_moves()), True

        board.play(move.cell, mark)
        move.board_after = str(board)
        rec.moves.append(move)
        history.append(f"{mark}->{move.cell}")
        if on_move:
            on_move(rec, move)

    rec.winner = board.winner()
    rec.reason = "three in a row" if rec.winner else "draw"
    rec.final = str(board)
    return rec


def format_game(rec: GameRecord) -> str:
    out = [f"X = {rec.x}   O = {rec.o}", ""]
    for m in rec.moves:
        for a in m.attempts:
            if a.error:
                out.append(f"  [{m.mark} rejected] {a.raw.strip()[:200]!r} -> {a.error}")
        if m.cell is None:
            out.append(f"{m.ply}. {m.mark} ({m.player}) forfeits after {len(m.attempts)} illegal attempts")
            continue
        why = m.attempts[-1].reasoning
        tag = " [random fallback]" if m.fallback else ""
        out.append(f"{m.ply}. {m.mark} ({m.player}) -> {m.cell}{tag}   {m.seconds}s")
        if why:
            out.append(f"   reasoning: {why}")
        out.append("   " + Board(m.board_after).pretty().replace("\n", "\n   "))
        out.append("")
    res = "draw" if rec.winner is None else f"{rec.winner} wins ({rec.reason})"
    out.append(f"RESULT: {res}")
    return "\n".join(out)
