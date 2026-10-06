import argparse
import math
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STOP = set("a an the and or of to in on at for is are be it this that with you your we our i can do does".split())


def tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9£]+", text.lower()) if w not in STOP]


def token_f1(pred: str, ref: str) -> float:
    p, r = Counter(tokens(pred)), Counter(tokens(ref))
    common = sum((p & r).values())
    if not common:
        return 0.0
    precision, recall = common / sum(p.values()), common / sum(r.values())
    return 2 * precision * recall / (precision + recall)


def numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def score(pred: str, ref: str) -> float:
    nums = numbers(ref)
    num_ok = len(nums & numbers(pred)) / len(nums) if nums else 1.0
    return 0.7 * token_f1(pred, ref) + 0.3 * num_ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-360M-Instruct")
    ap.add_argument("--adapter")
    ap.add_argument("--val", default=str(ROOT / "data/processed/val.jsonl"))
    args = ap.parse_args()

    from own_data_sft.train import TrainConfig, encode, generate, load_model, load_rows, mean_loss, with_system

    cfg = TrainConfig()
    tok, model = load_model(args.model, args.adapter)
    rows = load_rows(args.val)
    enc = [e for m in rows if (e := encode(tok, with_system(m, cfg.system), cfg.max_len))]
    loss = mean_loss(model, enc, tok.pad_token_id)
    print(f"val loss {loss:.4f} (ppl {math.exp(loss):.2f})\n")

    scores = []
    for m in rows:
        q = next(x["content"] for x in m if x["role"] == "user")
        ref = next(x["content"] for x in m if x["role"] == "assistant")
        s = score(generate(tok, model, q, cfg.system), ref)
        scores.append(s)
        print(f"{100 * s:5.1f}  {q[:70]}")
    print(f"\nOVERALL {round(100 * sum(scores) / len(scores), 1)}/100")


if __name__ == "__main__":
    main()
