import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("app")
    ap.add_argument("out")
    ap.add_argument("--fill", action="append", default=[])
    ap.add_argument("--upload", action="append", default=[])
    ap.add_argument("--click", action="append", default=[])
    ap.add_argument("--wait-text")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--width", type=int, default=1280)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    app = Path(args.app).resolve()
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", str(app), "--server.headless", "true",
         "--server.port", str(port), "--browser.gatherUsageStats", "false", "--theme.base", "light"],
        cwd=app.parent, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": args.width, "height": 900}, device_scale_factor=2)
            for _ in range(60):
                try:
                    page.goto(f"http://127.0.0.1:{port}", timeout=2000)
                    break
                except Exception:
                    time.sleep(1)
            page.wait_for_selector("[data-testid='stApp']", timeout=60000)
            page.wait_for_timeout(2500)
            for f in args.fill:
                label, value = f.split("=", 1)
                box = page.get_by_label(label, exact=False).first
                box.fill(value)
                box.press("Enter") if box.evaluate("e => e.tagName") == "INPUT" else None
                page.wait_for_timeout(500)
            for u in args.upload:
                label, path = u.split("=", 1)
                page.locator("input[type=file]").first.set_input_files(str(Path(path).resolve()))
                page.wait_for_timeout(1500)
            for c in args.click:
                page.get_by_role("button", name=c).first.click()
                page.wait_for_timeout(500)
            if args.wait_text:
                page.get_by_text(args.wait_text, exact=False).first.wait_for(timeout=args.timeout * 1000)
            page.wait_for_timeout(1500)
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=args.out, full_page=True)
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
