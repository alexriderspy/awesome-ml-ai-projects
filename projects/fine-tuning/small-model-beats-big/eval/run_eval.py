import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ticket_router.data import load_split
from ticket_router.labels import LABELS
from ticket_router.metrics import accuracy, confusion, macro_f1, percentile

PRED_DIR = ROOT / "demo" / "predictions"
NAMES = {"tfidf": "TF-IDF + logistic regression", "base": "SmolLM2-360M-Instruct, no fine-tune",
         "local": "SmolLM2-360M-Instruct + LoRA", "api": "deepseek-flash zero-shot"}


def run_tfidf(test):
    from ticket_router.baseline import train_tfidf

    tr = load_split("train")
    clf = train_tfidf([r["text"] for r in tr], [r["label"] for r in tr])
    out = []
    for r in test:
        t0 = time.perf_counter()
        p = clf.predict([r["text"]])[0]
        out.append({"pred": p, "latency_s": time.perf_counter() - t0, "cost_usd": 0.0})
    return out


def run_small(test, adapter):
    from ticket_router.local_model import LocalConfig, load, predict

    tok, model = load(LocalConfig().model, adapter)
    predict(tok, model, [test[0]["text"]])
    return predict(tok, model, [r["text"] for r in test])


def run_api(test, model_name):
    from ticket_router.api_classifier import classify_api
    from ticket_router.llm import OpenAICompatible

    llm = OpenAICompatible(model=model_name, temperature=0.0)
    with ThreadPoolExecutor(8) as ex:
        return list(ex.map(lambda r: classify_api(llm, r["text"]), test))


def summarise(test, preds):
    gold = [r["label"] for r in test]
    pred = [p["pred"] for p in preds]
    lat = [p["latency_s"] for p in preds]
    return {
        "accuracy": accuracy(gold, pred), "macro_f1": macro_f1(gold, pred),
        "invalid": sum(p is None for p in pred), "p50_ms": 1000 * percentile(lat, 50), "p95_ms": 1000 * percentile(lat, 95),
        "cost_per_1k": 1000 * sum(p.get("cost_usd", 0.0) for p in preds) / len(preds),
        "confusion": confusion(gold, pred),
    }


def plot_confusions(results: dict, path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    keys = list(results)
    fig, axes = plt.subplots(1, len(keys), figsize=(4.2 * len(keys), 4.4), dpi=110)
    axes = [axes] if len(keys) == 1 else axes
    short = [l[:8] for l in LABELS] + ["invalid"]
    for ax, k in zip(axes, keys):
        m = results[k]["confusion"]
        ax.imshow(m, cmap="Greys")
        for i, row in enumerate(m):
            for j, v in enumerate(row):
                if v:
                    ax.text(j, i, v, ha="center", va="center", fontsize=7, color="white" if v > 6 else "black")
        ax.set_xticks(range(len(short)), short, rotation=90, fontsize=7)
        ax.set_yticks(range(len(LABELS)), short[:-1], fontsize=7)
        ax.set_title(f"{NAMES[k]}\nacc {results[k]['accuracy']:.2f}", fontsize=8)
    fig.supxlabel("predicted", fontsize=8)
    fig.supylabel("true", fontsize=8)
    fig.tight_layout()
    fig.savefig(path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="tfidf,base,local,api")
    ap.add_argument("--adapter", default=str(ROOT / "outputs/smollm2-360m-lora/adapter"))
    ap.add_argument("--api-model", default="deepseek-flash")
    args = ap.parse_args()

    test = load_split("test")
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    for s in args.systems.split(","):
        preds = {"tfidf": lambda: run_tfidf(test), "base": lambda: run_small(test, None),
                 "local": lambda: run_small(test, args.adapter), "api": lambda: run_api(test, args.api_model)}[s]()
        with open(PRED_DIR / f"{s}.jsonl", "w") as f:
            for r, p in zip(test, preds):
                f.write(json.dumps({"id": r["id"], "label": r["label"], **p}) + "\n")

    results = {}
    for s in NAMES:
        path = PRED_DIR / f"{s}.jsonl"
        if path.exists():
            preds = [json.loads(l) for l in path.read_text().splitlines()]
            results[s] = summarise(test, preds)

    for s, r in results.items():
        print(f"{s:6s} acc={r['accuracy']:.3f}  macroF1={r['macro_f1']:.3f}  invalid={r['invalid']}  "
              f"p50={r['p50_ms']:.0f}ms  p95={r['p95_ms']:.0f}ms  $/1k={r['cost_per_1k']:.4f}")
    lines = ["| System | Accuracy | Macro-F1 | Invalid | p50 latency | p95 latency | Cost / 1k tickets |", "|---|---|---|---|---|---|---|"]
    for s, r in results.items():
        lines.append(f"| {NAMES[s]} | {r['accuracy']:.3f} | {r['macro_f1']:.3f} | {r['invalid']} | {r['p50_ms']:.0f} ms | {r['p95_ms']:.0f} ms | ${r['cost_per_1k']:.4f} |")
    (ROOT / "demo" / "comparison.md").write_text(f"Test split: {len(test)} tickets, 12 per category.\n\n" + "\n".join(lines) + "\n")
    plot_confusions(results, ROOT / "demo" / "confusion.png")
    if "local" in results:
        print(f"\nOVERALL {round(100 * results['local']['accuracy'], 1)}/100")


if __name__ == "__main__":
    main()
