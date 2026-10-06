def leaderboard(players):
    ordered = sorted(players, key=lambda p: (p["score"], p["name"]), reverse=True)
    return [p["name"] for p in ordered]
