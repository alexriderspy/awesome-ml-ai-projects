import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Interest:
    name: str
    weight: float
    keywords: list[str]


@dataclass
class Profile:
    name: str
    interests: list[Interest]
    about: str = ""
    dislikes: list[str] = field(default_factory=list)
    dislike_weight: float = 2.0
    prior_weight: float = 0.5

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        interests = [Interest(i["name"], float(i.get("weight", 1.0)), [str(k) for k in i.get("keywords", [])])
                     for i in d.get("interests", [])]
        if not interests:
            raise ValueError("profile needs at least one interest")
        return cls(
            name=d.get("name", "me"),
            about=d.get("about", ""),
            interests=interests,
            dislikes=[str(x) for x in d.get("dislikes", [])],
            dislike_weight=float(d.get("dislike_weight", 2.0)),
            prior_weight=float(d.get("prior_weight", 0.5)),
        )

    def describe(self) -> str:
        lines = [f"Reader: {self.name}. {self.about}".strip()]
        for i in sorted(self.interests, key=lambda i: -i.weight):
            lines.append(f"- cares about {i.name} (weight {i.weight:g}): {', '.join(i.keywords)}")
        if self.dislikes:
            lines.append(f"- does NOT want: {', '.join(self.dislikes)}")
        return "\n".join(lines)


def load_profile(path: str | Path) -> Profile:
    path = Path(path)
    raw = path.read_text()
    if path.suffix.lower() in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)
    return Profile.from_dict(data)
