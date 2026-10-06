import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from dep_doctor import PyPIClient, check, explain, parse_pyproject, parse_requirements, target_python
from dep_doctor.llm import parse_json
from run_eval import leaked_packages, prf, run_case

CACHE = ROOT / "eval/practice/pypi-cache"


def codes(findings):
    return {(f.code, f.package) for f in findings}


def offline():
    return PyPIClient(CACHE, offline=True)


def test_requirements_parsing_handles_comments_hashes_options_and_continuations():
    m = parse_requirements("-r base.txt\n# c\nrequests==2.31.0 \\\n    --hash=sha256:abc\nFlask>=2  # web\n-e .\n")
    assert [(d.name, str(d.specifier), d.line) for d in m.deps] == [("requests", "==2.31.0", 3), ("flask", ">=2", 5)]
    assert len(m.notes) == 2


def test_stdlib_backport_and_compat():
    m = parse_requirements("json\nmock==5.1.0\nsix\nDateTime==5.0\n")
    assert codes(check(m, "3.11")) == {("DD001", "json"), ("DD002", "mock"), ("DD003", "six")}


def test_backport_depends_on_target_python():
    m = parse_requirements("tomli==2.0.1\nimportlib-metadata==7.0.0\n")
    assert codes(check(m, "3.9")) == set()
    assert codes(check(m, "3.11")) == {("DD002", "tomli"), ("DD002", "importlib-metadata")}


def test_marker_that_excludes_target_is_not_flagged():
    m = parse_requirements('tomli==2.0.1; python_version < "3.11"\n')
    assert check(m, "3.12") == []


def test_unpinned_and_lower_bound_only():
    m = parse_requirements("httpx\ntenacity>=8\nrich>=13,<14\n")
    assert codes(check(m, "3.11")) == {("DD004", "httpx"), ("DD005", "tenacity")}


def test_duplicate_vs_conflict_uses_normalized_names():
    m = parse_requirements("PyYAML==6.0.1\npyyaml>=5\nNumPy>=1.24\nnumpy<1.20\n")
    assert codes(check(m, "3.11")) == {("DD006", "pyyaml"), ("DD007", "numpy")}


def test_yanked_and_missing_from_cache():
    m = parse_requirements("requests==2.32.0\npandas==1.99.0\nclick==8.1.7\n")
    assert codes(check(m, "3.11", offline())) == {("DD008", "requests"), ("DD009", "pandas")}


def test_offline_without_cache_skips_lookup(tmp_path):
    m = parse_requirements("requests==2.32.0\n")
    assert check(m, "3.11", PyPIClient(tmp_path, offline=True)) == []


def test_pyproject_requires_python_sets_target_and_poetry_caret():
    m = parse_pyproject('[tool.poetry.dependencies]\npython = "^3.10"\nfastapi = "^0.110"\nuvicorn = "*"\n')
    assert target_python(m, None) == "3.10"
    fastapi = next(d for d in m.deps if d.name == "fastapi")
    assert str(fastapi.specifier) == "<0.111.0,>=0.110.0"
    assert codes(check(m)) == {("DD004", "uvicorn")}


def test_pep621_extras_are_separate_groups():
    m = parse_pyproject('[project]\ndependencies = ["pytest>=7"]\n[project.optional-dependencies]\ndev = ["pytest>=8"]\n')
    assert codes(check(m, "3.11")) == set()


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, user):
        self.calls.append(user)
        return self.replies.pop(0)


def test_explain_retries_then_keeps_only_real_findings():
    findings = check(parse_requirements("mock\nuuid\n"), "3.11")
    bad = json.dumps([{"code": "DD002", "package": "mock", "explanation": "x"}, {"code": "DD999", "package": "evil", "explanation": "y"}])
    good = json.dumps([{"code": f.code, "package": f.package, "explanation": f"why {f.package}"} for f in findings])
    llm = FakeLLM([bad, good])
    out, log = explain(findings, llm)
    assert log[0].startswith("attempt 1: extra item") and log[1] == "attempt 2: ok"
    assert "rejected" in llm.calls[1]
    assert [o["explanation"] for o in out] == [f"why {f.package}" for f in findings]


def test_explain_falls_back_to_linter_text_when_model_keeps_drifting():
    findings = check(parse_requirements("mock\n"), "3.11")
    out, log = explain(findings, FakeLLM(["not json", "[]"]))
    assert out[0]["package"] == "mock" and "unittest.mock" in out[0]["explanation"]
    assert not log[-1].endswith("ok")


def test_parse_json_handles_fences_and_arrays():
    assert parse_json('```json\n[{"a": 1}]\n```') == [{"a": 1}]
    assert parse_json('sure: {"a": [1]} done') == {"a": [1]}


def test_eval_helpers():
    assert prf(set(), set()) == (1.0, 1.0, 1.0)
    assert prf({1, 2}, {2, 3})[2] == pytest.approx(0.5)
    assert leaked_packages([{"package": "mock", "explanation": "also see requests"}], {"mock", "requests"}) == ["mock->requests"]
    assert leaked_packages([{"package": "pyyaml", "explanation": "use yaml.safe_load"}], {"pyyaml", "yaml"}) == ["pyyaml->yaml"]


@pytest.mark.parametrize("case_id", json.loads((ROOT / "eval/practice/gold.json").read_text()).keys())
def test_practice_set_checks_match_gold(case_id):
    case = json.loads((ROOT / "eval/practice/gold.json").read_text())[case_id]
    assert run_case(case)["f1"] == 1.0
