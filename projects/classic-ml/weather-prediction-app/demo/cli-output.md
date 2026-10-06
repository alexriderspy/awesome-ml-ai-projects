# CLI run

```
$ PYTHONPATH=src python -m weather London
London: 3653 days, 2016-09-29 .. 2026-09-29
MAE on the last 365 days (°C):
  persistence  1.98
  ridge        1.83
  gbm          1.76

latest archived day 2026-09-29: max 25.8 °C
forecast max for 2026-09-30: 22.9 °C (gbm)

$ PYTHONPATH=src python -m weather Delhi
Delhi: 3653 days, 2016-09-29 .. 2026-09-29
MAE on the last 365 days (°C):
  persistence  1.42
  ridge        1.33
  gbm          1.32

latest archived day 2026-09-29: max 30.8 °C
forecast max for 2026-09-30: 31.2 °C (gbm)

```
