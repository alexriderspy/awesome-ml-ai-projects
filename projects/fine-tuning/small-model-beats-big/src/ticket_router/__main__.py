import argparse
import json

from .data import DATA, load_jsonl, load_split, stratified_split


def main() -> None:
    ap = argparse.ArgumentParser(prog="ticket_router")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("split")
    t = sub.add_parser("train")
    t.add_argument("--model", default="HuggingFaceTB/SmolLM2-360M-Instruct")
    t.add_argument("--epochs", type=int, default=2)
    c = sub.add_parser("classify")
    c.add_argument("text")
    c.add_argument("--system", choices=["tfidf", "local", "api"], default="local")
    c.add_argument("--adapter", default="outputs/smollm2-360m-lora/adapter")
    args = ap.parse_args()

    if args.cmd == "split":
        split = stratified_split(load_jsonl(DATA / "tickets.jsonl"), n_val=13, n_test=12)
        (DATA / "splits.json").write_text(json.dumps(split, indent=1))
        print({k: len(v) for k, v in split.items()})
    elif args.cmd == "train":
        from .local_model import LocalConfig, train

        cfg = LocalConfig(model=args.model, epochs=args.epochs)
        res = train(cfg, load_split("train"), load_split("val"))
        print(json.dumps({k: v for k, v in res.items() if k != "log"}, indent=2))
    else:
        if args.system == "tfidf":
            from .baseline import train_tfidf

            rows = load_split("train")
            clf = train_tfidf([r["text"] for r in rows], [r["label"] for r in rows])
            print(clf.predict([args.text])[0])
        elif args.system == "api":
            from .api_classifier import classify_api
            from .llm import OpenAICompatible

            print(json.dumps(classify_api(OpenAICompatible(), args.text), indent=2))
        else:
            from .local_model import LocalConfig, load, predict

            tok, model = load(LocalConfig().model, args.adapter)
            print(json.dumps(predict(tok, model, [args.text])[0], indent=2))


if __name__ == "__main__":
    main()
