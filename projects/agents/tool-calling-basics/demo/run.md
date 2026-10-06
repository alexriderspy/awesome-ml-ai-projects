# Demo runs

Real runs of the CLI on 2026-10-06 with `deepseek-flash` through `https://api.deepseek.com`
(`PYTHONPATH=src`, `LLM_*` variables set). The weather in run 1 is live Open-Meteo data. Output is unedited.

Things worth noticing:

- Run 1: the model asks for both cities in one reply (`parallel x2`); both results go back with their own `tool_call_id`.
- Run 2: the second run searches the note the first run saved, because both use the same JSON file.
- Run 3: the unit tool fails twice; the error text goes back to the model, which works around it with the calculator. (Its list of "length units" in the answer wrongly includes `c`, the Celsius code from the error message.)
- Run 4: the model sent the two calls in parallel even though the second depends on the first. It got the right number only because it did 2.5 × 3 in its head when writing the second call.

## 1. Parallel calls + live Open-Meteo weather

```console
$ python -m tool_calling "What is the weather in Pune and in Toronto right now? Which one is more humid?"
Trace:
  [step 1 (parallel x2)] get_weather({"city": "Pune"}) -> {"city": "Pune", "country": "India", "local_time": "2026-10-06T14:00", "temperature_c": 33.0, "humidity_pct": 30, "wind_kmh": 7.5, "conditions": "mainly clear"}
  [step 1 (parallel x2)] get_weather({"city": "Toronto"}) -> {"city": "Toronto", "country": "Canada", "local_time": "2026-10-06T04:30", "temperature_c": 4.2, "humidity_pct": 68, "wind_kmh": 7.7, "conditions": "clear sky"}

Answer (2 model calls):
Here's the current weather:

**Pune, India** — 33.0 °C, humidity 30%, wind 7.5 km/h, mainly clear (local time 14:00)

**Toronto, Canada** — 4.2 °C, humidity 68%, wind 7.7 km/h, clear sky (local time 04:30)

**Toronto is more humid** — 68% vs. Pune's 30%.
```

## 2. Notes: add, then search (two separate runs, same file)

```console
$ python -m tool_calling --notes demo-notes.json "Save a note: the car service is booked for Saturday at 10am, tag it car"
Trace:
  [step 1] add_note({"text": "The car service is booked for Saturday at 10am.", "tags": ["car"]}) -> {"saved": {"id": 1, "text": "The car service is booked for Saturday at 10am.", "tags": ["car"], "created": "2026-10-06T14:02:44"}}

Answer (2 model calls):
Saved — note #1: "The car service is booked for Saturday at 10am." with the tag `car`.
```

```console
$ python -m tool_calling --notes demo-notes.json "When is the car service? Look in my notes."
Trace:
  [step 1 (parallel x2)] search_notes({"query": "car service"}) -> [{"id": 1, "text": "The car service is booked for Saturday at 10am.", "tags": ["car"], "created": "2026-10-06T14:02:44"}]
  [step 1 (parallel x2)] search_notes({"query": "car"}) -> [{"id": 1, "text": "The car service is booked for Saturday at 10am.", "tags": ["car"], "created": "2026-10-06T14:02:44"}]

Answer (2 model calls):
Your car service is booked for **Saturday at 10am** (note from 2026-10-06, tagged "car").
```

## 3. Error path: the tool error goes back to the model

```console
$ python -m tool_calling "Convert 5 parsecs to kilometres with the unit converter."
Trace:
  [step 1] unit_convert({"value": 5, "from_unit": "pc", "to_unit": "km"}) -> !! Error: unit_convert failed: UnitError: unknown unit 'pc'. Supported: c, cm, cup, f, floz, ft, g, gal, imp_gal, in, k, kg, km, l, lb, m, m3, mg, mi, ml, mm, nmi,...
  [step 2] unit_convert({"from_unit": "parsec", "to_unit": "km", "value": 5}) -> !! Error: unit_convert failed: UnitError: unknown unit 'parsec'. Supported: c, cm, cup, f, floz, ft, g, gal, imp_gal, in, k, kg, km, l, lb, m, m3, mg, mi, ml, mm, ...
  [step 3] calculator({"expression": "5 * (648000/pi) * 149597870.7"}) -> 154283879074568.38

Answer (4 model calls):
The unit converter doesn't know parsecs — it rejected both `pc` and `parsec` (its supported length units are only c, cm, ft, in, km, m, mi, nmi, yd, etc.).

So I computed it from the definition instead (1 pc = 648000/π au, 1 au = 149 597 870.7 km):

**5 pc = 1.5428387907456838 × 10¹⁴ km** (about 154 trillion km, ≈ 1.543 × 10¹⁴ km).

For reference, that's roughly 5 × 206 265 au ≈ 1.03 million au per... i.e. 1 031 324 au. If you'd like, I can express it in a supported unit such as miles instead.
```

## 4. Chaining tools: convert, then calculate

```console
$ python -m tool_calling "A recipe needs 2.5 cups of milk per batch. I am making 3 batches. How many millilitres is that in total?"
Trace:
  [step 1 (parallel x2)] calculator({"expression": "2.5 * 3"}) -> 7.5
  [step 1 (parallel x2)] unit_convert({"value": 7.5, "from_unit": "cup", "to_unit": "ml"}) -> 7.5 cup = 1774.411774 ml

Answer (2 model calls):
You need **7.5 cups** total (2.5 × 3 batches), which is **1774.41 ml** (about 1.77 litres).
```

