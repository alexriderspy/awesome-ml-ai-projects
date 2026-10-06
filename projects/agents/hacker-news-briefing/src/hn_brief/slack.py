import os
from typing import Callable


def send(text: str, webhook_url: str | None = None, post: Callable | None = None, timeout: float = 10.0) -> bool:
    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")
    if not url.startswith("https://hooks.slack.com/"):
        raise ValueError("SLACK_WEBHOOK_URL is missing or is not a hooks.slack.com URL")
    if post is None:
        import requests

        post = requests.post
    r = post(url, json={"text": text}, timeout=timeout)
    r.raise_for_status()
    return True
