# Demo run

Real run on 2026-10-06 against live PyPI, explanations by `deepseek-flash`.

```bash
PYTHONPATH=src python -m dep_doctor demo/requirements.txt --python 3.12 --explain
```

Input ([`requirements.txt`](requirements.txt)):

```
# an older internal tool, now deployed on Python 3.12
fastapi==0.110.0
pydantic==2.12.1
requests==2.32.1
httpx
mock==5.1.0
importlib-metadata==7.0.0
six==1.16.0
uuid
PyYAML==6.0.1
pyyaml>=5.4
tenacity>=8.2
```

stderr: `explain: attempt 1: ok` · exit code 1 (there are error-level findings)

Output:

# Dependency check: `demo/requirements.txt`

Target Python: 3.12 · 9 finding(s)

| Severity | Code | Package | Line | Problem |
|---|---|---|---|---|
| error | DD008 | `pydantic` | 3 | `pydantic==2.12.1` was yanked from PyPI (references a yanked version of pydantic-core). |
| error | DD008 | `requests` | 4 | `requests==2.32.1` was yanked from PyPI (Yanked due to conflicts with CVE-2024-35195 mitigation ). |
| error | DD001 | `uuid` | 9 | `uuid` is a standard-library module; the PyPI package of that name is unrelated or ancient and can break installs. |
| warning | DD004 | `httpx` | 5 | `httpx` has no version constraint, so any future release (including breaking ones) gets installed. |
| warning | DD002 | `mock` | 6 | `mock` backports something the stdlib has had since Python 3.3; target is 3.12. |
| warning | DD002 | `importlib-metadata` | 7 | `importlib-metadata` backports something the stdlib has had since Python 3.10; target is 3.12. |
| warning | DD006 | `pyyaml` | 11 | `pyyaml` appears 2 times (lines 10, 11); the effective constraint is `==6.0.1,>=5.4`. |
| info | DD003 | `six` | 8 | `six` is a Python 2/3 compatibility layer; on Python 3.12 it is only needed if a dependency still imports it. |
| info | DD005 | `tenacity` | 12 | `tenacity>=8.2` has no upper bound, so installs are not reproducible. |

## What to do

- **pydantic** (DD008): This version was yanked from PyPI because it depends on a yanked pydantic-core, so installs can fail or pull broken code. Move to the next non-yanked release.
- **requests** (DD008): This version was yanked due to conflicts with the CVE-2024-35195 fix, so it may be blocked or unsafe to install. Move to the next non-yanked release.
- **uuid** (DD001): The PyPI package named uuid is unrelated to Python's built-in uuid module and can shadow it or break installs. Delete the line; import uuid works without it.
- **httpx** (DD004): Without a version constraint, any future release including breaking ones will be installed. Pin it exactly in an app, or use a bounded range in a library.
- **mock** (DD002): This backports functionality that the standard library has provided since Python 3.3, but your target is 3.12. Remove it and use unittest.mock, or add a marker for older Python versions.
- **importlib-metadata** (DD002): This backports functionality that the standard library has provided since Python 3.10, but your target is 3.12. Remove it and use importlib.metadata, or add a marker for older Python versions.
- **pyyaml** (DD006): This package appears twice with conflicting constraints, which can confuse resolvers and make the installed version unpredictable. Merge the two lines into a single requirement.
- **six** (DD003): six is a Python 2/3 compatibility layer, and on Python 3.12 it is only needed if a dependency still imports it. Drop it once your own code no longer imports it.
- **tenacity** (DD005): The lower bound has no upper limit, so future releases can change behavior and break reproducibility. Pin an exact version, or use a lock file to freeze the resolved set.


Note: the model calls the pyyaml duplicate "conflicting"; it is not (both lines allow 6.0.1). The finding itself (DD006, duplicate) is correct; explanations are reworded by the model and can be loose like this.
