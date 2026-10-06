import argparse
import json
from pathlib import Path

from .config import load_config


def main() -> None:
    ap = argparse.ArgumentParser(prog="finetome_sft")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("train")
    t.add_argument("--config", required=True)
    t.add_argument("--demo-dir", default="demo")
    g = sub.add_parser("generate")
    g.add_argument("prompt")
    g.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M-Instruct")
    g.add_argument("--adapter")
    s = sub.add_parser("show")
    s.add_argument("n", type=int, nargs="?", default=2)
    args = ap.parse_args()

    if args.cmd == "train":
        from .train import plot_loss, train

        cfg = load_config(args.config)
        checks = json.loads((Path(__file__).resolve().parents[2] / "eval/practice/checks.json").read_text())
        prompts = [c["prompt"] for c in checks[:4]]
        res = train(cfg, sample_prompts=prompts)
        demo = Path(args.demo_dir)
        demo.mkdir(exist_ok=True)
        plot_loss(res["log"], demo / "loss_curve.png", f"LoRA SFT on FineTome-100k slice · {cfg.model} · {res['device']}")
        (demo / "train_result.json").write_text(json.dumps({k: v for k, v in res.items() if k != "samples"}, indent=2))
        lines = [f"# Before / after samples\n\nModel `{cfg.model}`, {cfg.max_steps} LoRA steps on {res['device']}. Greedy decoding.\n"]
        for s_ in res["samples"]:
            lines += [f"## Prompt\n\n{s_['prompt']}\n", f"**Before**\n\n```\n{s_['before']}\n```\n", f"**After**\n\n```\n{s_['after']}\n```\n"]
        (demo / "samples_before_after.md").write_text("\n".join(lines))
    elif args.cmd == "generate":
        from .train import generate, load_model

        tok, model = load_model(args.model, args.adapter)
        print(generate(tok, model, args.prompt))
    else:
        from .data import load_finetome

        convs, _ = load_finetome(args.n + 1, 1)
        print(json.dumps(convs[: args.n], indent=2)[:4000])


if __name__ == "__main__":
    main()
