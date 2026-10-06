# Demo run: the two-file bug

Real transcript of the agent fixing `tasks/parcel-weights` with deepseek-flash. The bug spans `units.py` (wrong kg factor, no pounds) and `shipping.py` (compares grams against kilogram limits).

```bash
export LLM_BASE_URL=https://api.deepseek.com LLM_API_KEY=... LLM_MODEL=deepseek-flash
PYTHONPATH=src python -m mini_coder parcel-weights
```

Output (file bodies the agent wrote are shown in code blocks):

````text
task: parcel-weights
issue: Almost every parcel is classed as 'large'. A 1.5 kg parcel should be 'small'. Pounds ('lb') are also not supported yet (1 lb = 453.592 g).

[step 1] model: I'll start by listing the files and reading the failing tests and relevant code.

[step 1] list_files({})
  -> parcels/__init__.py
     parcels/shipping.py
     parcels/units.py
     tests/test_parcels.py

[step 2] read_file({"path": "tests/test_parcels.py"})
  -> import pytest
     
     from parcels.shipping import parcel_class
     from parcels.units import to_grams
     
     
     def test_units():
         assert to_grams(1, "kg") == 1000
         assert to_grams(2, "lb") == pytest.approx(907.184)
         with pytest.raises(ValueError):
             to_grams(1, "stone")
     
     
     def test_classes():
         assert parcel_class([(1.5, "kg")]) == "small"
         assert parcel_class([(1, "kg"), (900, "g"), (5, "oz")]) == "medium"
         assert parcel_class([(3, "lb"), (500, "g")]) == "small"
         assert parcel_class([(9, "kg"), (3, "lb")]) == "large"
     

[step 2] read_file({"path": "parcels/shipping.py"})
  -> from .units import to_grams
     
     SMALL_MAX_G = 2000
     MEDIUM_MAX_G = 10000
     
     
     def parcel_class(items):
         """items: list of (value, unit). Returns 'small', 'medium' or 'large' by total weight."""
         total_kg = sum(to_grams(v, u) for v, u in items)
         if total_kg <= SMALL_MAX_G / 1000:
             return "small"
         if total_kg <= MEDIUM_MAX_G / 1000:
             return "medium"
         return "large"
     

[step 2] read_file({"path": "parcels/units.py"})
  -> GRAMS_PER = {"g": 1, "kg": 100, "oz": 28.3495}
     
     
     def to_grams(value, unit):
         try:
             return value * GRAMS_PER[unit]
         except KeyError:
             raise ValueError(f"unknown unit: {unit}") from None
     

[step 2] read_file({"path": "parcels/__init__.py"})
  -> 

[step 3] model: I found the bugs. In `shipping.py`, `to_grams` returns grams but the code treats the sum as kilograms (`/1000` divisor) — so almost everything exceeds the threshold and becomes "large". In `units.py`, `kg` is wrong (100 instead of 1000) and `lb` is missing.

[step 3] write_file({"path": "parcels/units.py", "content": "<221 chars>"})
```python
GRAMS_PER = {"g": 1, "kg": 1000, "oz": 28.3495, "lb": 453.592}


def to_grams(value, unit):
    try:
        return value * GRAMS_PER[unit]
    except KeyError:
        raise ValueError(f"unknown unit: {unit}") from None
```
  -> wrote parcels/units.py (221 chars)

[step 3] write_file({"path": "parcels/shipping.py", "content": "<371 chars>"})
```python
from .units import to_grams

SMALL_MAX_G = 2000
MEDIUM_MAX_G = 10000


def parcel_class(items):
    """items: list of (value, unit). Returns 'small', 'medium' or 'large' by total weight."""
    total_g = sum(to_grams(v, u) for v, u in items)
    if total_g <= SMALL_MAX_G:
        return "small"
    if total_g <= MEDIUM_MAX_G:
        return "medium"
    return "large"
```
  -> wrote parcels/shipping.py (371 chars)

[step 4] model: Now let me run the tests.

[step 4] run_tests({})
  -> ALL TESTS PASSED
     exit code 0
     ..                                                                       [100%]
     2 passed in 0.01s

[step 5] model: Fixed `units.py` (`kg` = 1000, added `lb` = 453.592) and `shipping.py` (compare the gram total against gram thresholds instead of dividing by 1000); all tests pass.

stopped: done after 5 steps, 7590 tokens (6668 prompt + 922 completion)
tests pass: True  tests untouched: True  SOLVED: True
````
