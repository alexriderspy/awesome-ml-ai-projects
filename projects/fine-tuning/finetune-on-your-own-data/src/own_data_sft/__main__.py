import argparse
import json

from .prepare import Rules, build


def main() -> None:
    ap = argparse.ArgumentParser(prog="own_data_sft")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--raw", default="data/raw")
    p.add_argument("--out", default="data/processed")
    p.add_argument("--owner", default="Maya")
    t = sub.add_parser("train")
    t.add_argument("--model", default="HuggingFaceTB/SmolLM2-360M-Instruct")
    t.add_argument("--epochs", type=int, default=3)
    t.add_argument("--out", default="outputs/own-data")
    c = sub.add_parser("chat")
    c.add_argument("question")
    c.add_argument("--model", default="HuggingFaceTB/SmolLM2-360M-Instruct")
    c.add_argument("--adapter", default="outputs/own-data/adapter")
    args = ap.parse_args()

    if args.cmd == "prepare":
        print(json.dumps(build(args.raw, args.out, Rules(owner=args.owner)), indent=2))
    elif args.cmd == "train":
        from .train import TrainConfig, train

        res = train(TrainConfig(model=args.model, epochs=args.epochs, out_dir=args.out))
        print(json.dumps({k: v for k, v in res.items() if k != "log"}, indent=2))
    else:
        from .train import TrainConfig, generate, load_model

        tok, model = load_model(args.model, args.adapter or None)
        print(generate(tok, model, args.question, TrainConfig().system))


if __name__ == "__main__":
    main()
