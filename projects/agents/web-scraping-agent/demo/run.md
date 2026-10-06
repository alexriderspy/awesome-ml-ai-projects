# Demo runs (deepseek-flash)

Real CLI runs with `LLM_MODEL=deepseek-flash` through `https://api.deepseek.com`.

## 1. Local practice site, schema generated from the description

The practice sites were served with `python -m http.server 8765 --bind 127.0.0.1` from `eval/sites/`.
No `--schema` is passed, so the agent first asks the model for a schema, then follows "Older postings →" to page 2.

```bash
PYTHONPATH=src python -m scrape_agent http://127.0.0.1:8765/jobs/page1.html \
  "job titles, company, location, whether remote, and the minimum salary"
```

```
[1] fetch_page({"url": "http://127.0.0.1:8765/jobs/page1.html"}) -> URL: http://127.0.0.1:8765/jobs/page1.html
[2] save_records({"records": "<5 records>"}) -> Saved 5, skipped 0 duplicates, rejected 0. Total records: 5.
[2] fetch_page({"url": "http://127.0.0.1:8765/jobs/page2.html"}) -> URL: http://127.0.0.1:8765/jobs/page2.html
[3] save_records({"records": "<4 records>"}) -> Saved 4, skipped 0 duplicates, rejected 0. Total records: 9.
[4] finish({"summary": "Scraped 9 job postings across 2 pages of the Harborline Jobs listing (page 2 stated no older postings, so the listing ended). Recorded job_id, title, company, location, remote flag, and minimum salary (null for the one posting without a listed salary)."}) -> Done.

schema: {"type": "object", "properties": {"job_id": {"type": "string", "description": "Unique identifier for the job posting, e.g. the posting ID or slug from its URL. Format: free-text string, e.g. \"1234567\" or \"senior-engineer-acme-2024\"."}, "job_title": {"type": "string", "description": "Title of the position as listed, e.g. \"Senior Software Engineer\". Format: free-text string."}, "company": {"type": "string", "description": "Name of the hiring company, e.g. \"Acme Corp\". Format: free-text string."}, "location": {"type": "string", "description": "Work location as listed, e.g. \"Berlin, Germany\" or \"New York, NY, USA\". Format: free-text string; use \"Unknown\" if not stated."}, "is_remote": {"type": "boolean", "description": "Whether the role is remote. Format: true if remote or remote-friendly is stated, false if on-site or hybrid only, false if unclear."}, "min_salary": {"type": "number", "description": "Minimum of the advertised salary range, as a plain number with no currency symbols or separators, e.g. 65000. Format: numeric value in the currency stated on the page (default USD); omit if no salary is given."}}, "required": ["job_id", "job_title", "company"], "key": "job_id"}
pages fetched: 2 | steps: 4 | stop: finished | records: 9
[
  {
    "job_id": "backend-engineer-payments",
    "job_title": "Backend Engineer, Payments",
    "company": "Lumen Ledger",
    "location": "Austin, TX",
    "is_remote": false,
    "min_salary": 140000
  },
  {
    "job_id": "data-analyst",
    "job_title": "Data Analyst",
    "company": "Quarry Health",
    "location": "Remote (US)",
    "is_remote": true,
    "min_salary": 85000
  },
  {
    "job_id": "junior-frontend-developer",
    "job_title": "Junior Frontend Developer",
    "company": "Tidepool Learning",
    "location": "Portland, OR",
    "is_remote": false,
    "min_salary": 72000
  },
  {
    "job_id": "site-reliability-engineer",
    "job_title": "Site Reliability Engineer",
    "company": "Northgate Freight",
    "location": "Remote (Canada)",
    "is_remote": true,
    "min_salary": 130000
  },
  {
    "job_id": "product-designer",
    "job_title": "Product Designer",
    "company": "Saltmarsh Studio",
    "location": "Brooklyn, NY",
    "is_remote": false,
    "min_salary": null
  },
  {
    "job_id": "machine-learning-engineer",
    "job_title": "Machine Learning Engineer",
    "company": "Quarry Health",
    "location": "Remote (US)",
    "is_remote": true,
    "min_salary": 155000
  },
  {
    "job_id": "qa-automation-engineer",
    "job_title": "QA Automation Engineer",
    "company": "Brightwater Bank",
    "location": "Charlotte, NC",
    "is_remote": false,
    "min_salary": 95000
  },
  {
    "job_id": "technical-writer",
    "job_title": "Technical Writer",
    "company": "Lumen Ledger",
    "location": "Austin, TX",
    "is_remote": false,
    "min_salary": 78000
  },
  {
    "job_id": "mobile-developer-android",
    "job_title": "Mobile Developer (Android)",
    "company": "Kettle & Co",
    "location": "Remote (EU)",
    "is_remote": true,
    "min_salary": 90000
  }
]
```

## 2. One public page: books.toscrape.com (a sandbox site made for scraping practice)

Single page only (`--max-pages 1`). The site has no robots.txt (404), and the fetcher checks robots before every host.

```bash
PYTHONPATH=src python -m scrape_agent https://books.toscrape.com/ \
  "book titles, prices in GBP and star rating" --max-pages 1
```

```
[1] fetch_page({"url": "https://books.toscrape.com/"}) -> URL: https://books.toscrape.com/
[2] save_records({"records": "<20 records>"}) -> Saved 20, skipped 0 duplicates, rejected 0. Total records: 20.
[3] finish({"summary": "Extracted 20 books (title, price in GBP, star rating) from page 1 of books.toscrape.com; page cap of 1 reached, so no further pages fetched."}) -> Done.

schema: {"type": "object", "properties": {"title": {"type": "string", "description": "Full book title as shown on the page, e.g. 'The Midnight Library'"}, "price_gbp": {"type": "number", "description": "Price in British pounds as a plain number without the '\u00a3' symbol, e.g. 9.99"}, "star_rating": {"type": "number", "description": "Star rating out of 5, numeric value allowing half stars, e.g. 4 or 4.5"}}, "required": ["title", "price_gbp", "star_rating"], "key": "title"}
pages fetched: 1 | steps: 3 | stop: finished | records: 20
[
  {
    "title": "A Light in the Attic",
    "price_gbp": 51.77,
    "star_rating": 3
  },
  {
    "title": "Tipping the Velvet",
    "price_gbp": 53.74,
    "star_rating": 1
  },
  {
    "title": "Soumission",
    "price_gbp": 50.1,
    "star_rating": 1
  },
  {
    "title": "Sharp Objects",
    "price_gbp": 47.82,
    "star_rating": 4
  },
  {
    "title": "Sapiens: A Brief History of Humankind",
    "price_gbp": 54.23,
    "star_rating": 5
  }
]
... (15 more records, trimmed here)
```

All 20 titles, prices and ratings were checked against the page HTML: 20/20 correct.

What this run taught us: the first version of the cleaner dropped CSS classes, and this site stores
the rating only as a class (`<p class="star-rating Three">`). The model still returned ratings on
that first run, but they could not have come from the page text it was given — they came from the
model's memory of this well-known sandbox. The cleaner now keeps classes that contain "rating" and
uses an anchor's `title` attribute when the visible text is cut short ("A Light in the ..."), and the
run above is after that fix.
