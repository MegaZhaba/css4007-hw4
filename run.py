"""Run strategies on the questions, score them and save everything in outputs/.

Examples
    python run.py --strategy s3 --questions Q-09            # one question, try it out
    python run.py --strategy s1 s2 s3 --run 1               # full run 1
    python run.py --strategy s3 --run c1-vague --vague --questions Q-03 Q-08 Q-09 Q-13 Q-17
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from strategies import STRATEGIES, Client

load_dotenv()

ROOT = Path(__file__).parent
QUESTIONS = json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))
OUT = ROOT / "outputs"

# USD per 1M tokens. Set them in .env (see README of the model's pricing page).
PRICE_INPUT = float(os.getenv("PRICE_INPUT_PER_1M", "0") or 0)
PRICE_OUTPUT = float(os.getenv("PRICE_OUTPUT_PER_1M", "0") or 0)
# Cached input tokens are billed at a lower rate; default = full input price.
PRICE_CACHED = float(os.getenv("PRICE_CACHED_INPUT_PER_1M", "") or PRICE_INPUT)


def is_correct(parsed, q: dict) -> bool:
    """Scoring rule (fixed before the first full run):
    - the name must equal `answer`, ignoring case and surrounding spaces/punctuation;
    - the number, rounded to `decimals`, must be within one unit of the last digit
      of `value` (|round(x, d) - value| <= 10**-d)."""
    if not parsed:
        return False
    name, number = parsed
    if name.strip().lower() != q["answer"].strip().lower():
        return False
    d = q["decimals"]
    return abs(round(number, d) - q["value"]) <= 10 ** -d + 1e-9


def cost(usage: dict) -> float:
    cached = usage.get("cached_tokens", 0)
    return ((usage.get("input_tokens", 0) - cached) * PRICE_INPUT
            + cached * PRICE_CACHED
            + usage.get("output_tokens", 0) * PRICE_OUTPUT) / 1_000_000


def run_one(client: Client, strategy: str, q: dict, vague: bool) -> dict:
    fn = STRATEGIES[strategy]
    try:
        result = fn(client, q["question"], decimals=q["decimals"], vague=vague)
        error = None
    except Exception as exc:  # an API failure marks the question unanswered
        result = {"answer_text": None, "parsed": None, "unanswered": True,
                  "usage": {}, "seconds": 0.0, "calls": 0}
        error = f"{type(exc).__name__}: {exc}"
    result["error"] = error
    result["id"] = q["id"]
    result["question"] = q["question"]
    result["expected"] = {"answer": q["answer"], "value": q["value"],
                          "decimals": q["decimals"]}
    result["correct"] = is_correct(result["parsed"], q)
    result["cost_usd"] = cost(result["usage"])
    return result


def summarise(results: list[dict]) -> dict:
    secs = [r["seconds"] for r in results]
    usage = {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0}
    for r in results:
        for k in usage:
            usage[k] += r["usage"].get(k, 0)
    return {
        "questions": len(results),
        "correct": sum(r["correct"] for r in results),
        "unanswered": sum(r["unanswered"] for r in results),
        "input_tokens": usage["input_tokens"],
        "output_tokens": usage["output_tokens"],
        "cached_tokens": usage["cached_tokens"],
        "median_seconds": round(statistics.median(secs), 2) if secs else 0,
        "total_seconds": round(sum(secs), 2),
        "cost_usd": round(cost(usage), 4),
        "per_question": {r["id"]: r["correct"] for r in results},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", nargs="+", default=["s1", "s2", "s3"],
                    choices=list(STRATEGIES))
    ap.add_argument("--run", default="test", help="name of the output folder, e.g. 1, 2")
    ap.add_argument("--questions", nargs="*", help="question ids (default: all 20)")
    ap.add_argument("--vague", action="store_true", help="C1: vague lookup description")
    args = ap.parse_args()

    questions = [q for q in QUESTIONS if not args.questions or q["id"] in args.questions]
    client = Client()
    run_dir = OUT / f"run{args.run}" if str(args.run).isdigit() else OUT / str(args.run)

    for strategy in args.strategy:
        sdir = run_dir / strategy
        sdir.mkdir(parents=True, exist_ok=True)
        results = []
        for q in questions:
            r = run_one(client, strategy, q, args.vague)
            results.append(r)
            (sdir / f"{q['id']}.json").write_text(
                json.dumps(r, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            mark = "OK " if r["correct"] else ("-- " if r["unanswered"] else "XX ")
            print(f"[{strategy}] {q['id']} {mark} got={r['parsed']} "
                  f"want=({q['answer']}, {q['value']}) calls={r['calls']} "
                  f"in={r['usage'].get('input_tokens', 0)} "
                  f"out={r['usage'].get('output_tokens', 0)} {r['seconds']:.1f}s"
                  + (f" ERROR {r['error']}" if r["error"] else ""), flush=True)
        summary = summarise(results)
        summary.update({
            "strategy": strategy, "run": args.run, "vague": args.vague,
            "settings": client.settings(),
            "price_per_1m": {"input": PRICE_INPUT, "cached_input": PRICE_CACHED,
                             "output": PRICE_OUTPUT},
            "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
        (sdir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"== {strategy}: {summary['correct']}/{summary['questions']} correct, "
              f"{summary['unanswered']} unanswered, in={summary['input_tokens']} "
              f"out={summary['output_tokens']}, ${summary['cost_usd']}", flush=True)


if __name__ == "__main__":
    main()
