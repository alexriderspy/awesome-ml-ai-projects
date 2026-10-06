import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Pair:
    instruction: str
    response: str
    source: str


def from_faq_csv(path: str | Path) -> list[Pair]:
    with open(path, newline="") as f:
        return [Pair(r["question"], r["answer"], "faq") for r in csv.DictReader(f)]


def from_notes_md(path: str | Path) -> list[Pair]:
    pairs, title, body = [], None, []
    for line in Path(path).read_text().splitlines() + ["## "]:
        if line.startswith("## "):
            if title and "".join(body).strip():
                pairs.append(Pair(f"What are the studio notes on {title[0].lower() + title[1:]}?", " ".join(" ".join(body).split()), "notes"))
            title, body = line[3:].strip(), []
        elif title is not None:
            body.append(line)
    return pairs


CHAT_LINE = re.compile(r"^\[(\d{2}/\d{2}/\d{4}), (\d{2}:\d{2})\] ([^:]+?): (.*)$")


def from_chat_export(path: str | Path, owner: str) -> tuple[list[Pair], set[str]]:
    turns, names = [], set()
    for line in Path(path).read_text().splitlines():
        m = CHAT_LINE.match(line)
        if not m:
            continue
        speaker = re.sub(r"\s*\(.*\)\s*$", "", m.group(3)).strip()
        text = m.group(4).strip()
        is_owner = speaker == owner
        if not is_owner:
            names.add(speaker)
        if turns and turns[-1][0] == is_owner:
            turns[-1][1].append(text)
        else:
            turns.append((is_owner, [text]))
    pairs = []
    for (a_owner, a), (b_owner, b) in zip(turns, turns[1:]):
        if not a_owner and b_owner:
            pairs.append(Pair(" ".join(a), " ".join(b), "chat"))
    return pairs, names


PII_PATTERNS = [
    ("[EMAIL]", re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")),
    ("[CARD]", re.compile(r"\b(?:\d[ -]?){13,19}\b")),
    ("[PHONE]", re.compile(r"(?<!\w)(?:\+?\d{1,3}[ -]?)?(?:\(?\d{2,5}\)?[ -]?)\d{3,4}[ -]?\d{3,4}\b")),
    ("[IP]", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
]


def scrub(text: str, names: set[str] = frozenset()) -> tuple[str, Counter]:
    hits = Counter()
    for tag, pat in PII_PATTERNS:
        text, n = pat.subn(tag, text)
        hits[tag] += n
    for name in sorted(names, key=len, reverse=True):
        for part in {name, name.split()[0]}:
            text, n = re.subn(rf"\b{re.escape(part)}\b", "[NAME]", text)
            hits["[NAME]"] += n
    return text, +hits


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def shingles(text: str, k: int = 3) -> set[str]:
    w = norm(text).split()
    return {" ".join(w[i : i + k]) for i in range(max(1, len(w) - k + 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


@dataclass
class Rules:
    min_instruction_words: int = 3
    min_response_words: int = 4
    max_words: int = 300
    near_dup_threshold: float = 0.8
    val_fraction: float = 0.15
    seed: int = 0
    owner: str = "Maya"
    keep_names: list[str] = field(default_factory=lambda: ["Maya", "Tom", "Priya"])
    drop_if_contains: list[str] = field(default_factory=lambda: ["[CARD]"])


def length_ok(p: Pair, r: Rules) -> str | None:
    ni, nr = len(p.instruction.split()), len(p.response.split())
    if ni < r.min_instruction_words:
        return "instruction_too_short"
    if nr < r.min_response_words:
        return "response_too_short"
    if ni + nr > r.max_words:
        return "too_long"
    return None


def dedupe(pairs: list[Pair], threshold: float) -> tuple[list[Pair], Counter]:
    kept, seen, sh, dropped = [], set(), [], Counter()
    for p in pairs:
        key = norm(p.instruction + " || " + p.response)
        if key in seen:
            dropped["exact_duplicate"] += 1
            continue
        s = shingles(p.instruction + " " + p.response)
        if any(jaccard(s, o) >= threshold for o in sh):
            dropped["near_duplicate"] += 1
            continue
        seen.add(key)
        sh.append(s)
        kept.append(p)
    return kept, dropped


def split(pairs: list[Pair], val_fraction: float, seed: int) -> tuple[list[Pair], list[Pair]]:
    def bucket(p):
        h = hashlib.sha256(f"{seed}:{norm(p.instruction)}".encode()).hexdigest()
        return int(h[:8], 16) / 0xFFFFFFFF

    train = [p for p in pairs if bucket(p) >= val_fraction]
    val = [p for p in pairs if bucket(p) < val_fraction]
    return train, val


def to_messages(p: Pair, system: str | None = None) -> dict:
    msgs = ([{"role": "system", "content": system}] if system else []) + [
        {"role": "user", "content": p.instruction}, {"role": "assistant", "content": p.response}]
    return {"messages": msgs, "source": p.source}


def build(raw_dir: str | Path, out_dir: str | Path, rules: Rules = Rules()) -> dict:
    raw, out = Path(raw_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pairs, names = [], set()
    if (raw / "faq.csv").exists():
        pairs += from_faq_csv(raw / "faq.csv")
    if (raw / "notes.md").exists():
        pairs += from_notes_md(raw / "notes.md")
    if (raw / "chats.txt").exists():
        chat_pairs, names = from_chat_export(raw / "chats.txt", rules.owner)
        names -= set(rules.keep_names)
        pairs += chat_pairs
    report = {"ingested": Counter(p.source for p in pairs), "pii_replaced": Counter(), "dropped": Counter()}

    clean = []
    for p in pairs:
        ins, h1 = scrub(p.instruction, names)
        res, h2 = scrub(p.response, names)
        report["pii_replaced"] += h1 + h2
        p = Pair(ins, res, p.source)
        if any(t in ins + res for t in rules.drop_if_contains):
            report["dropped"]["contains_sensitive"] += 1
            continue
        if reason := length_ok(p, rules):
            report["dropped"][reason] += 1
            continue
        clean.append(p)
    clean, dup = dedupe(clean, rules.near_dup_threshold)
    report["dropped"] += dup
    train, val = split(clean, rules.val_fraction, rules.seed)
    for name, rows in (("train", train), ("val", val)):
        with open(out / f"{name}.jsonl", "w") as f:
            for p in rows:
                f.write(json.dumps(to_messages(p)) + "\n")
    report.update(kept=len(clean), train=len(train), val=len(val))
    report = {k: dict(v) if isinstance(v, Counter) else v for k, v in report.items()}
    (out / "report.json").write_text(json.dumps(report, indent=2))
    return report
