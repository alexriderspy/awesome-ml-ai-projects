# CLI run

```
$ PYTHONPATH=src python -m house_price train
saved artifacts/house_price.joblib
test RMSE 0.4444  MAE 0.2885  (x $100k)
80% band coverage 0.791, mean width 0.914

$ PYTHONPATH=src python -m house_price predict --MedInc 8 --Latitude 37.44 --Longitude -122.14
predicted median value: $447,793  (80% band $361,860 - $504,308)
$ PYTHONPATH=src python -m house_price predict --MedInc 3 --Latitude 36.74 --Longitude -119.79
predicted median value: $78,359  (80% band $59,982 - $86,301)
```
