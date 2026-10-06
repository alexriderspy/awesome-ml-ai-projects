import argparse

from .documents import load_jd, load_resumes
from .llm import OpenAICompatible
from .pipeline import DEFAULT_CALENDAR, run_pipeline, write_outputs
from .scheduler import Calendar


def main() -> None:
    ap = argparse.ArgumentParser(description="Screen resumes, write interview questions, schedule interviews")
    ap.add_argument("--jd", required=True, help="job description (.md with '## Must have' / '## Nice to have')")
    ap.add_argument("--resumes", required=True, help="folder of .md/.txt resumes")
    ap.add_argument("--out", required=True, help="output folder")
    ap.add_argument("--calendar", default=str(DEFAULT_CALENDAR), help="simulated calendar JSON")
    ap.add_argument("--max-shortlist", type=int, default=3)
    ap.add_argument("--threshold", type=float, default=50.0, help="minimum fit score (0-100) to shortlist")
    args = ap.parse_args()

    llm = OpenAICompatible()
    out = run_pipeline(llm, load_jd(args.jd), load_resumes(args.resumes), Calendar.load(args.calendar),
                       args.max_shortlist, args.threshold)
    for p in write_outputs(out, args.out):
        print(f"wrote {p}")
    cost = llm.cost_usd()
    print(f"LLM calls: {llm.usage['calls']}, tokens in/out: {llm.usage['input_tokens']}/{llm.usage['output_tokens']}"
          + (f", est. cost ${cost:.4f}" if cost is not None else ""))


if __name__ == "__main__":
    main()
