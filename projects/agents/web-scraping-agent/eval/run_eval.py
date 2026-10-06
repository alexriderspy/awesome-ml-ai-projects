import argparse
import functools
import http.server
import json
import re
import sys
import threading
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SITES = Path(__file__).parent / "sites"


def norm(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    s = str(value).strip()
    if s == "":
        return None
    if re.fullmatch(r"-?[\d,]+(\.\d+)?", s):
        return round(float(s.replace(",", "")), 2)
    if s.startswith(("http://", "https://", "/")):
        return urlparse(s).path.rstrip("/").lower()
    return re.sub(r"\s+", " ", s).lower().strip(" .")


def field_f1(pred: list[dict], gold: list[dict], fields: list[str], key: str) -> dict:
    gold_by_key = {norm(g[key]): g for g in gold}
    seen, tp = set(), 0
    for p in pred:
        k = norm(p.get(key))
        if k in gold_by_key and k not in seen:
            seen.add(k)
            g = gold_by_key[k]
            tp += sum(1 for f in fields if norm(p.get(f)) == norm(g.get(f)))
    n_pred, n_gold = len(pred) * len(fields), len(gold) * len(fields)
    precision = tp / n_pred if n_pred else 0.0
    recall = tp / n_gold if n_gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"f1": f1, "precision": precision, "recall": recall, "matched": len(seen)}


def pagination_score(fetched: list[str], gold_pages: list[str], site: str) -> float:
    names = {urlparse(u).path.rsplit("/", 1)[-1] for u in fetched if f"/{site}/" in u}
    return len(names & set(gold_pages)) / len(gold_pages)


def score_site(result, case: dict, site: str) -> dict:
    fields = list(case["schema"]["properties"])
    s = field_f1(result.records, case["records"], fields, case["schema"]["key"])
    s["pagination"] = pagination_score(result.pages, case["pages"], site)
    s.update(records=len(result.records), gold=len(case["records"]), pages=len(result.pages),
             gold_pages=len(case["pages"]), steps=result.steps, stop=result.stop_reason)
    return s


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    handler = functools.partial(_Quiet, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="append", help="only these sites")
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true", help="print every tool call")
    args = ap.parse_args()

    from scrape_agent.agent import run_agent
    from scrape_agent.fetch import HttpFetcher
    from scrape_agent.llm import OpenAICompatible

    llm = OpenAICompatible(temperature=0.0)
    server, base = serve(SITES)
    results = {}
    try:
        for site_dir in sorted(p for p in SITES.iterdir() if (p / "gold.json").exists()):
            if args.site and site_dir.name not in args.site:
                continue
            case = json.loads((site_dir / "gold.json").read_text())
            url = f"{base}/{site_dir.name}/{case['start']}"
            res = run_agent(url, case["description"], llm, schema=case["schema"], fetcher=HttpFetcher(),
                            max_pages=args.max_pages, verbose=args.verbose)
            results[site_dir.name] = score_site(res, case, site_dir.name)
    finally:
        server.shutdown()

    overall = round(100 * sum(r["f1"] for r in results.values()) / len(results), 1)
    if args.json:
        print(json.dumps({"overall": overall, "sites": results}, indent=2))
        return
    for name, r in results.items():
        print(f"{name:10s} F1={r['f1']:.3f}  P={r['precision']:.2f}  R={r['recall']:.2f}  "
              f"records={r['records']}/{r['gold']}  pages={r['pages']} (pagination {r['pagination']:.2f})  "
              f"steps={r['steps']}  stop={r['stop']}")
    print(f"\nOVERALL {overall}/100")


if __name__ == "__main__":
    main()
