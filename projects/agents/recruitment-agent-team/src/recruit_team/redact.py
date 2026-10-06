import re
from collections import Counter
from dataclasses import dataclass, field

FIELD_KEYS = (
    "full name", "name", "age", "date of birth", "d\\.?o\\.?b\\.?", "born", "birthday", "birth date",
    "place of birth", "gender", "sex", "pronouns?", "marital status", "civil status", "family status",
    "family", "nationality", "citizenship", "religion", "ethnicity", "race", "photo", "photograph",
    "picture", "headshot", "children", "dependents", "kids", "home address", "address", "height", "weight",
)
FIELD_RE = re.compile(rf"^\s*(?:[-*]\s*)?\**\s*({'|'.join(FIELD_KEYS)})\s*\**\s*[:|]\s*(.*)$", re.I)
PHOTO_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)|\[\s*photo[^\]]*\]|\(photo[^)]*\)|\.(?:jpe?g|png|gif|webp|heic)\b", re.I)

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RE = re.compile(r"https?://\S+|\b(?:www\.)?(?:linkedin|github|gitlab|twitter|x)\.com/\S+", re.I)
PHONE_RE = re.compile(r"(?<![\w-])\+?\(?\d[\d\s().-]{7,}\d")

HONORIFIC_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Mx|Mister|Madam|Mme|Mlle|Miss|Sir)\b\.?\s*")

AGE_RES = [
    re.compile(r"\b\d{1,2}\s*-?\s*(?:years?|yrs?)\s*-?\s*old\b", re.I),
    re.compile(r"\b\d{1,2}\s*y/o\b", re.I),
    re.compile(r"\baged?\s*:?\s*\d{1,2}\b", re.I),
    re.compile(r"\bborn\s+(?:in|on)\s+[^.,;\n]+", re.I),
    re.compile(r"\bin my (?:twenties|thirties|forties|fifties|sixties|\d0s)\b", re.I),
]
GRAD_RES = [
    re.compile(r"\bclass of\s+'?\d{2,4}\b", re.I),
    re.compile(r"\b(graduat(?:ed|ing|ion)(?:\s+(?:in|year))?:?\s+)(?:19|20)\d{2}\b", re.I),
]
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
EDU_HEADER_RE = re.compile(r"educat|academic|qualification|degree|schooling", re.I)

PRONOUNS = {
    "he's": "they're", "she's": "they're", "he'd": "they'd", "she'd": "they'd", "he'll": "they'll",
    "she'll": "they'll", "he": "they", "she": "they", "him": "them", "his": "their", "hers": "theirs",
    "himself": "themself", "herself": "themself",
}
OBJECT_FOLLOWERS = {
    "to", "and", "or", "in", "into", "for", "at", "on", "with", "as", "by", "from", "the", "a", "an", "after",
    "before", "over", "about", "through", "during", "while", "when", "because", "that", "this", "up", "out",
    "back", "down", "off", "again", "too", "also", "so", "but", "if", "than", "until",
}
REPLACE_WORDS = {
    "chairman": "chairperson", "chairwoman": "chairperson", "spokesman": "spokesperson",
    "spokeswoman": "spokesperson", "salesman": "salesperson", "saleswoman": "salesperson",
    "businessman": "businessperson", "businesswoman": "businessperson", "alumnus": "alum", "alumna": "alum",
    "fraternity": "student society", "sorority": "student society", "waitress": "server", "waiter": "server",
    "actress": "actor", "headmaster": "head teacher", "headmistress": "head teacher",
    "maternity": "parental", "paternity": "parental", "foreman": "supervisor", "forewoman": "supervisor",
}
GENDER_WORDS = ("woman", "women", "man", "men", "female", "females", "male", "males", "girl", "girls", "boy",
                "boys", "lady", "ladies", "gentleman", "gentlemen", "feminine", "masculine")
FAMILY_WORDS = ("wife", "husband", "spouse", "mother", "father", "mom", "mum", "dad", "son", "sons", "daughter",
                "daughters", "married", "unmarried", "divorced", "divorcee", "widow", "widowed", "widower",
                "pregnant", "pregnancy", "grandmother", "grandfather", "grandma", "grandpa", "fiancé", "fiancée", "fiance", "fiancee", "single mother", "single father",
                "single parent", "stay-at-home parent", "stay-at-home mom", "stay-at-home dad")
NOT_NAMES = {
    "resume", "résumé", "cv", "curriculum", "vitae", "profile", "summary", "engineer", "developer", "analyst",
    "manager", "lead", "senior", "junior", "data", "software", "backend", "frontend", "support", "customer",
    "scientist", "designer", "consultant", "specialist", "director", "head", "team", "the", "of", "and",
}
NAME_TOKEN_RE = re.compile(r"^[A-ZÀ-ÖØ-Þ][\w'’-]*\.?$")


@dataclass
class Redaction:
    text: str
    counts: Counter = field(default_factory=Counter)


def _case_like(src: str, repl: str) -> str:
    return repl[0].upper() + repl[1:] if src[:1].isupper() else repl


def _words_re(words) -> re.Pattern:
    alts = sorted((re.escape(w) for w in words), key=len, reverse=True)
    return re.compile(rf"(?<![\w-])(?:{'|'.join(alts)})(?![\w-])", re.I)


GENDER_RE = _words_re(GENDER_WORDS)
FAMILY_RE = _words_re(FAMILY_WORDS)
REPLACE_RE = _words_re(REPLACE_WORDS)
PRONOUN_RE = _words_re(PRONOUNS)
HER_RE = re.compile(r"\b(her)\b(\s+([A-Za-z]+)|[^\w]|$)", re.I)


def _name_from_line(line: str) -> tuple[list[str], str] | None:
    s = HONORIFIC_RE.sub("", line.strip().lstrip("#").strip().strip("*").strip())
    parts = re.split(r"\s[|—–·-]\s|,\s", s, maxsplit=1)
    head, rest = parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
    tokens = head.split()
    if not (2 <= len(tokens) <= 4) or any(c.isdigit() for c in head):
        return None
    if not all(NAME_TOKEN_RE.match(t) for t in tokens) or any(t.lower().strip(".") in NOT_NAMES for t in tokens):
        return None
    return tokens, rest


def _find_name(lines: list[str]) -> tuple[list[str], int | None, str]:
    for line in lines:
        m = FIELD_RE.match(line)
        if m and m.group(1).lower() in ("name", "full name"):
            value = HONORIFIC_RE.sub("", m.group(2).strip("* "))
            return [t for t in value.split() if len(t.strip(".")) > 1], None, ""
    for i, line in enumerate(lines):
        if line.strip():
            found = _name_from_line(line)
            if found:
                return found[0], i, found[1]
            break
    return [], None, ""


def redact(text: str) -> Redaction:
    c: Counter = Counter()
    lines = text.splitlines()
    name_tokens, name_line, rest = _find_name(lines)
    if name_line is not None:
        lines[name_line] = ("# " + rest) if rest else ""
        c["name"] += 1

    out, in_edu = [], False
    for line in lines:
        m = FIELD_RE.match(line)
        if m:
            c[re.sub(r"\W+", "_", m.group(1).lower()).strip("_")] += 1
            continue
        if PHOTO_RE.search(line):
            c["photo"] += 1
            continue
        is_header = line.lstrip().startswith("#") or (line.strip().isupper() and 2 < len(line.strip()) < 40)
        if is_header:
            in_edu = bool(EDU_HEADER_RE.search(line))
        elif in_edu and YEAR_RE.search(line):
            line, n = YEAR_RE.subn("[YEAR]", line)
            c["graduation_year"] += n
        out.append(line)
    s = "\n".join(out)

    def sub(pattern, repl, kind, s):
        s2, n = pattern.subn(repl, s)
        c[kind] += n
        return s2

    s = sub(EMAIL_RE, "[EMAIL]", "email", s)
    s = sub(URL_RE, "[LINK]", "link", s)
    s = PHONE_RE.sub(lambda m: "[PHONE]" if sum(ch.isdigit() for ch in m.group()) >= 9 else m.group(), s)
    c["phone"] += s.count("[PHONE]")
    s = sub(HONORIFIC_RE, "", "honorific", s)

    tokens = [t.rstrip(".") for t in name_tokens if len(t.rstrip(".")) > 1 and t.lower().rstrip(".") not in ("dr", "prof")]
    if tokens:
        full = re.compile(r"\b" + r"\s+".join(re.escape(t) for t in tokens) + r"\b")
        s = sub(full, "[CANDIDATE]", "name", s)
        for t in tokens:
            s = sub(re.compile(rf"(?<![\w-]){re.escape(t)}(?![\w-])"), "[CANDIDATE]", "name", s)
        s = re.sub(r"\[CANDIDATE\](?:\s+\[CANDIDATE\])+", "[CANDIDATE]", s)

    for r in AGE_RES:
        s = sub(r, "[AGE]", "age", s)
    s = sub(GRAD_RES[0], "[YEAR]", "graduation_year", s)
    s = sub(GRAD_RES[1], lambda m: m.group(1) + "[YEAR]", "graduation_year", s)

    def her(m):
        nxt = m.group(3)
        word = "them" if (nxt is None or nxt.lower() in OBJECT_FOLLOWERS) else "their"
        return _case_like(m.group(1), word) + m.group(2)

    s = sub(HER_RE, her, "pronoun", s)
    s = sub(PRONOUN_RE, lambda m: _case_like(m.group(), PRONOUNS[m.group().lower()]), "pronoun", s)
    s = sub(REPLACE_RE, lambda m: _case_like(m.group(), REPLACE_WORDS[m.group().lower()]), "gendered_word", s)
    s = sub(FAMILY_RE, "[FAMILY]", "family", s)
    s = sub(GENDER_RE, "[GENDER]", "gendered_word", s)

    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip() + "\n"
    return Redaction(s, Counter({k: v for k, v in c.items() if v}))
