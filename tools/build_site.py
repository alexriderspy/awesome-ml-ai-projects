import html
import json
import random
import re
import shutil
import sys
from pathlib import Path

import markdown
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
REPO = "https://github.com/alexriderspy/awesome-ml-ai-projects"
CATS = {"llm-apps": "LLM apps", "agents": "Agents", "fine-tuning": "Fine-tuning", "classic-ml": "Classic ML"}
ORDER = ["llm-apps", "agents", "fine-tuning", "classic-ml"]
FIRST = ["youtube-summarizer", "ppt-generator-agent", "chat-with-pdf", "structured-extraction",
         "tool-calling-basics", "multi-agent-blog-writer", "github-issue-triage-agent"]
FONTS = "https://fonts.googleapis.com/css2?family=Sora:wght@500;600;700&family=Geist:wght@400;500;600&family=Geist+Mono:wght@400;500&display=swap"


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def inline_md(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)


def parse(readme: Path, cat: str) -> dict:
    text = readme.read_text()
    lines = text.splitlines()
    title = lines[0].lstrip("# ").strip()
    pitch = next(l for l in lines[1:] if l.strip() and not l.startswith(("!", "|", "#", ">", "`")))
    meta = re.search(r"\*\*Level:\*\* (.+?) · \*\*Time:\*\* (.+?) · \*\*Runs on:\*\* (.+)", text)
    video = re.search(r"^Video: \[[^\]]*\]\((https://[^)]+)\)", text, re.M)
    imgs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    pick = next((i for i in imgs if "slide-03" in i), imgs[0] if imgs else None)
    lb = re.search(r"\| reference \| [^|]+ \|(?: [^|]+ \|)?? ([\d.]+) \|", text)
    return {
        "slug": readme.parent.name, "cat": cat, "cat_label": CATS[cat], "dir": readme.parent,
        "title": title, "pitch": pitch, "text": text,
        "level": meta.group(1) if meta else "", "time": meta.group(2) if meta else "", "runs": meta.group(3) if meta else "",
        "video": video.group(1) if video else "", "image": pick, "score": lb.group(1) if lb else "",
    }


def body_markdown(p: dict) -> str:
    out, skip_intro = [], True
    for line in p["text"].splitlines()[1:]:
        if skip_intro:
            if line.startswith("## "):
                skip_intro = False
            else:
                continue
        out.append(line)
    return "\n".join(out)


def thumb(src: Path, dest: Path) -> None:
    im = Image.open(src).convert("RGB")
    w, h = im.size
    top = 0 if "slide" in src.name else min(60, h // 20)
    ch = min(h - top, int(w * 10 / 16))
    im = im.crop((0, top, w, top + ch))
    im = im.resize((960, int(960 * ch / w)), Image.LANCZOS)
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "JPEG", quality=82, optimize=True)


def render_body(p: dict, page_dir: Path) -> str:
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
    out = md.convert(body_markdown(p))

    def fix_img(m):
        src = m.group(1)
        if src.startswith("http"):
            return m.group(0)
        f = p["dir"] / src
        if f.exists():
            (page_dir / src).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(f, page_dir / src)
        return m.group(0)

    def fix_link(m):
        href = m.group(1)
        if href.startswith(("http", "#", "mailto:")):
            return m.group(0)
        kind = "tree" if (p["dir"] / href).is_dir() else "blob"
        return f'href="{REPO}/{kind}/main/projects/{p["cat"]}/{p["slug"]}/{href}"'

    out = re.sub(r'<img [^>]*src="([^"]+)"', lambda m: (fix_img(m)), out)
    out = re.sub(r'href="([^"]+)"', fix_link, out)
    out = re.sub(r"<li>\[ \] ", "<li><label><input type=\"checkbox\" disabled> <span>", out)
    out = re.sub(r"(<li><label><input type=\"checkbox\" disabled> <span>.*?)</li>", r"\1</span></label></li>", out, flags=re.S)
    out = re.sub(r"<ul>(\s*<li><label><input)", r'<div class="bar"><i></i></div><p class="mono" data-progress></p><ul class="tasks">\1', out)
    return out


def head(title: str, desc: str, depth: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{FONTS}">
<link rel="stylesheet" href="{depth}assets/style.css">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='9' fill='%23ff6a2b'/%3E%3C/svg%3E">
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="{depth}">awesome-ml-ai-projects</a>
<nav class="nav">
<a href="{depth}#projects">Projects</a>
<a href="{depth}#start">Quick start</a>
<a href="{depth}#leaderboards">Leaderboards</a>
<a class="btn btn-light" href="{REPO}">Star on GitHub</a>
</nav>
</div></header>
"""


FOOT = """<footer><div class="wrap">
<span>Made by Sreemanti Dey · MIT licence</span>
<span><a href="https://www.youtube.com/@sreemantidey">YouTube</a><a href="{repo}">GitHub</a></span>
</div></footer>
<script src="{depth}assets/site.js"></script>
</body>
</html>
"""


def card(p: dict) -> str:
    pic = (f'<img src="assets/thumbs/{p["slug"]}.jpg" alt="" loading="lazy">' if p["thumb"]
           else f'<div class="ini">{esc("".join(w[0] for w in p["title"].split() if w[0].isupper())[:2])}</div>')
    pill = (f'<span class="pill"><i></i>Score {esc(p["score"])}</span>' if p["score"]
            else '<span class="pill off"><i></i>Colab ready</span>')
    return f"""<a class="pcard" data-cat="{p['cat']}" href="p/{p['slug']}/">
<div class="t"><b>{esc(p['title'])}</b><span>{inline_md(p['pitch'])}</span></div>
<div class="pic">{pic}<span class="tag mono">{esc(p['cat_label'])} · {esc(p['level'])}</span>{pill}</div>
</a>"""


def home(projects: list[dict]) -> str:
    pics = [f"assets/thumbs/{p['slug']}.jpg" for p in projects if p["thumb"]]
    rnd = random.Random(7)
    tiles = []
    for i in range(22):
        w = rnd.randint(130, 300)
        while True:
            x, y = rnd.randint(-760, 760), rnd.randint(-420, 300)
            if abs(x) > 430 or y < -170:
                break
        z, ry, rx = rnd.randint(-700, 200), rnd.randint(-35, 35), rnd.randint(-11, 11)
        bright = 0.22 + 0.4 * (z + 700) / 900
        tiles.append(f'<div class="tile" style="transform: translate3d({x}px,{y}px,{z}px) rotateY({ry}deg) rotateX({rx}deg)">'
                     f'<img src="{pics[i % len(pics)]}" alt="" style="width:{w}px;height:{int(w * .62)}px;margin:{-int(w * .31)}px 0 0 {-w // 2}px;'
                     f'filter:brightness({bright:.2f});animation-delay:-{i * .9:.1f}s"></div>')
    orbs = "".join(
        f'<img class="orb" src="{src}" alt="" style="--r:{250 + (i % 3) * 80}px;width:{44 + (i % 3) * 12}px;height:{44 + (i % 3) * 12}px;'
        f'left:{-(22 + (i % 3) * 6)}px;top:{-(22 + (i % 3) * 6)}px;animation-duration:{26 + i * 5}s;animation-delay:-{i * 6}s">'
        for i, src in enumerate(pics[:6]))
    triage = next((p for p in projects if p["slug"] == "github-issue-triage-agent" and p["thumb"]), None)
    finder_img = f"assets/thumbs/{triage['slug']}.jpg" if triage else pics[0]
    n = len(projects)
    chips = '<button class="chip" data-cat="all" aria-pressed="true">All</button>' + "".join(
        f'<button class="chip" data-cat="{c}" aria-pressed="false">{CATS[c]}</button>' for c in ORDER)
    cards = "\n".join(card(p) for p in projects)
    desc = f"{n} hands-on ML and AI projects with working code, an eval that scores your build, offline tests and a real demo."
    return head("Awesome ML & AI Projects", desc, "") + f"""
<main>
<section class="hero"><div class="hero-stage">
<div class="glow"></div>
<div class="cloud">{''.join(tiles)}</div>
<div class="hud" aria-hidden="true"><i class="tl"></i><i class="tr"></i><i class="bl"></i><i class="br"></i>
<span class="tick l"></span><span class="tick r"></span>
<span class="lab a mono">{n} projects</span><span class="lab b mono">MIT · free</span>
<span class="lab c mono"><span class="dot"></span>Eval 100/100</span><span class="lab d mono">Ollama · any API</span></div>
<div class="hero-copy">
<div class="mono rise">Hands-on ML &amp; AI projects</div>
<h1 class="rise" style="animation-delay:.15s">Where ideas become <span class="accent">shipped</span> models</h1>
<p class="rise" style="animation-delay:.3s">Working code, an eval that scores your build out of 100, offline tests and a real demo for every project.</p>
<div class="row rise" style="animation-delay:.45s"><a class="btn btn-accent" href="#projects">Browse projects →</a><a class="btn btn-ghost" href="#start">Quick start</a></div>
</div>
</div></section>

<section class="finder">
<img class="blur" src="{finder_img}" alt="">
<div class="fade"></div>
<div class="frame"><img src="{finder_img}" alt="The GitHub Issue Triage Agent labelling an issue and finding its duplicate"><b class="tl"></b><b class="tr"></b><b class="bl"></b><b class="br"></b><span class="cross"></span></div>
<span class="side l mono">Tool calls 6</span><span class="side r mono">$0.0035</span>
<div class="finder-copy"><div class="mono">A real run · GitHub Issue Triage Agent</div><h2>Every demo is a real run, not a mockup</h2></div>
</section>

<section class="block"><div class="wrap">
<div class="orbit"><h2>Where your build gets a <span class="accent">score</span></h2><div class="orb-anchor">{orbs}</div></div>
<div class="four">
<div class="card"><div class="k">01 · MILESTONES</div><p>Build it yourself in 4 to 6 steps, each pointing at the file it lives in.</p></div>
<div class="card"><div class="k">02 · REFERENCE CODE</div><p>A working implementation to read when you get stuck. No framework magic.</p></div>
<div class="card"><div class="k">03 · SCORE OUT OF 100</div><p>An original practice set and an eval, so you know your build works.</p></div>
<div class="card"><div class="k">04 · REAL DEMO</div><p>Screenshots and outputs from an actual run.</p></div>
</div>
</div></section>

<section id="projects" style="padding: 40px 0 120px"><div class="wrap">
<div class="head"><h2>All projects</h2><span class="mono" data-count>{n} of {n} projects</span></div>
<div class="chips" role="group" aria-label="Filter by category">{chips}</div>
<div class="grid">
{cards}
</div>
</div></section>

<section id="start" style="padding: 0 0 120px"><div class="wrap split">
<div><h2 class="big">Start in a minute</h2><p class="lead">Free local model through Ollama, no API key. Swap in any OpenAI-compatible model with three environment variables.</p></div>
<div class="term">git clone {REPO}
cd awesome-ml-ai-projects/projects/llm-apps/youtube-summarizer
pip install -r requirements.txt
ollama pull llama3.2
PYTHONPATH=src python eval/run_eval.py
<span class="accent">OVERALL 100.0/100</span></div>
</div></section>

<section id="leaderboards" class="lb"><div class="glow2"></div>
<div class="wrap split" style="position: relative; padding: 120px 24px">
<div><h2 class="big">Beat the <span class="accent">reference</span></h2><p class="lead">Every project has a leaderboard. Run the eval with your model and your code, then open a pull request with your row.</p>
<p style="margin-top: 24px"><a class="btn" style="background: var(--text); color: #050505" href="{REPO}/blob/main/CONTRIBUTING.md">How to post a score →</a></p></div>
<div class="table"><div class="mono">Structured Extraction · leaderboard</div>
<div><span>reference · deepseek-flash</span><span style="font-family: var(--mono)">99.1</span></div>
<div><span>reference · qwen2.5:7b</span><span style="font-family: var(--mono)">87.7</span></div>
<div style="color: var(--faint)"><span>your build</span><span class="accent" style="font-family: var(--mono)">—</span></div></div>
</div></section>
</main>
""" + FOOT.format(repo=REPO, depth="")


def project_page(p: dict, nxt: dict, page_dir: Path) -> str:
    body = render_body(p, page_dir)
    img = f"../../assets/thumbs/{p['slug']}.jpg" if p["thumb"] else None
    hero_img = (f'<img class="blur" src="{img}" alt=""><div class="fade"></div>'
                f'<div class="frame"><img src="{img}" alt="{esc(p["title"])} demo"><b class="tl"></b><b class="tr"></b><b class="bl"></b><b class="br"></b></div>'
                f'<span class="side l mono">Level · {esc(p["level"])}</span><span class="side r mono">{esc(p["time"])}</span>'
                if img else '<div class="noimg"></div>')
    words = p["title"].split()
    title = esc(" ".join(words[:-1])) + (" " if len(words) > 1 else "") + f'<span class="accent">{esc(words[-1])}</span>'
    video = f'<a class="btn btn-ghost" href="{p["video"]}">▶ Watch the build</a>' if p["video"] else ""
    score = (f'<div class="n">{esc(p["score"])}<span>/100</span></div>' if p["score"]
             else '<div class="n" style="font-size:40px">Your turn</div><p style="margin:0;color:var(--muted)">Train it and post the first score.</p>')
    nimg = f'<img src="../../assets/thumbs/{nxt["slug"]}.jpg" alt="">' if nxt["thumb"] else ""
    code_url = f"{REPO}/tree/main/projects/{p['cat']}/{p['slug']}"
    return head(f"{p['title']} · Awesome ML & AI Projects", re.sub(r"[`*]", "", p["pitch"]), "../../") + f"""
<main>
<section class="p-hero{'' if img else ' bare'}">
{hero_img}
<div class="copy">
<div class="mono rise"><a href="../../#projects" style="color: var(--muted); text-decoration: none">Projects</a> / {esc(p['cat_label'])}</div>
<h1 class="rise" style="animation-delay:.12s">{title}</h1>
<p class="rise" style="animation-delay:.24s">{inline_md(p['pitch'])}</p>
<div class="meta rise" style="animation-delay:.3s"><span>{esc(p['level'])}</span><span>{esc(p['time'])}</span><span>{inline_md(p['runs'])}</span></div>
<div class="row rise" style="animation-delay:.36s"><a class="btn btn-accent" href="{code_url}">View the code →</a>{video}</div>
</div>
</section>
<div class="wrap p-body">
<article class="prose">{body}</article>
<aside class="aside">
<div class="card score"><div class="mono">Reference score</div>{score}</div>
<a class="btn btn-accent" style="justify-content:center" href="{code_url}">Open on GitHub →</a>
<a class="next" href="../{nxt['slug']}/">{nimg}<span><span class="mono" style="color:#d4d4d4">Next project</span><strong>{esc(nxt['title'])} →</strong></span></a>
</aside>
</div>
</main>
""" + FOOT.format(repo=REPO, depth="../../")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets/thumbs").mkdir(parents=True)
    shutil.copy(ROOT / "site/style.css", OUT / "assets/style.css")
    shutil.copy(ROOT / "site/site.js", OUT / "assets/site.js")

    projects = []
    for cat in ORDER:
        for readme in sorted((ROOT / "projects" / cat).glob("*/README.md")):
            projects.append(parse(readme, cat))
    rank = {s: i for i, s in enumerate(FIRST)}
    projects.sort(key=lambda p: (ORDER.index(p["cat"]), rank.get(p["slug"], 99), p["slug"]))

    for p in projects:
        src = p["dir"] / p["image"] if p["image"] else None
        p["thumb"] = bool(src and src.exists())
        if p["thumb"]:
            thumb(src, OUT / "assets/thumbs" / f"{p['slug']}.jpg")

    (OUT / "index.html").write_text(home(projects))
    for i, p in enumerate(projects):
        page_dir = OUT / "p" / p["slug"]
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / "index.html").write_text(project_page(p, projects[(i + 1) % len(projects)], page_dir))
    (OUT / ".nojekyll").write_text("")
    (OUT / "projects.json").write_text(json.dumps([{k: p[k] for k in ("slug", "cat", "title", "score", "video")} for p in projects], indent=1))
    print(f"built {len(projects)} project pages into {OUT}")


if __name__ == "__main__":
    main()
