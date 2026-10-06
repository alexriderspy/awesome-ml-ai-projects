import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from recruit_team.redact import redact

PRACTICE = ROOT / "eval" / "practice"

SAMPLE = """# Ms. Jane Q. Doe | Platform Engineer
Pronouns: she/her
Gender: Female
Age: 34
Date of Birth: 01/02/1992
Marital status: Married
Photo: jane.jpg
jane.doe@example.com · +1 415 555 0199 · https://linkedin.com/in/janedoe

## Experience
### Platform Engineer, Acme (2018 - 2024)
- Jane led her team of 4; the CTO promoted her to staff in 2022. She is 34 years old.
- Doe's migration plan was adopted. Chairwoman of the Women in Ops guild. Mother of two.
- Has 5 years of experience; manages the average p95 budget.

## Education
MS Computer Science, State University, 2014
Class of 2014
"""


@pytest.fixture(scope="module")
def red():
    return redact(SAMPLE).text


def test_name_removed_everywhere(red):
    assert "Jane" not in red and "Doe" not in red
    assert "[CANDIDATE] led" in red and "[CANDIDATE]'s migration" in red
    assert red.startswith("# Platform Engineer")


@pytest.mark.parametrize("leak", ["Pronouns", "Gender:", "Female", "Age:", "Date of Birth", "Married", "jane.jpg",
                                  "Ms.", "34 years old", "@", "555", "linkedin", "Mother", "Women", "Chairwoman"])
def test_protected_signals_removed(red, leak):
    assert leak.lower() not in red.lower()


def test_pronouns_neutralised(red):
    assert "their team" in red and "promoted them to staff" in red and "They is" in red
    assert not re.search(r"\b(she|her|he|him|his)\b", red, re.I)


def test_graduation_years_hidden_but_work_dates_kept(red):
    assert "2014" not in red and "Class of [YEAR]" in red and "State University, [YEAR]" in red
    assert "(2018 - 2024)" in red and "staff in 2022" in red


def test_no_over_redaction(red):
    for keep in ("5 years of experience", "manages the average", "MS Computer Science", "Chairperson of the"):
        assert keep in red


@pytest.mark.parametrize("line", ["Name: Arjun Mehta", "**Name:** Arjun Mehta", "- Full name: Arjun Mehta"])
def test_name_field(line):
    red = redact(f"{line}\nSummary: Arjun builds APIs.\n").text
    assert "Arjun" not in red and "Mehta" not in red and "[CANDIDATE] builds APIs" in red


@pytest.mark.parametrize("text", ["Born in 1980", "born on 3 May 1980", "aged 52", "52-year-old engineer", "29 y/o",
                                  "Graduated in 1999", "graduated 2001"])
def test_age_phrases(text):
    red = redact("Engineer Profile\n" + text + "\n").text
    assert not re.search(r"\d", red), red


def test_title_line_is_not_mistaken_for_a_name():
    red = redact("Senior Data Analyst\n- SQL and Looker\n").text
    assert red.startswith("Senior Data Analyst")


def test_date_ranges_are_not_phone_numbers():
    assert "2015-2018, 2018-2021" in redact("Acme 2015-2018, 2018-2021\n").text


def test_her_object_vs_possessive():
    assert redact("Notes\nWe gave her the award and her manager agreed.\n").text.strip() == \
        "Notes\nWe gave them the award and their manager agreed."


def test_practice_resumes_leak_no_names_or_contacts():
    for path in PRACTICE.glob("*/*/*.md"):
        if path.parent.name not in ("resumes", "counterfactual"):
            continue
        raw = path.read_text()
        first = raw.strip().splitlines()[0].lstrip("# ").split("|")[0]
        name_line = next((ln for ln in raw.splitlines() if ln.lower().startswith("name:")), None)
        names = (name_line.split(":", 1)[1] if name_line else first).replace("Mr.", "").replace("Ms.", "") \
            .replace("Mrs.", "").replace("Dr.", "").split()
        red = redact(raw).text
        for n in names:
            assert not re.search(rf"(?<![\w-]){re.escape(n)}(?![\w-])", red), (path.name, n)
        assert "@" not in red
        assert not re.search(r"^(age|gender|pronouns|date of birth|marital status|nationality)\s*:", red, re.I | re.M)


def test_counterfactual_twins_redact_identically():
    twins = sorted(PRACTICE.glob("*/counterfactual/*.md"))
    assert len(twins) == 3
    for twin in twins:
        orig = twin.parent.parent / "resumes" / twin.name
        assert orig.read_text() != twin.read_text()
        assert redact(orig.read_text()).text == redact(twin.read_text()).text, twin


def test_programmatic_swap_redacts_identically():
    tmpl = ("{hon} {first} Kowalczyk\nGender: {g}\nAge: {age}\n{first}@mail.test\n\n## Experience\n"
            "- {P} shipped the billing API; the VP promoted {obj} after {pos} launch.\n"
            "- {first}'s team grew to 6 under {pos} lead.\n\n## Education\nBSc Physics, 20{yy}\n")
    a = tmpl.format(hon="Ms.", first="Anna", g="Female", age=27, P="She", obj="her", pos="her", yy="18")
    b = tmpl.format(hon="Mr.", first="Piotr", g="Male", age=58, P="He", obj="him", pos="his", yy="01")
    assert redact(a).text == redact(b).text
