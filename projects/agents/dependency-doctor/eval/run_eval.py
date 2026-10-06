import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dep_doctor import PyPIClient, check, explain, load

PRACTICE = Path(__file__).parent / "practice"
CACHE = PRACTICE / "pypi-cache"


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def leaked_packages(explained: list[dict], manifest_names: set[str]) -> list[str]:
    leaks = []
    for e in explained:
        text = e["explanation"].lower()
        for name in manifest_names - {e["package"]}:
            if re.search(rf"(?<![\w.-]){re.escape(name)}(?![\w-])", text):
                leaks.append(f"{e['package']}->{name}")
    return leaks


def run_case(case: dict, llm=None, online: bool = False) -> dict:
    manifest = load(PRACTICE / case["file"])
    findings = check(manifest, case.get("python"), PyPIClient(CACHE, offline=not online))
    pred = {(f.code, f.package) for f in findings}
    gold = {tuple(x) for x in case["findings"]}
    p, r, f = prf(pred, gold)
    out = {"p": p, "r": r, "f1": f, "tp": len(pred & gold), "n_pred": len(pred), "n_gold": len(gold),
           "missed": sorted(gold - pred), "extra": sorted(pred - gold)}
    if llm is not None and findings:
        explained, log = explain(findings, llm)
        leaks = leaked_packages(explained, {d.name for d in manifest.deps})
        ok = log[-1].endswith("ok")
        out.update(explain_ok=ok, explain_log=log, leaks=leaks,
                   explain_score=(1.0 if ok else 0.0) * (0.0 if leaks else 1.0))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--online", action="store_true", help="fill the PyPI cache from the network")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    llm = None
    if not args.no_llm:
        from dep_doctor.llm import OpenAICompatible

        llm = OpenAICompatible()

    gold = json.loads((PRACTICE / "gold.json").read_text())
    results = {cid: run_case(case, llm, args.online) for cid, case in gold.items()}

    tp = sum(r["tp"] for r in results.values())
    n_pred = sum(r["n_pred"] for r in results.values())
    n_gold = sum(r["n_gold"] for r in results.values())
    micro_p = tp / n_pred if n_pred else 1.0
    micro_r = tp / n_gold if n_gold else 1.0
    micro_f = 2 * micro_p * micro_r / (micro_p + micro_r) if micro_p + micro_r else 0.0
    expl = [r["explain_score"] for r in results.values() if "explain_score" in r]
    if llm is None:
        overall = round(100 * micro_f, 1)
    else:
        overall = round(100 * (0.8 * micro_f + 0.2 * (sum(expl) / len(expl) if expl else 1.0)), 1)

    if args.json:
        print(json.dumps({"overall": overall, "micro": [micro_p, micro_r, micro_f], "cases": results}, indent=2, default=list))
        return
    for cid, r in results.items():
        line = f"{cid:14s} P={r['p']:.2f} R={r['r']:.2f} F1={r['f1']:.2f}  ({r['tp']}/{r['n_gold']} gold, {r['n_pred']} found)"
        if "explain_score" in r:
            line += f"  explain={'ok' if r['explain_ok'] else 'FAIL'} leaks={len(r['leaks'])}"
        if r["missed"]:
            line += f"  missed={r['missed']}"
        if r["extra"]:
            line += f"  extra={r['extra']}"
        print(line)
    print(f"\nfindings micro P={micro_p:.3f} R={micro_r:.3f} F1={micro_f:.3f}")
    if expl:
        print(f"explanations grounded: {sum(expl):.0f}/{len(expl)}")
    print(f"\nOVERALL {overall}/100" + ("  (checks only, --no-llm)" if llm is None else ""))


if __name__ == "__main__":
    main()
