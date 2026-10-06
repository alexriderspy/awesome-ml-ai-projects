import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from latex_ocr.metrics import exact_match, normalized_edit_distance, score


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen2-VL-2B-Instruct")
    ap.add_argument("--adapter")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--save")
    args = ap.parse_args()

    from latex_ocr.data import load_split
    from latex_ocr.infer import load, transcribe

    processor, model = load(args.model, args.adapter)
    ds = load_split(args.split, args.limit)
    preds, refs, rows = [], [], []
    for i, sample in enumerate(ds):
        pred = transcribe(processor, model, sample["image"])
        preds.append(pred)
        refs.append(sample["text"])
        ned = normalized_edit_distance(pred, sample["text"])
        rows.append({"pred": pred, "ref": sample["text"], "edit_distance": ned})
        print(f"{i:4d}  {'EM ' if exact_match(pred, sample['text']) else '   '} ned={ned:.2f}  {pred[:60]}")
    if args.save:
        Path(args.save).write_text(json.dumps(rows, indent=2))
    s = score(preds, refs)
    print(f"\nexact match {s['exact_match']:.3f}  edit distance {s['edit_distance']:.3f}  BLEU {s['bleu']:.3f}")
    print(f"OVERALL {s['overall']}/100")


if __name__ == "__main__":
    main()
