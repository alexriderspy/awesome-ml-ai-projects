from games.rank import leaderboard


def test_order():
    players = [
        {"name": "zoe", "score": 90},
        {"name": "Bea", "score": 75},
        {"name": "amir", "score": 90},
        {"name": "carl", "score": 75},
        {"name": "Dev", "score": 99},
    ]
    assert leaderboard(players) == ["Dev", "amir", "zoe", "Bea", "carl"]
