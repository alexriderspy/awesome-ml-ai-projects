import argparse
import json

from .game import format_game, play_game
from .players import PERSONAS, make_player

KINDS = ["llm", "minimax", "random"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Play one game of tic-tac-toe between two players")
    ap.add_argument("--x", choices=KINDS, default="llm", help="player for X (moves first)")
    ap.add_argument("--o", choices=KINDS, default="minimax", help="player for O")
    ap.add_argument("--model-x", help="LLM model for X (default LLM_MODEL_X, then LLM_MODEL)")
    ap.add_argument("--model-o", help="LLM model for O (default LLM_MODEL_O, then LLM_MODEL)")
    ap.add_argument("--persona-x", choices=sorted(PERSONAS))
    ap.add_argument("--persona-o", choices=sorted(PERSONAS))
    ap.add_argument("--retries", type=int, default=2, help="retries per turn after an illegal move")
    ap.add_argument("--policy", choices=["forfeit", "random"], default="forfeit",
                    help="what happens when all attempts are illegal")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", action="store_true", help="print the full game record as JSON")
    args = ap.parse_args()

    px = make_player(args.x, "X", seed=args.seed, model=args.model_x, persona=args.persona_x)
    po = make_player(args.o, "O", seed=args.seed + 1, model=args.model_o, persona=args.persona_o)
    rec = play_game(px, po, max_retries=args.retries, policy=args.policy, seed=args.seed)
    print(json.dumps(rec.to_dict(), indent=2) if args.json else format_game(rec))


if __name__ == "__main__":
    main()
