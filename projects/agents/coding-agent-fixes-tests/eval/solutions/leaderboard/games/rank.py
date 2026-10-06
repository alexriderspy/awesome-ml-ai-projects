def leaderboard(players):
    ordered = sorted(players, key=lambda p: (-p["score"], p["name"].lower()))
    return [p["name"] for p in ordered]
