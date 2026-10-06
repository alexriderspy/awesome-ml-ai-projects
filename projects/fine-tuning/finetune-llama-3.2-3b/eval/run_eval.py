import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finetome_sft.checks import score_case
from finetome_sft.config import load_config

CHECKS = Path(__file__).parent / "practice" / "checks.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "configs/local-smollm2-135m.toml"))
    ap.add_argument("--adapter")
    ap.add_argument("--skip-loss", action="store_true")
    ap.add_argument("--save", help="write generations to this JSON file")
    args = ap.parse_args()

    from finetome_sft.data import load_finetome, tokenize_with_mask
    from finetome_sft.train import generate, load_model, mean_loss

    cfg = load_config(args.config)
    tok, model = load_model(cfg.model, args.adapter)

    if not args.skip_loss:
        _, held = load_finetome(cfg.n_rows, cfg.n_heldout, seed=cfg.seed)
        held_ex = [e for c in held if (e := tokenize_with_mask(tok, c, cfg.max_len))]
        loss = mean_loss(model, held_ex, tok.pad_token_id)
        print(f"held-out loss {loss:.4f}  (ppl {math.exp(loss):.2f}, {len(held_ex)} examples)\n")

    cases = json.loads(CHECKS.read_text())
    scores, saved = [], []
    for case in cases:
        out = generate(tok, model, case["prompt"])
        s, results = score_case(case, out)
        scores.append(s)
        saved.append({"id": case["id"], "output": out, "score": s})
        detail = "  ".join(f"{k}={'ok' if ok else 'FAIL'}" for k, ok in results)
        print(f"{case['id']:20s} score={100 * s:5.1f}  {detail}")
    if args.save:
        Path(args.save).write_text(json.dumps(saved, indent=2))
    print(f"\nOVERALL {round(100 * sum(scores) / len(scores), 1)}/100")


if __name__ == "__main__":
    main()
