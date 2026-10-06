import json
from datetime import datetime
from pathlib import Path


class NotesStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text() or "[]")

    def _save(self, notes: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(notes, indent=2))

    def add(self, text: str, tags: list[str] | None = None) -> dict:
        notes = self._load()
        note = {
            "id": max((n["id"] for n in notes), default=0) + 1,
            "text": text.strip(),
            "tags": [t.strip().lower() for t in tags or [] if t.strip()],
            "created": datetime.now().isoformat(timespec="seconds"),
        }
        notes.append(note)
        self._save(notes)
        return note

    def all(self) -> list[dict]:
        return self._load()

    def search(self, query: str) -> list[dict]:
        words = [w.strip(".,?!:;'\"") for w in query.lower().split()]
        words = [w for w in words if len(w) >= 3]
        scored = []
        for n in self._load():
            hay = (n["text"] + " " + " ".join(n.get("tags", []))).lower()
            hits = sum(w in hay for w in words)
            if hits:
                scored.append((hits, n))
        scored.sort(key=lambda x: -x[0])
        return [n for _, n in scored]
