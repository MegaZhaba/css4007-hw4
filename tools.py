"""The two tools the model can call: `lookup` and `calculate`.

Both functions never raise: on any problem they return {"error": "..."} so the
model can read what went wrong and try again.
"""
from __future__ import annotations

import ast
import difflib
import json
import math
import operator
import re
from pathlib import Path

CORPUS_PATH = Path(__file__).parent / "data" / "corpus.jsonl"

FIELDS = [
    "population_2025", "population_2020", "area_km2",
    "budget_2025_million_tenge", "water_use_2025_megalitres",
    "schools", "pupils_2025_26", "paved_road_km", "founded_year",
    "water_tariff_2025_tenge_per_m3", "water_tariff_2024_tenge_per_m3",
]
REGION = "Region"
REGION_FIELDS = {"water_tariff_2025_tenge_per_m3", "water_tariff_2024_tenge_per_m3"}
MAX_EVIDENCE = 300
MAX_NAME = 50

NUM = r"(\d[\d,]*(?:\.\d+)?)"

# For every field: (regex with one or two number groups, unit). The three profile
# templates phrase the same fact differently, so each field lists every phrasing.
PATTERNS: dict[str, list[tuple[str, str]]] = {
    "population_2025": [
        (rf"2025 census recorded {NUM} residents", "residents"),
        (rf"2025 census counted {NUM} residents", "residents"),
        (rf"Census population: {NUM} in 2020 and {NUM} in 2025", "residents#2"),
    ],
    "population_2020": [
        (rf"2020 census had recorded {NUM}", "residents"),
        (rf"up from {NUM} at the 2020 census", "residents"),
        (rf"Census population: {NUM} in 2020", "residents"),
    ],
    "area_km2": [
        (rf"{NUM} square kilometres", "km2"),
    ],
    "budget_2025_million_tenge": [
        (rf"budget for 2025 was set at {NUM} million tenge", "million tenge"),
        (rf"2025 budget was {NUM} million tenge", "million tenge"),
        (rf"2025 budget amounted to {NUM} million tenge", "million tenge"),
    ],
    "water_use_2025_megalitres": [
        (rf"(?:used|came to) {NUM} megalitres", "ML"),
        (rf"used {NUM} cubic metres", "m3"),
    ],
    "schools": [
        (rf"There are {NUM} schools", "schools"),
        (rf"runs {NUM} schools", "schools"),
        (rf"has {NUM} schools", "schools"),
    ],
    "pupils_2025_26": [
        (rf"attended by {NUM} pupils in 2025/26", "pupils"),
        (rf"schools with {NUM} pupils enrolled in the 2025/26", "pupils"),
        (rf"enrolled {NUM} pupils for the 2025/26", "pupils"),
    ],
    "paved_road_km": [
        (rf"road network is {NUM} km", "km"),
        (rf"maintains {NUM} km of paved road", "km"),
        (rf"keeps {NUM} km of paved road", "km"),
    ],
    "founded_year": [
        (r"[Ff]ounded in (\d{4})", "year"),
    ],
    "water_tariff_2025_tenge_per_m3": [
        (rf"From 1 January 2025 the regional household water tariff is {NUM} tenge per cubic metre",
         "tenge per m3"),
    ],
    "water_tariff_2024_tenge_per_m3": [
        (rf"2024 tariff was {NUM} tenge per cubic metre", "tenge per m3"),
    ],
}

# What a correction notice can override: phrase in the notice -> field.
CORRECTION_PATTERNS = {
    "area_km2": rf"correct area is {NUM} square kilometres",
}


def _num(text: str) -> float:
    value = float(text.replace(",", ""))
    return int(value) if value.is_integer() else value


def _sentence(text: str, start: int, end: int) -> str:
    """The sentence around text[start:end], cut to MAX_EVIDENCE characters."""
    dot = text.rfind(". ", 0, start)
    left = dot + 2 if dot >= 0 else 0
    right = text.find(". ", end)
    right = len(text) if right < 0 else right + 1
    return text[left:right].strip()[:MAX_EVIDENCE]


def load_corpus(path: Path = CORPUS_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class Corpus:
    def __init__(self, docs: list[dict]):
        self.docs = docs
        self.districts = self._district_names()

    def _district_names(self) -> list[str]:
        about = next(d for d in self.docs if "about these profiles" in d["title"])
        m = re.search(r"twelve districts: ([^.]+)\.", about["text"])
        return [n.strip() for n in m.group(1).split(",")]

    def profiles(self, district: str) -> tuple[list[dict], list[dict]]:
        """(current profiles, archived profiles) whose title names the district."""
        current, archived = [], []
        for d in self.docs:
            title = d["title"]
            if not title.startswith(f"{district} district profile"):
                continue
            (archived if "ARCHIVED" in title.upper() else current).append(d)
        return current, archived

    def corrections(self, district: str) -> list[dict]:
        return [d for d in self.docs
                if d["title"].lower().startswith("correction notice")
                and district.lower() in d["title"].lower()]

    def region_doc(self, field: str) -> dict | None:
        for d in self.docs:
            if "tariff" in d["title"].lower():
                return d
        return None


_CORPUS: Corpus | None = None


def get_corpus() -> Corpus:
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = Corpus(load_corpus())
    return _CORPUS


def resolve_district(name, corpus: Corpus) -> tuple[str | None, str | None]:
    """(canonical name, None) or (None, error message). Never auto-corrects."""
    if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME:
        return None, f"district must be a non-empty string of at most {MAX_NAME} characters"
    cleaned = name.strip()
    if cleaned.lower().endswith(" district"):
        cleaned = cleaned[: -len(" district")].strip()
    valid = corpus.districts + [REGION]
    for v in valid:
        if v.lower() == cleaned.lower():
            return v, None
    close = difflib.get_close_matches(cleaned.title(), valid, n=3, cutoff=0.6)
    # Names that share a prefix (Ossbridge / Ossford) are suggested together.
    prefix = cleaned[:3].lower()
    for v in valid:
        if v.lower().startswith(prefix) and v not in close and len(prefix) == 3:
            close.append(v)
    if close:
        return None, f"no district named '{name}'; did you mean {' or '.join(close)}?"
    return None, f"no district named '{name}'. Valid names: {', '.join(valid)}"


def _extract(doc: dict, field: str):
    """(value, unit, evidence) for a field in one document, or None."""
    text = doc["text"]
    for pattern, unit in PATTERNS[field]:
        m = re.search(pattern, text)
        if not m:
            continue
        group = 2 if unit.endswith("#2") else 1
        unit = unit.split("#")[0]
        try:
            value = _num(m.group(group))
        except ValueError:
            return None
        return value, unit, _sentence(text, m.start(), m.end())
    return None


def lookup(district, field) -> dict:
    """Return one current, corrected, unit-normalised fact with its source."""
    try:
        corpus = get_corpus()
        if not isinstance(field, str) or field not in FIELDS:
            return {"error": f"unknown field '{field}'. Valid fields: {', '.join(FIELDS)}"}
        canonical, err = resolve_district(district, corpus)
        if err:
            return {"error": err}

        if canonical == REGION or field in REGION_FIELDS:
            if canonical != REGION or field not in REGION_FIELDS:
                return {"error": f"field '{field}' is not available for {canonical}; "
                                 f"region-wide fields ({', '.join(sorted(REGION_FIELDS))}) "
                                 f"need district='{REGION}'"}
            doc = corpus.region_doc(field)
            found = _extract(doc, field) if doc else None
            if not found:
                return {"error": f"field '{field}' not found for {REGION}"}
            value, unit, evidence = found
            return {"district": REGION, "field": field, "value": value, "unit": unit,
                    "source": doc["id"], "evidence": evidence}

        current, archived = corpus.profiles(canonical)
        if not current:
            return {"error": f"no current (non-archived) profile for {canonical}"}
        if len(current) > 1:
            ids = ", ".join(d["id"] for d in current)
            return {"error": f"ambiguous: several current profiles for {canonical} ({ids})"}
        doc = current[0]
        found = _extract(doc, field)
        if not found:
            return {"error": f"field '{field}' is not available for {canonical} ({doc['id']})"}
        value, unit, evidence = found
        result = {"district": canonical, "field": field, "value": value, "unit": unit,
                  "source": doc["id"], "evidence": evidence}
        notes = []

        for notice in corpus.corrections(canonical):
            pattern = CORRECTION_PATTERNS.get(field)
            m = re.search(pattern, notice["text"]) if pattern else None
            if m:
                notes.append(f"correction notice {notice['id']} overrides {doc['id']} "
                             f"(which says {value})")
                result["value"] = _num(m.group(1))
                result["source"] = notice["id"]
                result["evidence"] = _sentence(notice["text"], m.start(), m.end())

        if field == "water_use_2025_megalitres" and unit != "ML":
            if unit != "m3":
                return {"error": f"unknown water unit '{unit}' for {canonical}"}
            notes.append(f"converted from {value:,} cubic metres (1 ML = 1,000 m3, NR-15)")
            result["value"] = round(result["value"] / 1000, 6)
            result["unit"] = "ML"

        if archived:
            notes.append("ignored archived profile " + ", ".join(d["id"] for d in archived))
        if notes:
            result["note"] = "; ".join(notes)
        return result
    except Exception as exc:  # the tool must never crash the loop
        return {"error": f"lookup failed: {type(exc).__name__}: {exc}"}


# ----------------------------------------------------------------------------
# calculate
# ----------------------------------------------------------------------------

MAX_EXPR = 300
MAX_EXPONENT = 100
MAX_MAGNITUDE = 1e15

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class CalcError(Exception):
    pass


def _check(value):
    if isinstance(value, complex) or not math.isfinite(value) or abs(value) > MAX_MAGNITUDE:
        raise CalcError(f"result too large (limit {MAX_MAGNITUDE:g})")
    return value


def _eval(node):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant):
        if type(node.value) in (int, float):
            return _check(node.value)
        raise CalcError(f"not allowed in expression: {type(node.value).__name__} constant")
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _check(_UNARY[type(node.op)](_eval(node.operand)))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _eval(node.left)
        right = _eval(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise CalcError("division by zero")
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_EXPONENT:
                raise CalcError(f"exponent too large (limit {MAX_EXPONENT})")
            if left == 0 and right < 0:
                raise CalcError("division by zero")
            if left < 0 and not float(right).is_integer():
                raise CalcError("fractional power of a negative number")
            # log10 estimate before computing, so 1e10**99 is refused cheaply
            if left != 0 and right * math.log10(abs(left)) > math.log10(MAX_MAGNITUDE):
                raise CalcError(f"result too large (limit {MAX_MAGNITUDE:g})")
        return _check(_BINOPS[type(node.op)](left, right))
    if isinstance(node, ast.Tuple):
        raise CalcError("not allowed in expression: Tuple (write plain numbers without "
                        "commas, e.g. 44675 not 44,675)")
    raise CalcError(f"not allowed in expression: {type(node).__name__}")


def calculate(expression) -> dict:
    """Evaluate an arithmetic expression with ast; never eval/exec."""
    if not isinstance(expression, str) or not expression.strip() or len(expression) > MAX_EXPR:
        return {"error": f"expression must be a string of 1-{MAX_EXPR} characters"}
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:
        return {"error": f"could not parse expression: {exc.msg} "
                         "(write plain numbers without commas, e.g. 44675 not 44,675)"}
    except Exception as exc:
        return {"error": f"could not parse expression: {type(exc).__name__}"}
    try:
        result = _eval(tree)
    except CalcError as exc:
        return {"error": str(exc)}
    except RecursionError:
        return {"error": "expression is nested too deeply"}
    except Exception as exc:
        return {"error": f"calculation failed: {type(exc).__name__}: {exc}"}
    return {"expression": expression.strip(), "result": result}


# ----------------------------------------------------------------------------
# Definitions sent to the model (copied from SUBMISSION.md A2)
# ----------------------------------------------------------------------------

LOOKUP_DESCRIPTION = (
    "Look up ONE official 2025 fact about a district of the Nine Rivers Region (or a "
    "region-wide fact) and get back the number, its unit and the source document id. "
    "Archived 2019 profiles are ignored and correction notices are already applied, so "
    "the value returned is the one to use. Water use is always returned in megalitres "
    "(1 ML = 1,000 cubic metres = 1,000,000 litres). Budgets are in million tenge. Call "
    "this once per fact you need; never guess a number. If the district name is not "
    "recognised you get an error with suggestions - check the spelling (Ossbridge and "
    "Ossford are two different districts)."
)
VAGUE_LOOKUP_DESCRIPTION = "Looks things up."

CALCULATE_DESCRIPTION = (
    "Evaluate ONE arithmetic expression exactly and return the unrounded result. "
    "Allowed: numbers (no thousands separators: write 44675, not 44,675), + - * / ** and "
    "parentheses. No variables, functions, units or text. Use it for every division, "
    "multiplication, percentage and difference instead of doing arithmetic in your head, "
    "e.g. '37203 / 758.6 - 44675 / 921.4'. Round only in your final answer."
)


def tool_definitions(vague: bool = False) -> list[dict]:
    lookup_params = {
        "type": "object",
        "properties": {
            "district": {
                "type": "string",
                "description": "District name, e.g. 'Brightwater'. Use 'Region' for "
                               "region-wide facts (water tariffs).",
            },
            "field": {"type": "string", "enum": FIELDS, "description": "Which fact to return."},
        },
        "required": ["district", "field"],
        "additionalProperties": False,
    }
    return [
        {"type": "function", "function": {
            "name": "lookup",
            "description": VAGUE_LOOKUP_DESCRIPTION if vague else LOOKUP_DESCRIPTION,
            "parameters": lookup_params,
        }},
        {"type": "function", "function": {
            "name": "calculate",
            "description": CALCULATE_DESCRIPTION,
            "parameters": {
                "type": "object",
                "properties": {"expression": {
                    "type": "string",
                    "description": "Arithmetic expression, at most 300 characters, "
                                   "e.g. '(52904 - 48317) / 48317 * 100'.",
                }},
                "required": ["expression"],
                "additionalProperties": False,
            },
        }},
    ]


TOOLS = {"lookup": lookup, "calculate": calculate}
REQUIRED_ARGS = {"lookup": ["district", "field"], "calculate": ["expression"]}


def run_tool(name: str, arguments: str) -> dict:
    """Validate the JSON-string arguments of a tool call, then run the tool."""
    if name not in TOOLS:
        return {"error": f"unknown tool '{name}'. Available: {', '.join(TOOLS)}"}
    try:
        args = json.loads(arguments or "{}")
    except (json.JSONDecodeError, TypeError) as exc:
        return {"error": f"arguments are not valid JSON: {exc}"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object"}
    missing = [k for k in REQUIRED_ARGS[name] if k not in args]
    if missing:
        return {"error": f"missing required argument(s): {', '.join(missing)}"}
    extra = [k for k in args if k not in REQUIRED_ARGS[name]]
    if extra:
        return {"error": f"unexpected argument(s): {', '.join(extra)}"}
    return TOOLS[name](**args)
