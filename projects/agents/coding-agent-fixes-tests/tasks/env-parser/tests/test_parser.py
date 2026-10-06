from dotenv_lite.parser import parse_env

SAMPLE = """
# app settings
DEBUG = true
NAME="mini app"
DB_URL=postgres://u:pw@db/app?sslmode=require&pool=5
EMPTY=
"""


def test_parse():
    assert parse_env(SAMPLE) == {
        "DEBUG": "true",
        "NAME": "mini app",
        "DB_URL": "postgres://u:pw@db/app?sslmode=require&pool=5",
        "EMPTY": "",
    }
