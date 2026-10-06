import argparse
import json
import sys

from .checks import check, target_python
from .explain import explain, render_markdown
from .manifest import load
from .pypi import PyPIClient


def main() -> None:
    ap = argparse.ArgumentParser(description="Find problems in requirements.txt / pyproject.toml")
    ap.add_argument("path")
    ap.add_argument("--python", help="oldest Python you support (default: requires-python, else 3.11)")
    ap.add_argument("--explain", action="store_true", help="ask the LLM to explain each finding")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--offline", action="store_true", help="skip PyPI lookups that are not cached")
    ap.add_argument("--cache-dir", help="PyPI response cache (default ~/.cache/dependency-doctor)")
    args = ap.parse_args()

    manifest = load(args.path)
    py = target_python(manifest, args.python)
    findings = check(manifest, args.python, PyPIClient(args.cache_dir, offline=args.offline))
    explained = None
    if args.explain and findings:
        from .llm import OpenAICompatible

        explained, log = explain(findings, OpenAICompatible())
        print("explain: " + " | ".join(log), file=sys.stderr)

    if args.json:
        print(json.dumps({"path": args.path, "python": py, "findings": [f.to_dict() for f in findings],
                          "explanations": explained, "skipped": manifest.notes}, indent=2))
    else:
        print(render_markdown(args.path, py, findings, explained))
        for note in manifest.notes:
            print(f"\n_note: {note}_")
    sys.exit(1 if any(f.severity == "error" for f in findings) else 0)


if __name__ == "__main__":
    main()
