# HW4 — submission

**AI assistance:** <!-- STUDENT: fill in honestly, e.g. "Claude Code (Anthropic) was used to help draft the plan, code, tests and text; I reviewed, ran and edited everything." -->

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

<!-- what changed in your plan, and why. "None" is an answer too. -->

### B2 — Tests

```text
<!-- pytest output -->
```

### B3 — The loop

- Round limit, and why:
- Where the logs are:
- Real Q-09 conversation compared with my A3 version, what is different:

### B4 — Three strategies

**What I kept the same:**

<!-- model, temperature, k, prompts, answer format, anything else -->

**My rule for a correct answer** (written before the first full run):

| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens | Median seconds per question | Total seconds | Cost ($) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | S1 direct | | | | | | | |
| 1 | S2 think and vote (k = ) | | | | | | | |
| 1 | S3 tools | | | | | | | |
| 2 | S1 direct | | | | | | | |
| 2 | S2 think and vote (k = ) | | | | | | | |
| 2 | S3 tools | | | | | | | |

**Per question (run 1):**

| Question | S1 | S2 | S3 |
|---|:---:|:---:|:---:|
| Q-01 | | | |
| Q-02 | | | |
| Q-03 | | | |
| Q-04 | | | |
| Q-05 | | | |
| Q-06 | | | |
| Q-07 | | | |
| Q-08 | | | |
| Q-09 | | | |
| Q-10 | | | |
| Q-11 | | | |
| Q-12 | | | |
| Q-13 | | | |
| Q-14 | | | |
| Q-15 | | | |
| Q-16 | | | |
| Q-17 | | | |
| Q-18 | | | |
| Q-19 | | | |
| Q-20 | | | |

---

## Part C — Explain and choose (Hard)

### C1 — Does the tool description matter?

| Question | Calls (your description) | Calls (vague) | Answer (yours) | Answer (vague) |
|---|---:|---:|---|---|
| | | | | |

### C2 — Three mistakes explained

### C3 — Which strategy I would use, and what would change it

### C4 — How sure I can be

### Final questions

1.
2.
3.
4.
5.
6.
7.
8.
