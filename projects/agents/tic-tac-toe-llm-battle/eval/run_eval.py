import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ttt_battle.board import Board, IllegalMove
from ttt_battle.game import GameRecord, play_game
from ttt_battle.players import LLMPlayer, MinimaxPlayer, check_move

PRACTICE = Path(__file__).parent / "practice"
WEIGHTS = {"non_loss": 0.6, "legal": 0.2, "tactics": 0.2}


def load_practice() -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(PRACTICE.glob("*.json"))]


def llm_attempts(rec: GameRecord, mark: str) -> tuple[int, int]:
    total = illegal = 0
    for m in rec.moves:
        if m.mark == mark:
            total += len(m.attempts)
            illegal += m.illegal
    return total, illegal


def solve_position(player, case: dict) -> dict:
    board = Board(case["board"])
    prop = player.propose(board.copy(), board.to_move())
    try:
        cell = check_move(board, prop.move)
        err = None
    except IllegalMove as e:
        cell, err = None, str(e)
    return {"id": case["id"], "kind": case["kind"], "answer": case["answer"], "cell": cell,
            "correct": cell == case["answer"], "error": err, "reasoning": prop.reasoning}


def summarize(games: list[dict], positions: list[dict]) -> dict:
    n = len(games)
    draws = sum(g["result"] == "draw" for g in games)
    wins = sum(g["result"] == "win" for g in games)
    losses = sum(g["result"] == "loss" for g in games)
    attempts = sum(g["attempts"] for g in games)
    illegal = sum(g["illegal"] for g in games)
    parts = {
        "non_loss": (draws + wins) / n if n else 0.0,
        "legal": 1 - illegal / attempts if attempts else 0.0,
        "tactics": sum(p["correct"] for p in positions) / len(positions) if positions else 0.0,
    }
    if not positions:
        w = {"non_loss": 0.75, "legal": 0.25, "tactics": 0.0}
    else:
        w = WEIGHTS
    overall = round(100 * sum(w[k] * parts[k] for k in w), 1)
    return {"games": n, "wins": wins, "draws": draws, "losses": losses,
            "draw_rate": draws / n if n else 0.0, "loss_rate": losses / n if n else 0.0,
            "illegal_rate": illegal / attempts if attempts else 0.0,
            "forfeits": sum(g["forfeit"] for g in games), **parts, "overall": overall}


def run_games(make_llm_player, games_per_side: int, retries: int, workers: int) -> list[dict]:
    jobs = [(side, i) for side in ("X", "O") for i in range(games_per_side)]

    def one(job):
        side, i = job
        llm_p, mm = make_llm_player(), MinimaxPlayer(seed=1000 + i * 2 + (side == "O"))
        px, po = (llm_p, mm) if side == "X" else (mm, llm_p)
        rec = play_game(px, po, max_retries=retries, policy="forfeit")
        total, illegal = llm_attempts(rec, side)
        return {"id": f"llm-as-{side}-{i + 1}", "side": side, "result": rec.result_for(side),
                "reason": rec.reason, "moves": [m.cell for m in rec.moves], "final": rec.final,
                "attempts": total, "illegal": illegal, "forfeit": rec.reason.startswith("forfeit")}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(one, jobs))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=4, help="games per side (LLM as X, LLM as O)")
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--persona", default="default")
    ap.add_argument("--no-practice", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from ttt_battle.llm import OpenAICompatible

    def make_llm_player():
        return LLMPlayer(OpenAICompatible(), persona=args.persona)

    games = run_games(make_llm_player, args.games, args.retries, args.workers)
    positions = []
    if not args.no_practice:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            positions = list(ex.map(lambda c: solve_position(make_llm_player(), c), load_practice()))
    s = summarize(games, positions)

    if args.json:
        print(json.dumps({"summary": s, "games": games, "positions": positions}, indent=2))
        return
    model = make_llm_player().name
    print(f"model: {model}   opponent: minimax (perfect)   retries: {args.retries}   policy: forfeit\n")
    for g in games:
        moves = " ".join(str(c) if c else "-" for c in g["moves"])
        print(f"{g['id']:12s} {g['result']:5s} ({g['reason']:24s}) moves={moves:18s} "
              f"illegal={g['illegal']}/{g['attempts']}")
    for p in positions:
        got = p["cell"] if p["cell"] is not None else f"illegal: {p['error']}"
        print(f"{p['id']:22s} {p['kind']:5s} answer={p['answer']} got={got}  {'ok' if p['correct'] else 'MISS'}")
    print(f"\ngames={s['games']}  wins={s['wins']}  draws={s['draws']}  losses={s['losses']}  "
          f"forfeits={s['forfeits']}")
    print(f"draw_rate={s['draw_rate']:.2f}  loss_rate={s['loss_rate']:.2f}  illegal_rate={s['illegal_rate']:.2f}")
    print(f"non_loss={s['non_loss']:.2f} (60%)  legal={s['legal']:.2f} (20%)  tactics={s['tactics']:.2f} (20%)")
    print(f"\nOVERALL {s['overall']}/100")


if __name__ == "__main__":
    main()
