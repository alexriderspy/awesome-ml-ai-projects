import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

from .plan import Deck


def soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def render_with_libreoffice(pptx: Path, out_dir: Path, pages: list[int], scale: float = 1.0) -> list[Path]:
    import pypdfium2 as pdfium

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([soffice(), "--headless", "--convert-to", "pdf", "--outdir", tmp, str(pptx)],
                       check=True, capture_output=True, timeout=180)
        pdf = pdfium.PdfDocument(str(Path(tmp) / (pptx.stem + ".pdf")))
        out = []
        for i in pages:
            if i < len(pdf):
                path = out_dir / f"slide-{i + 1:02d}.png"
                pdf[i].render(scale=scale).to_pil().save(path)
                out.append(path)
        return out


def render_with_pillow(deck: Deck, out_dir: Path, pages: list[int]) -> list[Path]:
    from PIL import Image, ImageDraw, ImageFont

    seq = [("title", deck.title, [deck.subtitle])]
    for i, sec in enumerate(deck.sections, 1):
        seq.append(("section", f"{i:02d}  {sec.title}", []))
        seq += [("content", s.title, s.bullets) for s in sec.slides]

    def font(size):
        try:
            return ImageFont.truetype("Arial.ttf", size)
        except OSError:
            return ImageFont.load_default(size)

    out = []
    for i in pages:
        if i >= len(seq):
            continue
        kind, title, lines = seq[i]
        img = Image.new("RGB", (1280, 720), "white")
        d = ImageDraw.Draw(img)
        y = 300 if kind != "content" else 50
        d.text((70, y), textwrap.fill(title, 40), fill="#111111", font=font(48 if kind != "content" else 40))
        y += 140 if kind != "content" else 110
        for line in lines:
            d.text((90, y), "• " + textwrap.fill(line, 60), fill="#333333", font=font(28))
            y += 60
        d.text((70, 680), "preview drawn by Pillow from slide text", fill="#999999", font=font(16))
        path = out_dir / f"slide-{i + 1:02d}.png"
        img.save(path)
        out.append(path)
    return out


def render_previews(pptx: str | Path, deck: Deck, out_dir: str | Path, pages: list[int]) -> tuple[list[Path], str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if soffice():
        try:
            return render_with_libreoffice(Path(pptx), out_dir, pages), "libreoffice"
        except (subprocess.SubprocessError, OSError, ImportError):
            pass
    return render_with_pillow(deck, out_dir, pages), "pillow"
