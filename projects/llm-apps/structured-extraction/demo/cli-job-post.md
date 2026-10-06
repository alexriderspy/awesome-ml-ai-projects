# CLI run: job post (deepseek-flash)

Input: [`input-job-post.txt`](input-job-post.txt). Real output, unedited.

```bash
PYTHONPATH=src python -m extractor job_post demo/input-job-post.txt --samples 2
```

```json
{
  "data": {
    "title": "Computer Vision Engineer",
    "company": "Kestrel Robotics",
    "location": "Lisbon, Portugal",
    "work_mode": "hybrid",
    "employment_type": "full-time",
    "salary_min": 58000.0,
    "salary_max": 72000.0,
    "salary_currency": "EUR",
    "salary_period": "year",
    "min_years_experience": 3,
    "skills": [
      "Computer Vision",
      "Python",
      "OpenCV",
      "PyTorch",
      "ROS 2"
    ],
    "apply_by": "2025-11-20"
  },
  "confidence": {
    "title": 1.0,
    "company": 1.0,
    "location": 1.0,
    "work_mode": 1.0,
    "employment_type": 1.0,
    "salary_min": 0.5,
    "salary_max": 0.5,
    "salary_currency": 1.0,
    "salary_period": 1.0,
    "min_years_experience": 1.0,
    "skills[0]": 0.5,
    "skills[1]": 1.0,
    "skills[2]": 1.0,
    "skills[3]": 1.0,
    "skills[4]": 1.0,
    "apply_by": 1.0
  },
  "attempts": 1,
  "errors_fixed": []
}
```

`salary_min`/`salary_max` get 0.5 because "58000" never appears literally in the text (it says "€58k"), even though both samples agree. "Computer Vision" as a skill also gets 0.5: one of the two extra samples left it out.
