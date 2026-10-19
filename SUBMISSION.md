# HW4 — submission

**AI assistance:** Claude Code (Anthropic) was used to help draft the plan, code, tests and text; I reviewed, ran and edited everything.

---

## Part A — Plan on paper (Easy)

> Commit this whole part before any `.py` file exists.

### A1 — The steps

Every question in the set has the same shape: *two or three named districts → one
or two facts per district → a derived ratio per district → a comparison → a name
plus one rounded number*. The task therefore splits into seven steps. Steps S2–S4
are the inside of the `lookup` tool, S5 is the `calculate` tool, S1 and S6 are the
model's job, and S7 is my loop / harness.

| # | Step | What goes in (types) | What comes out (types) | When it goes wrong | Tool, loop, or model? |
|---|---|---|---|---|---|
| S1 | **Plan the question** — read it, list the districts, the facts needed for each, and the formula | `question: str` | `plan: list[(district: str, field: str)]` + a formula in words, e.g. *density = population_2025 / area_km2* | Question names a district that does not exist → S2 reports it; the model must not invent a value. Unclear metric (e.g. "water per day") → the model states the unit it assumes (litres, 365 days). | **model** |
| S2 | **Resolve the district name** | `district: str` (free text, any case) | `canonical: str`, one of the 12 names in NR-00, or `"Region"` for region-wide facts | No exact match → error `{"error": "no district named 'X'; did you mean A or B?"}` with the closest names. Never auto-correct: `Ossbridge` and `Ossford` are both real, so a typo could silently pick the wrong one. Empty / non-string / > 50 chars → error. | **tool** (`lookup`, internal) |
| S3 | **Pick the valid document** | `canonical: str` | `doc_id: str` (exactly one current profile) + `notices: list[str]` (correction notices for it) | 0 current profiles → error `"no current profile for X"`. > 1 current profile → error `"ambiguous: NR-a, NR-b"` (never guess). Archived profiles (title contains `ARCHIVED`) are **never** used, only mentioned in a `note`. | **tool** (`lookup`, internal) |
| S4 | **Extract one fact, apply corrections, normalise the unit** | `doc_id: str`, `field: str` (fixed enum) | `{"value": float, "unit": str, "source": str, "evidence": str (≤ 300 chars), "note": str (optional)}` | Field not in enum → error listing valid fields. Pattern not found → error `"field F is not available for X"`. Number cannot be parsed → error, never `0`. Unknown unit → error. A correction notice overrides the profile value and becomes the `source`. Water in m³ is converted to ML (÷ 1,000, NR-15) and the `note` says so. | **tool** (`lookup`, internal) |
| S5 | **Compute** a derived number | `expression: str`, e.g. `"44675 / 921.4"` (numbers, `+ - * / ** ( )` only) | `{"expression": str, "result": float}` (full precision, not rounded) | Syntax error, name, call, attribute, string → `{"error": "not allowed in expression: Call"}`, nothing is executed. Division by zero → error. Exponent > 100 or result > 1e15 → error. > 300 chars → error. | **tool** (`calculate`) |
| S6 | **Compare, round and answer** | S4 facts and S5 results (`float`) | text ending in `ANSWER: <name or yes/no> \| <number>` (`str`) | A tool returned an error → fix the name / field and call again instead of guessing. Tie → say so, still give one line. Rounding happens **only here**, once. | **model** |
| S7 | **Orchestrate and check** — call the API, run requested tools, return results, stop, log, score | model messages; `tool_calls: list` (arguments are JSON **strings**) | one tool message per `tool_call_id`; a log `dict` per question; `(name: str, number: float)` parsed from `ANSWER:`; `correct: bool` | Invalid JSON / missing key / unknown tool → send a tool result containing an error (the model can retry). Round limit reached → stop and mark **unanswered**. No `ANSWER:` line → unanswered. API error → retry with back-off, then unanswered. | **loop** (my Python code) |

**How the steps connect:**

```text
question ──► S1 plan (model)
               │ for every (district, field) in the plan
               ▼
     ┌──────────────────────── lookup tool ─────────────────────────┐
     │ S2 resolve name ──► S3 pick document ──► S4 extract/correct/  │
     │                                              normalise        │
     └───────────────────────────────────────────────────────────────┘
               │ value, unit, source           (an error goes back to S1: re-plan)
               ▼
          S5 calculate (tool) ◄── expression the model writes from the S4 values
               │ result (unrounded float)
               ▼
          S6 compare, round, "ANSWER: name | number" (model)
               │
               ▼
          S7 parse ANSWER line ──► score against questions.json ──► outputs/ log

S7 (the loop) also wraps every arrow between the model and a tool.
```

In one line: `S1 → (S2 → S3 → S4) × n → S5 × m → S6 → S7`, with `n` = number of
facts (2–6 here) and `m` = number of calculations (1–4).

**Why the set is complete and does not overlap.** Every question needs: knowing
*what* to fetch (S1), fetching it (S2–S4), arithmetic (S5), and turning numbers
into an answer (S6); S7 is the only part that talks to the API. Each decision is
made in exactly one step: names only in S2, which document is valid only in S3,
raw text only in S4, arithmetic only in S5, rounding and the "winner" only in S6.
The model never decides which document is valid, and the tools never decide which
district wins.

**What I am assuming:**

- **Year.** "2025" = 2025 census, 2025 fiscal-year budget, calendar-2025 water use
  (NR-00). Pupils and schools = school year 2025/26. 2020 population only for growth.
- **Archived profiles** (NR-13, NR-14, title contains `ARCHIVED`) are never used for
  a value; they are superseded (NR-00).
- **Corrections** (NR-16) take precedence over the profile they correct (NR-00), so
  Brightwater's area is 921.4 km², not 912.4. They are applied *inside* `lookup`, so
  the model cannot forget them.
- **Units.** Water is normalised to megalitres (1 ML = 1,000 m³, NR-15), so
  Lindenmoor's 2,151,400 m³ = 2,151.4 ML. 1 ML = 1,000,000 litres. "Per day" = ÷ 365
  (2025 is not a leap year). Budgets stay in **million tenge**; the model converts to
  tenge or thousand tenge as the question asks. Tariff in tenge per m³.
- **Percentages.** Growth % = (new − old) / old × 100; "percentage points" = the
  difference of two such percentages.
- **Rounding.** Never round intermediate values; round once at the end.
- **Districts.** Exactly the 12 names in NR-00; `Ossbridge` ≠ `Ossford`.

**The assumption the answer is most sensitive to:** that `lookup` returns the *one*
valid 2025 value — i.e. that archived profiles and corrections can be recognised
from the document title, and there is exactly one current profile per district. If
that fails, the error is silent: Q-09 changes from **0.6** to **0.1** with the
uncorrected 912.4 km², and any Tarnvale/Kelmarsh question goes wrong if NR-13/NR-14
are read. Other assumptions (365 days, ML conversion) produce an obviously wrong
order of magnitude; this one produces a plausible wrong number. That is why S3/S4
are code, not model work.

### A2 — The two tools

#### `lookup`

Design choice: **structured lookup** (`district` + `field` → one number), not
free-text search. The model never sees whole documents; it gets one value, its
unit, the document it came from and one evidence sentence (≤ 300 characters).

```json
{
  "type": "function",
  "function": {
    "name": "lookup",
    "description": "Look up ONE official 2025 fact about a district of the Nine Rivers Region (or a region-wide fact) and get back the number, its unit and the source document id. Archived 2019 profiles are ignored and correction notices are already applied, so the value returned is the one to use. Water use is always returned in megalitres (1 ML = 1,000 cubic metres = 1,000,000 litres). Budgets are in million tenge. Call this once per fact you need; never guess a number. If the district name is not recognised you get an error with suggestions - check the spelling (Ossbridge and Ossford are two different districts).",
    "parameters": {
      "type": "object",
      "properties": {
        "district": {
          "type": "string",
          "description": "District name, e.g. 'Brightwater'. Use 'Region' for region-wide facts (water tariffs)."
        },
        "field": {
          "type": "string",
          "enum": [
            "population_2025", "population_2020", "area_km2",
            "budget_2025_million_tenge", "water_use_2025_megalitres",
            "schools", "pupils_2025_26", "paved_road_km", "founded_year",
            "water_tariff_2025_tenge_per_m3", "water_tariff_2024_tenge_per_m3"
          ],
          "description": "Which fact to return."
        }
      },
      "required": ["district", "field"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"district": "Brightwater", "field": "area_km2", "value": 921.4, "unit": "km2", "source": "NR-16", "evidence": "The correct area is 921.4 square kilometres.", "note": "correction notice NR-16 overrides NR-05 (which says 912.4)"}` |
| success, unit converted | `{"district": "Lindenmoor", "field": "water_use_2025_megalitres", "value": 2151.4, "unit": "ML", "source": "NR-08", "evidence": "Households used 2,151,400 cubic metres of water during 2025", "note": "converted from 2,151,400 cubic metres (1 ML = 1,000 m3, NR-15)"}` |
| misspelled name | `{"error": "no district named 'Ossbrige'; did you mean Ossbridge or Ossford?"}` |
| unknown name, nothing similar | `{"error": "no district named 'Atlantis'. Valid names: Ossbridge, Ossford, ..., Region"}` |
| unknown field | `{"error": "unknown field 'density'. Valid fields: population_2025, ..."}` |
| fact not in the document / unparsable number | `{"error": "field 'water_tariff_2025_tenge_per_m3' is not available for Brightwater ..."}` — never `0`, never a guess |
| only archived profile / two current profiles | `{"error": "no current (non-archived) profile for X"}` / `{"error": "ambiguous: several current profiles for X (NR-a, NR-b)"}` |
| wrong argument types (number, null, 10 kB string) | `{"error": "district must be a non-empty string of at most 50 characters"}` |

**Worst thing it could do with strange or dangerous input:** very little — it only
reads a fixed in-memory table built from `corpus.jsonl`, never opens a path or runs
anything built from the input, and strings are length-limited before fuzzy
matching. The realistic worst case is **a plausible wrong answer**: e.g. if fuzzy
matching auto-corrected `Ossbrige` to the wrong neighbour, or if a correction were
missed. That is why it refuses instead of auto-correcting, and why every result
names its source document so a mistake can be traced.

#### `calculate`

```json
{
  "type": "function",
  "function": {
    "name": "calculate",
    "description": "Evaluate ONE arithmetic expression exactly and return the unrounded result. Allowed: numbers (no thousands separators: write 44675, not 44,675), + - * / ** and parentheses. No variables, functions, units or text. Use it for every division, multiplication, percentage and difference instead of doing arithmetic in your head, e.g. '37203 / 758.6 - 44675 / 921.4'. Round only in your final answer.",
    "parameters": {
      "type": "object",
      "properties": {
        "expression": {
          "type": "string",
          "description": "Arithmetic expression, at most 300 characters, e.g. '(52904 - 48317) / 48317 * 100'."
        }
      },
      "required": ["expression"],
      "additionalProperties": false
    }
  }
}
```

| Case | What the tool returns |
|---|---|
| success | `{"expression": "44675 / 921.4", "result": 48.48599956587801}` |
| syntax error (`"44,675 / 921.4"`, `"2 +"`) | `{"error": "could not parse expression ... (write plain numbers without commas)"}` |
| forbidden element (name, call, attribute, string: `__import__('os')...`, `(1).__class__`) | `{"error": "not allowed in expression: Call"}` — refused while checking the syntax tree, **nothing is executed** |
| division by zero | `{"error": "division by zero"}` |
| huge numbers (`9**9**9`, `10**400`) | `{"error": "exponent too large (limit 100)"}` / `{"error": "result too large (limit 1e15)"}` — checked **before** the power is computed |
| empty / too long | `{"error": "expression must be a string of 1-300 characters"}` |

**Worst thing it could do with strange or dangerous input:** with `eval` it could run
any Python (delete files, read `.env` and leak the API key). Parsing with `ast` and
allowing only numeric constants, `BinOp` (+ − × ÷ **) and unary ± makes that
impossible. The remaining risk is **resource exhaustion** (`9**9**9` would run for
minutes and use gigabytes), blocked by an exponent limit, a result-size limit and a
length limit — and the model sending a *wrong but valid* expression, which no
calculator can catch.

### A3 — Q-09 by hand

```json
[
  {"role": "system", "content": "You answer questions about the Nine Rivers Region using ONLY the tools lookup and calculate ... End your reply with exactly one line: ANSWER: <name or yes/no> | <number>"},
  {"role": "user", "content": "Which district has the higher population density in 2025, Brightwater or Millbrook, and by how many residents per square kilometre?"},

  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_1", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"population_2025\"}"}},
    {"id": "call_2", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Brightwater\", \"field\": \"area_km2\"}"}},
    {"id": "call_3", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"population_2025\"}"}},
    {"id": "call_4", "type": "function", "function": {"name": "lookup", "arguments": "{\"district\": \"Millbrook\", \"field\": \"area_km2\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_1", "content": "{\"district\": \"Brightwater\", \"field\": \"population_2025\", \"value\": 44675, \"unit\": \"residents\", \"source\": \"NR-05\", \"evidence\": \"Census population: 39,902 in 2020 and 44,675 in 2025.\"}"},
  {"role": "tool", "tool_call_id": "call_2", "content": "{\"district\": \"Brightwater\", \"field\": \"area_km2\", \"value\": 921.4, \"unit\": \"km2\", \"source\": \"NR-16\", \"evidence\": \"The correct area is 921.4 square kilometres.\", \"note\": \"correction notice NR-16 overrides NR-05 (which says 912.4)\"}"},
  {"role": "tool", "tool_call_id": "call_3", "content": "{\"district\": \"Millbrook\", \"field\": \"population_2025\", \"value\": 37203, \"unit\": \"residents\", \"source\": \"NR-11\", \"evidence\": \"Census population: 34,590 in 2020 and 37,203 in 2025.\"}"},
  {"role": "tool", "tool_call_id": "call_4", "content": "{\"district\": \"Millbrook\", \"field\": \"area_km2\", \"value\": 758.6, \"unit\": \"km2\", \"source\": \"NR-11\", \"evidence\": \"The district, founded in 1897, stretches along the Mill Brook over 758.6 square kilometres and keeps 360.1 km of paved road.\"}"},

  {"role": "assistant", "content": null, "tool_calls": [
    {"id": "call_5", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"44675 / 921.4\"}"}},
    {"id": "call_6", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"37203 / 758.6\"}"}},
    {"id": "call_7", "type": "function", "function": {"name": "calculate", "arguments": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\"}"}}
  ]},
  {"role": "tool", "tool_call_id": "call_5", "content": "{\"expression\": \"44675 / 921.4\", \"result\": 48.48599956587801}"},
  {"role": "tool", "tool_call_id": "call_6", "content": "{\"expression\": \"37203 / 758.6\", \"result\": 49.041655681518584}"},
  {"role": "tool", "tool_call_id": "call_7", "content": "{\"expression\": \"37203 / 758.6 - 44675 / 921.4\", \"result\": 0.5556561156405735}"},

  {"role": "assistant", "content": "Brightwater: 44,675 residents / 921.4 km2 (corrected area, NR-16) = 48.49 per km2. Millbrook: 37,203 / 758.6 km2 = 49.04 per km2. Millbrook is denser by 0.556, i.e. 0.6 residents per km2.\nANSWER: Millbrook | 0.6"}
]
```

Three model rounds: (1) four lookups in parallel, (2) three calculations, (3) the
final answer.

**My arithmetic:**

- Brightwater density = 44,675 / 921.4 = **48.486** residents/km² (area from the
  correction notice NR-16, not the 912.4 in NR-05).
- Millbrook density = 37,203 / 758.6 = **49.042** residents/km².
- Difference = 49.042 − 48.486 = **0.556 → 0.6** (1 decimal). Millbrook is denser —
  matches `questions.json` (Millbrook, 0.6).
- The trap: with the uncorrected 912.4 km², Brightwater = 44,675 / 912.4 = 48.964 and
  the difference is 0.077 → **0.1**, which is wrong. The correction changes the
  answer, which is why it is my "most sensitive assumption" in A1.

### A4 — Why I split it this way

**Rejected alternative: no structured `lookup`, but a free-text `search(query)` tool
that returns matching sentences** (a mini-RAG), with the model doing name
resolution, archive filtering, corrections and unit conversion itself.

Why I did not choose it:

1. **The traps would move back into the model.** A search for "Brightwater area"
   returns *both* "912.4 square kilometres" (NR-05) and the correction (NR-16);
   "Tarnvale schools" returns NR-03 *and* NR-13. The model would have to notice and
   resolve the conflict on every question and every sample — exactly the kind of
   step it can get wrong. In my split these rules are code, written and tested once
   (S3, S4).
2. **Testability.** `lookup(district, field)` has a finite input space (13 × 11), and
   I can unit-test every trap without a model. A search tool can only be judged
   with the model in the loop.
3. **Cost.** A search returns several sentences per call; my lookup returns one
   number and one evidence sentence, so every later round of the loop re-sends
   fewer tokens.

What I give up: the structured lookup only answers the 11 fields I anticipated. A
question about a new kind of fact ("which river is Redfen on?") cannot be answered,
while search could. For this question set every needed fact is in the enum, so I
accept that. (A second alternative — one tool per derived metric, e.g.
`density(district)` — was rejected for the opposite reason: it hard-codes the
formulas of the answers, leaves the model nothing to reason about, and needs a new
tool for every new question type.)

---

## Part B — Build it and run it (Medium)

### What I changed from Part A while coding

The tool interfaces and the step split stayed as in Part A. Small changes made while coding:

- `lookup` also returns a `note` such as `"ignored archived profile NR-13"` when an archived profile exists, so the log shows the trap was seen (Part A only said archived profiles are never returned).
- The loop's argument check (`run_tool` in `tools.py`) also rejects **unexpected** argument names, not only missing ones, because `additionalProperties: false` in the schema is a request to the model, not a guarantee.
- `calculate`: `"44,675 / 921.4"` is parsed by Python as a *tuple*, so I added a specific error message for that case telling the model to drop the commas.
- Round limit set to 10 (see B3).
- **`reasoning_effort="none"` for all strategies.** My first S3 test on Q-09 failed with `400: Function tools with reasoning_effort are not supported for gpt-5.6-luna in /v1/chat/completions ... set reasoning_effort to 'none'`. The model's default is `medium`, so I had to set `none` for S3. I set the same value for S1 and S2 as well, otherwise S1/S2 would get hidden reasoning that S3 does not get, and the comparison would not be like for like. As a result, S1 really is "no reasoning", and in S2 the only reasoning is the visible chain of thought.
- Cost counts cached input tokens at their own price ($0.02 / 1M instead of $0.20 / 1M). The API reports `prompt_tokens_details.cached_tokens`, and in S3 most of each round's prompt is cached.

### B2 — Tests

Command: `python -m pytest -v` (no API key needed; `tests/test_tools.py` = tools, `tests/test_loop.py` = loop, parser, vote and scoring with a fake model).

```text
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-9.1.1, pluggy-1.7.0 -- C:\Users\Asus\css4007-hw4\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\Asus\css4007-hw4
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.15.1
collecting ... collected 41 items

tests/test_loop.py::test_loop_answers_every_tool_call_id_and_keeps_assistant_message PASSED [  2%]
tests/test_loop.py::test_loop_stops_at_round_limit_and_marks_unanswered PASSED [  4%]
tests/test_loop.py::test_parse_answer PASSED                             [  7%]
tests/test_loop.py::test_vote_majority_and_tie_break PASSED              [  9%]
tests/test_loop.py::test_scoring_rule PASSED                             [ 12%]
tests/test_tools.py::test_lookup_finds_2025_population PASSED            [ 14%]
tests/test_tools.py::test_lookup_all_three_profile_templates PASSED      [ 17%]
tests/test_tools.py::test_lookup_misspelled_name_suggests_and_does_not_guess PASSED [ 19%]
tests/test_tools.py::test_lookup_similar_names_are_different_districts PASSED [ 21%]
tests/test_tools.py::test_lookup_ignores_archived_profiles[Tarnvale-schools-29-27] PASSED [ 24%]
tests/test_tools.py::test_lookup_ignores_archived_profiles[Tarnvale-pupils_2025_26-10652-9870] PASSED [ 26%]
tests/test_tools.py::test_lookup_ignores_archived_profiles[Kelmarsh-pupils_2025_26-3268-2944] PASSED [ 29%]
tests/test_tools.py::test_lookup_ignores_archived_profiles[Kelmarsh-water_use_2025_megalitres-1739-1652] PASSED [ 31%]
tests/test_tools.py::test_lookup_applies_correction_notice PASSED        [ 34%]
tests/test_tools.py::test_lookup_converts_cubic_metres_to_megalitres PASSED [ 36%]
tests/test_tools.py::test_lookup_region_tariff PASSED                    [ 39%]
tests/test_tools.py::test_lookup_never_crashes[Atlantis-area_km2] PASSED [ 41%]
tests/test_tools.py::test_lookup_never_crashes[-area_km2] PASSED         [ 43%]
tests/test_tools.py::test_lookup_never_crashes[None-area_km2] PASSED     [ 46%]
tests/test_tools.py::test_lookup_never_crashes[42-area_km2] PASSED       [ 48%]
tests/test_tools.py::test_lookup_never_crashes[xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-area_km2] PASSED [ 51%]
tests/test_tools.py::test_lookup_never_crashes[Redfen-density] PASSED    [ 53%]
tests/test_tools.py::test_lookup_never_crashes[Redfen-None] PASSED       [ 56%]
tests/test_tools.py::test_lookup_never_crashes[../../.env-area_km2] PASSED [ 58%]
tests/test_tools.py::test_lookup_result_is_short PASSED                  [ 60%]
tests/test_tools.py::test_calculate_multiplication PASSED                [ 63%]
tests/test_tools.py::test_calculate_precedence_and_parentheses PASSED    [ 65%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[__import__('os').system('echo hi')] PASSED [ 68%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[(1).__class__] PASSED [ 70%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[9**9**9] PASSED [ 73%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[().__class__.__bases__[0].__subclasses__()] PASSED [ 75%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[open('.env').read()] PASSED [ 78%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[lambda: 1] PASSED [ 80%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly['a' * 10] PASSED [ 82%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[[1, 2]] PASSED [ 85%]
tests/test_tools.py::test_calculate_refuses_dangerous_input_quickly[x + 1] PASSED [ 87%]
tests/test_tools.py::test_calculate_division_by_zero PASSED              [ 90%]
tests/test_tools.py::test_calculate_huge_numbers_refused PASSED          [ 92%]
tests/test_tools.py::test_calculate_bad_syntax_and_length PASSED         [ 95%]
tests/test_tools.py::test_run_tool_validates_json_string_arguments PASSED [ 97%]
tests/test_tools.py::test_tool_definitions_shape PASSED                  [100%]

============================= 41 passed in 0.28s ==============================
```

### B3 — The loop

- **Round limit, and why:** `MAX_ROUNDS = 10` model calls per question (`strategies.py`). The hardest questions need 6 facts and about 4 calculations. If the model batches calls in parallel that is 3–4 rounds (Q-09 by hand: 3). If it makes one call per round it needs about 11, but that is slow and costly anyway. 10 leaves room for 2–3 retries after tool errors, and still stops a model that loops forever. This matters for cost, because every round sends the whole conversation again. When the limit is reached the question is saved with `"hit_round_limit": true` and counted as **unanswered**.
- **Where the logs are:** `outputs/run<N>/s3/Q-xx.json`. Each one has the full `messages` list, `rounds` (usage and seconds per model call) and `tool_calls` (round, id, tool, raw `arguments` string, result, `ms`). S1 and S2 logs are in `outputs/run<N>/s1|s2/`, and S2 also stores all 5 samples and the vote counts. `summary.json` in each folder holds the totals and the settings used.
- **Real Q-09 conversation compared with my A3 version, what is different** (`outputs/run1/s3/Q-09.json`):
  - **Round 1 is exactly as planned:** the same 4 lookups, sent in parallel in one message, with the same arguments (`{"district": "Brightwater", "field": "area_km2"}` etc.). `lookup` returned 921.4 with `"source": "NR-16"`, so the correction trap was handled by the tool, as designed.
  - **4 rounds instead of 3.** I expected all three calculations in one round. The model sent the two densities in parallel (round 2) and the difference `37203 / 758.6 - 44675 / 921.4` only in round 3, after it had seen the first results. In my earlier test run (same settings, same question) it even used 5 rounds, one `calculate` per round. So the number of rounds varies from run to run, while the lookups were the same every time.
  - **Tokens per round grow:** 713 → 1,117 → 1,236 → 1,311 input tokens, because each round re-sends the whole conversation (1,114–1,233 of them were cached).
  - **Final text:** `Millbrook has the higher 2025 population density by 0.556 residents per square kilometre.` / `ANSWER: Millbrook | 0.556`. It gives 0.556 instead of my rounded 0.6, because my prompt asks for at least 3 decimals; the scorer rounds it to 0.6. It does not mention NR-16 or the correction, although the note was in the tool result. The model used the value without explaining it.

### B4 — Three strategies

**What I kept the same:**

| Setting | Value (same for S1, S2, S3) |
|---|---|
| Model | `gpt-5.6-luna` (Chat Completions API) |
| Questions | all 20 from `data/questions.json`, same order, same text |
| `temperature` | 1.0 for every strategy (S2 needs > 0 so samples differ; S1/S3 use the same value so only the strategy changes). If the API refuses `temperature`, `Client` drops it for **every** call and records it in `summary.json → settings.dropped_parameters`. |
| `max_completion_tokens` | 4000 |
| `reasoning_effort` | `"none"` for every strategy (required for tools in Chat Completions, see above) |
| System prompt | the same rules + the same answer-format block (`ANSWER_FORMAT` in `strategies.py`). S1/S2 add all 17 documents, S3 adds instead "you do not have the documents, use the tools". |
| Strategy instruction (the only intended difference) | S1: "Answer directly. Do not show your working." · S2: "Think step by step ..." + k = 5 independent calls + majority vote · S3: tools + loop, max 10 rounds |
| Answer format | last line `ANSWER: <name or yes/no> \| <number>`, number with at least 3 decimals unless whole |
| Parser and scorer | one function each (`parse_answer`, `is_correct`) for all strategies |
| Token counting | `usage` of **every** API call: all 5 samples in S2, every round in S3 |
| Time | wall clock per question (`time.perf_counter`), calls run one after another (no parallel requests) |
| Price | from the OpenAI model page for gpt-5.6-luna: input $0.20, cached input $0.02, output $1.20 per 1M tokens. Cost = (input − cached) × 0.20 + cached × 0.02 + output × 1.20, per 1M |

**My rule for a correct answer** (written before the first full run):

A question is **correct** when both of these are true (`is_correct` in `run.py`):
1. the name in the `ANSWER:` line equals `answer` from `questions.json`, ignoring case and surrounding spaces, `*` and quotes (so `millbrook` is fine, but `Mill brook` or `Ossford` for `Ossbridge` is wrong);
2. the number, rounded to the question's `decimals`, is within one unit of the last digit of `value`: `|round(x, d) − value| ≤ 10^−d`.

**Unanswered** = no parsable `ANSWER:` line, the S3 round limit was reached, or the API failed after retries. Unanswered always counts as wrong. In S2 the vote is over `(name, number rounded to decimals)` pairs; a tie goes to the pair that appeared first.

Why this rule: the name check makes the "which district" part all-or-nothing. That is what the question asks, and it catches the Ossbridge/Ossford trap. The ±1 in the last digit allows for honest rounding differences: a model that rounds an intermediate value can be off by one in the last digit. But it still fails the real traps: the uncorrected Brightwater area gives 0.1 instead of 0.6 on Q-09, and cubic metres read as megalitres would be off by a factor of 1000. The prompt asks for at least 3 decimals, so that the model's own rounding does not decide the score.

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | 4 | 1 | 45,000 | 492 | 1.28 | 25.35 | 0.0017 |
| 1 | S2 think and vote (k = 5) | 15 | 0 | 227,300 | 20,967 | 10.66 | 215.41 | 0.0300 |
| 1 | S3 tools | 19 | 0 | 83,550 | 4,630 | 6.05 | 119.19 | 0.0148 |
| 2 | S1 direct | 5 | 1 | 45,000 | 527 | 1.29 | 29.97 | 0.0015 |
| 2 | S2 think and vote (k = 5) | 16 | 0 | 227,300 | 20,926 | 11.09 | 216.89 | 0.0297 |
| 2 | S3 tools | 19 | 0 | 81,121 | 4,689 | 5.27 | 102.63 | 0.0110 |

Generated by `python report.py` from `outputs/run1|run2/<strategy>/summary.json`; the console log of both runs is in `outputs/run_log.txt`. Cached input tokens (charged at $0.02/1M): S1 44,041 / 44,940, S2 225,664 / 227,000, S3 41,754 / 60,449 (run 1 / run 2). The API accepted `temperature` (`dropped_parameters: []`), so S2's samples really vary. Total cost of everything (tests, both runs, C1, measurement): about **$0.09**.

**Why 20 questions and this rule:** 20 is the whole set given, and a full run costs only ~$0.05, so I ran all of it twice instead of sampling fewer questions. The second run is the cheapest way to measure run-to-run noise (C4). The rule scores the name exactly and the number to the question's own precision ±1 in the last digit. A strategy cannot be "half right": a correct number with the wrong name (or `yes` instead of a name) is wrong, because the question asks for both.

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | ✗ | ✓ | ✓ |
| Q-02 | ✗ | ✓ | ✓ |
| Q-03 | ✗ | ✓ | ✓ |
| Q-04 | ✗ | ✓ | ✓ |
| Q-05 | ✗ | ✗ | ✓ |
| Q-06 | ✓ | ✓ | ✓ |
| Q-07 | ✗ | ✓ | ✓ |
| Q-08 | ✗ | ✗ | ✓ |
| Q-09 | ✗ | ✓ | ✓ |
| Q-10 | ✓ | ✓ | ✓ |
| Q-11 | ✗ | ✓ | ✓ |
| Q-12 | ✗ | ✗ | ✓ |
| Q-13 | ✓ | ✓ | ✓ |
| Q-14 | ✗ | ✗ | ✗ |
| Q-15 | ✗ | ✓ | ✓ |
| Q-16 | ✓ | ✓ | ✓ |
| Q-17 | ✗ (unanswered) | ✓ | ✓ |
| Q-18 | ✗ | ✓ | ✓ |
| Q-19 | ✗ | ✓ | ✓ |
| Q-20 | ✗ | ✗ | ✓ |
| **Total** | **4** | **15** | **19** |

Run 2 per question, the S3 rounds and tool calls per question, and the list of every wrong answer with the S2 vote counts are in `outputs/report.md`.

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

I re-ran S3 on Q-03, Q-08, Q-09, Q-13 and Q-17 (`python run.py --strategy s3 --run c1-vague --vague --questions ...`). The only change was that the `lookup` description became `"Looks things up."`. The parameter schema, including the `field` enum, stayed the same (checked in `test_tool_definitions_shape`). The "your description" column is from run 1. Logs: `outputs/c1-vague/s3/`.

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| Q-03 | 7 | 7 | Lindenmoor \| 5.34 ✓ | Lindenmoor \| 5.34 ✓ |
| Q-08 | 6 | 4 | Brightwater \| 72.456 ✓ | Brightwater \| 72.456 ✓ |
| Q-09 | 7 | 5 | Millbrook \| 0.556 ✓ | Millbrook \| 0.556 ✓ |
| Q-13 | 9 | 9 | Coldharbour \| 4.159 ✓ | Coldharbour \| 4.159 ✓ |
| Q-17 | 8 | 6 | Harrowfield \| 884.457 ✓ | Harrowfield \| 884.457 ✓ |

**What changed:** the answers did not change (5/5 in both). The vague version used the same or **fewer** calls, and fewer input tokens (15,448 for the five questions, against 20,848 for the same five in run 1). The lookup inputs were identical in kind: the same `district` + `field` pairs, and `Region` for the tariff. The differences:

- **Q-08:** with my description the model fetched the 2 populations as well, which it did not need (`{"district": "Brightwater", "field": "population_2025"}`). With the vague one it fetched only the water use and the tariff.
- **Q-09 / Q-17:** with the vague description the model put the whole computation into **one** `calculate` call (`"7146*1000*142.35/90212-(3862*1000*142.35/52904)"`), instead of computing each district first and the difference in a later round. That saved a round: 3 rounds instead of 4.

**Why:** in my design almost all of the "how to use it" information is in the **schema**, not the prose. The `field` enum lists all 11 legal names with their units in the name (`water_use_2025_megalitres`), and the `district` parameter description says "Use 'Region' for region-wide facts". The model reads the schema as part of the tool definition, so `"Looks things up."` takes away very little. The things my long description adds (archived profiles ignored, corrections applied, ML conversion) are guarantees that the tool enforces in code anyway. The model does not need to know them in order to call it correctly. The extra calls with my description probably come from "Call this once per fact you need; never guess a number", which nudges the model to fetch more. The limit of this test: if I had also removed the enum, the model would have to guess field names, and I would expect `unknown field` errors and retry rounds. So the description matters little *here* because the schema is strict. It would matter a lot for a free-text `lookup(query)`.

### C2 — Three mistakes explained

**S1 — Q-09, run 1 (got Brightwater 9.858, correct Millbrook 0.6).** Log `outputs/run1/s1/Q-09.json`, the whole reply:

> `Brightwater, by 9.858 residents per square kilometre.` / `ANSWER: Brightwater | 9.858`

With `reasoning_effort="none"` and "do not show your working", the model has to produce the name and the number as its first tokens. To get it right it would have to (1) find 4 numbers in 2,300 tokens of context, (2) notice that NR-16 overrides NR-05, (3) do two 5-digit divisions and (4) subtract, all inside one forward pass per token, with no intermediate tokens to hold partial results. 9.858 is not the result of any consistent formula: the uncorrected area gives 0.08, the corrected one 0.56. It is a *plausible-looking* number. S1 got the name right on only 10/20 questions in run 1 and the number right on 4. The questions it got right in both runs (Q-06, Q-10, Q-16) need only one addition or subtraction, with no division. So the failure is not about finding facts. It is about computation: a transformer generating the answer with no scratchpad has a fixed amount of computation per output token, and multi-step division does not fit into it.

**S2 — Q-12, run 1 (got Tarnvale 0.1, correct Tarnvale 64.4).** Log `outputs/run1/s2/Q-12.json`, `vote_counts = {'tarnvale | 0.1': 2, 'tarnvale | 63.8': 1, 'tarnvale | 64.3': 1, 'tarnvale | 64.0': 1}`. All 5 samples found the right four facts and the right winner. Two samples made the **same unit error**. Sample 1: `16,021.7 × 1,000,000 ÷ 13,904 = 1,152,597.814 tenge per pupil = 1.152598 thousand tenge per pupil` (it divided by 10⁶ instead of 10³). Sample 3 made the same mistake. The other three did the conversion right, but each had a slightly different mental division: 63.804, 64.297, and "64.???". Sample 5 literally wrote `1,152,? ` and `64.???`; my parser read that as 64.0, which is a flaw in my parser (it should reject `64.???`). The correct value is 64.38. So voting failed for two different reasons:

1. **Voting removes independent, random errors, not shared ones.** Self-consistency works when each sample is right with probability p > ½ and the errors are scattered, so the correct answer is the mode. Here the *same* misconception (million → thousand) appeared twice, so the wrong answer became the mode with 2 votes.
2. **For a continuous answer, the correct samples do not agree with each other.** Mental long division gives 63.8 / 64.3 / 64.0. All three are "almost right", but they are three different keys, so each gets 1 vote and they lose to the 2 identical wrong ones. The same thing happened in Q-05 (5 different values, `14258/14230/14277/14346/14219`, so the "mode" is just the first sample), Q-08 and Q-20, in both runs. Voting fixed the **names** (S2 picked the right district on 20/20 questions in run 1, and every vote was unanimous on the name) and the order of magnitude. It does not fix the last digits, because there the errors are a small spread, not a few outliers. In total 75 of the 100 individual samples in run 1 were correct, but only 15 of the 20 votes. A median vote on the number would have fixed Q-05, Q-08 and Q-20. A majority vote cannot.

**S3 — Q-14, run 1 (got `yes | 4.853`, correct Ashgrove 4.9).** Log `outputs/run1/s3/Q-14.json`:

```text
1 lookup {"district": "Tarnvale", "field": "water_use_2025_megalitres"} -> 5207
1 lookup {"district": "Tarnvale", "field": "population_2025"}            -> 71388
1 lookup {"district": "Ashgrove", "field": "water_use_2025_megalitres"} -> 4390
1 lookup {"district": "Ashgrove", "field": "population_2025"}            -> 58760
2 calculate {"expression": "5207 * 1000000 / 71388 / 365"}              -> 199.834...
2 calculate {"expression": "4390 * 1000000 / 58760 / 365"}              -> 204.686...
3 calculate {"expression":"4390 * 1000000 / 58760 / 365 - 5207 * 1000000 / 71388 / 365"} -> 4.85276...
final: "Ashgrove used more water, by 4.853 litres per resident per day.\n\nANSWER: yes | 4.853"
```

Every fact and every number is right, and the sentence even names Ashgrove. The model then filled the `<district name, or yes/no>` slot with `yes`, as if the question were a yes/no question. Run 2 made the same mistake on Q-15 (`Redfen has more pupils per school ... ANSWER: yes | 17.609`). These are the **only two** S3 errors in 40 answers, and both are formatting errors, not reasoning errors. That shows the principle. The calculator removes the error the model cannot control on its own: every division in S3 is exact, and S3 never had a number wrong in either run. Each arithmetic step that is done "in the head" has a small chance of a digit error, and those chances add up over a chain of 3–5 operations (S1, S2). In S3 that chance is zero for the arithmetic. What is left is the model's job of *interpreting* (which slot, which unit, which formula), and the tool cannot check that. My answer template mentions "yes/no", and that is ambiguous for a no-reasoning model. A fix would be to tell the model which kind of answer is expected per question (e.g. `ANSWER: <one of: Tarnvale, Ashgrove> | <number>`).

**Why the loop needed 4 rounds, and why each round costs more.** Q-14 took 4 rounds: (1) four parallel lookups, (2) two parallel calculations, (3) the difference, which depends on round 2's results (the model did not write it as one expression), (4) the answer. Rounds are only needed where there is a data dependency: facts → per-district values → difference → text. Input tokens per round: **719 → 1,157 → 1,304 → 1,406**. Chat Completions is stateless, so every round re-sends the system prompt, both tool definitions (~519 tokens, measured), the question and *all earlier tool calls and results*. Round n costs roughly 719 + Σ (tokens added in rounds < n), so the total grows quadratically with the number of rounds. Prompt caching softened this: in run 2, 60,449 of S3's 81,121 input tokens were cached, i.e. charged at a tenth of the price.

### C3 — Which strategy I would use, and what would change it

Averages over the two runs (from the B4 table):

| Strategy | Correct /20 | Input tok | Output tok | Median s / question | Cost per 20 questions |
|---|---:|---:|---:|---:|---:|
| S1 direct | 4.5 | 45,000 | 510 | 1.3 | $0.0016 |
| S2 think + vote (k = 5) | 15.5 | 227,300 | 20,947 | 10.9 | $0.0299 |
| S3 tools | **19** | 82,336 | 4,660 | 5.7 | $0.0129 |

**I choose S3 (tools).** It is the most accurate (19/20 in both runs, and its two errors were format slips, not wrong facts or wrong numbers). It is also **cheaper and faster than S2**: about 2.3× cheaper and about half the median latency. And it is the only strategy whose answers can be **audited**: each number in the log comes with its source document id and the exact expression that produced it.

- **Why not S2:** it pays ~19× the S1 cost and ~2.3× the S3 cost, and is still 3–4 questions worse, because its errors are arithmetic drift (Q-05, Q-08, Q-20) and a shared unit error (Q-12). Voting cannot remove those (C2). Its only advantage is that it needs no tool code.
- **Why not S1:** it is by far the cheapest and fastest (1.3 s, $0.0016), but 4–5/20 is worse than useless. The answers look confident (`Brightwater | 9.858`), so a reader cannot tell which ones to trust.

**Situations that would change my choice:**

1. **Questions with no arithmetic** (e.g. "which district was founded first?", or a yes/no comparison of two integers). S1 already got Q-06, Q-10 and Q-16 right in both runs. With nothing to compute, the calculator has no benefit and the loop only adds rounds → **S1**. (I would keep reasoning switched on; it is only off here because tools required it.)
2. **A strict latency limit (≤ 2 s per answer)** → **S1**, or a single S3 round with all lookups server-side. S3's median is 5–6 s because of 3–4 sequential model calls, and that cannot be done in parallel.
3. **1,000× more documents (~2.3M tokens).** S1/S2 become impossible (the corpus no longer fits in the context window), or they cost ~1000× more per call. S3's cost per question does not depend on corpus size, because `lookup` returns one number → **S3 even more clearly**, with an indexed `lookup` (final question 6).
4. **Very small budget but arithmetic still needed** → still **S3**: it is cheaper than S2 in my runs. Only if tokens had to be minimised at any accuracy would S1 win.
5. **No time to build or maintain tools, a one-off analysis, plenty of budget** → **S2**, with a median vote on the number instead of a majority vote, and reasoning switched on. It needs no code apart from the prompt.

### C4 — How sure I can be

- **Run-to-run difference:** S1 4 → 5 (3 questions flipped: Q-01, Q-13, Q-18), S2 15 → 16 (1 flip: Q-14), S3 19 → 19 (2 flips that cancelled out: Q-14 wrong in run 1, Q-15 wrong in run 2). So one run moves a score by about **±1 question (5 percentage points)**, and the set of wrong questions changes even when the score does not.
- **Is the S3–S2 gap bigger than that?** The gap is 3–4 questions, larger than the 1-question run-to-run noise. But the right test is a *paired* one (the same questions). In run 1 the discordant pairs (one strategy right, the other wrong) are 4 : 0 in favour of S3 (Q-05, Q-08, Q-12, Q-20). A sign test gives p = 2·(½)⁴ = **0.125**. In run 2 it is 4 : 1, p ≈ 0.38. Pooling both runs (8 : 1) gives p ≈ 0.04, but the two runs use the same 20 questions, so they are not independent evidence about *new* questions. The 95 % Wilson intervals overlap: S3 19/20 → [0.76, 0.99], S2 15/20 → [0.53, 0.89] (run 1) and 16/20 → [0.58, 0.92] (run 2). **S1 vs. S3 is settled**: the discordant pairs are 15 : 0 (run 1) and 14 : 0 (run 2), sign test p ≈ 0.0001. **S3 > S2 is likely but not proven** with 20 questions. It is also a claim about *this* question type, generated from one template.
- **How many questions would I need?** With S3 ≈ 95 % and S2 ≈ 77 %, about 20 % of questions are discordant, almost all in S3's favour. To get a sign test with p < 0.05 and 80 % power I need about 10–12 discordant pairs, i.e. **≈ 50–60 questions**. To estimate each accuracy to ±5 points (95 % CI) I would need ~ 75–100 questions per strategy. The questions should also be varied (not only "compare two districts by a ratio"), because the measurement also depends on my answer template (S3's two errors were template errors), on `reasoning_effort="none"`, and on a single model.
- **What this comparison cannot settle:** (1) whether S2 would beat S3 if reasoning were switched on. That is impossible in Chat Completions with tools for this model, but would be possible for S1/S2 alone, so my "S1/S2 without reasoning" is a controlled setting, not the best possible S1/S2. (2) Whether the 4-question gap holds on questions that need judgement rather than arithmetic. (3) The cost figures depend heavily on prompt caching: ~98 % of S1/S2 input tokens were cached; without the cache S2 would cost ~$0.07 instead of $0.03.

### Final questions

1. **What has actually run when the model sends `tool_calls`?** Nothing has run yet, only the model's text generation. A `tool_calls` message is just structured text: the model asks for `lookup(...)` and stops. No tool has run, no file has been read, no number has been computed. My loop decides whether to run it (`run_tool`), runs it on my machine, and sends the result back as a `tool` message. Only then does the model see a value. The same is true for invalid requests: in my S3 logs a bad request just gets an error result back.
2. **Why is `arguments` a string, and what goes wrong if you pass it straight in?** The model produces tokens, so `arguments` is text that *should* be JSON. It can be invalid JSON, have a missing or extra key, the wrong type, or arguments meant for another tool. If I passed the string straight in, `lookup('{"district": ...}')` would get the whole JSON as one positional argument and the call would fail with a TypeError. With `**json.loads(...)` and no checks, an unexpected key would raise and crash the loop, and a tool with dangerous parameters could be called with input I never checked. So `run_tool` parses the string, checks it is an object with exactly the required keys, and only then calls the function. Any failure becomes an error message for the model (tested in `test_run_tool_validates_json_string_arguments`).
3. **How many tokens do the two tool definitions add to every S3 request?** **519 tokens**, measured (`python measure_tools.py` → `outputs/measure_tools.json`). The same one-line request costs 9 prompt tokens without tools and 528 with them. With the vague `lookup` description it adds 383. My tiktoken estimate of the JSON (520) is almost exactly the same. These 519 tokens are paid on **every round**, so for an average S3 question (3.7 rounds) the tool definitions alone are ~1,900 input tokens. That is about a quarter of S3's input. Caching makes them cheap after the first round.
4. **How much more did S2 cost than S1?** $0.0300 vs $0.0017 in run 1 (**≈ 18×**) and $0.0297 vs $0.0015 in run 2 (≈ 20×). Input tokens are exactly **5.05×** (227,300 vs 45,000): the same prompt with the whole corpus is sent k = 5 times, plus the longer step-by-step instruction. Output tokens are **≈ 42×** (20,967 vs 492): 5 samples × ~210 tokens of written-out reasoning, against ~25 tokens for a direct answer. The cost ratio is much higher than 5× because output tokens are 6× more expensive than input, and S1/S2 input is ~98 % cached ($0.02/1M). So S2's bill is ~84 % output tokens. Its latency is ~8.5× S1's (10.7 s vs 1.3 s median), because I ran the 5 samples one after another.
5. **Which question needed the most rounds in S3, and why?** **Q-19 in run 1: 5 rounds** (every other question took 3–4; average 3.75). The facts came in one parallel round (4 lookups), but then the model sent the calculations **one per round**: `402.3 / 1015.7` (round 2), `244.6 / 677.1` (round 3), then the difference (round 4), then the answer (round 5). Nothing forced this: the two densities are independent and could have been one round, as in run 2 (4 rounds). Input tokens grew 713 → 1,151 → 1,212 → 1,271 → 1,352. The most *tool calls* were on Q-11 and Q-20 (10 each), which involve three districts (6 lookups + 4 calculations), but those still took only 4 rounds because the calls were parallel. So the number of rounds depends on how many *dependent* steps the model chooses to make, not on how many facts it needs.
6. **What would I change in `lookup` for 100,000 documents?** My `lookup` searches every title with a regex on each call and depends on fixed sentence patterns. With 100,000 documents I would extract the facts **once, offline**, into an indexed table (SQLite: `district, field, value, unit, source_doc, published, superseded_by`). Archived profiles and corrections would become links between rows, not title checks done at query time. For the long tail of facts that do not fit the schema I would add a second, search-style tool (BM25/embedding retrieval) that returns the top-k short passages with their doc ids. Its output size would have to be limited, because every passage is re-sent on every later round. Name resolution would also need a proper index (many more near-duplicate names than Ossbridge/Ossford), and the tool should return "ambiguous, candidates: …" more often instead of guessing.
7. **What stops `calculate` from running dangerous code? Could the model still make it misbehave?** It never calls `eval`/`exec`. `ast.parse(..., mode="eval")` only builds a syntax tree, and `_eval` walks it with a whitelist: numeric `Constant`, `BinOp` with + − × ÷ **, and unary ±. Anything else (`Call`, `Attribute`, `Name`, `Subscript`, strings, lambdas) is refused before any of it runs, so `__import__('os')…` and `(1).__class__` are refused (tests). Resource abuse is limited: input is at most 300 characters, the exponent is at most 100 and is checked with a log₁₀ estimate *before* the power is computed (so `9**9**9` returns at once), every result must stay below 1e15, and deep nesting is caught as `RecursionError`. The model can still make it give a **wrong answer**: a valid but wrong expression (wrong operand order, dividing by the 2020 figure, forgetting ÷ 365) is computed faithfully. The calculator removes arithmetic errors, not reasoning errors.
8. **Where did tools help most, and where not at all?** They helped most on questions where the answer needs a **chain of multiplications or divisions with large numbers, or a unit conversion**: Q-05 and Q-20 (million tenge → tenge per resident, 5-digit results), Q-08 (ML → m³ × tariff), Q-12 (million → thousand tenge per pupil). S2 got these wrong in **both** runs, and S3 got them right in both, because the calculator makes the arithmetic exact and the `lookup` units fix the conversion base. They did not help at all on Q-06, Q-10 and Q-16 (one integer addition or subtraction): S1, S2 and S3 were all right there in both runs, so the extra rounds were pure cost. Tools also did not fix the one thing that is left to the model, the final answer format (Q-14 and Q-15: `yes` instead of the district name).
