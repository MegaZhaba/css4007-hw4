"""Build the markdown tables for SUBMISSION.md from the saved outputs.

    python report.py            -> prints the tables and writes outputs/report.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "outputs"
NAMES = {"s1": "S1 direct", "s2": "S2 think and vote (k = 5)", "s3": "S3 tools"}


def load(run_dir: Path, strategy: str):
    sdir = run_dir / strategy
    if not (sdir / "summary.json").exists():
        return None, {}
    summary = json.loads((sdir / "summary.json").read_text(encoding="utf-8"))
    per_q = {}
    for f in sorted(sdir.glob("Q-*.json")):
        per_q[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return summary, per_q


def main_table() -> str:
    rows = ["| Run | Strategy | Correct /20 | Unanswered | Input tokens | Output tokens "
            "| Median seconds per question | Total seconds | Cost ($) |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for run in ("1", "2"):
        for s in ("s1", "s2", "s3"):
            summ, _ = load(OUT / f"run{run}", s)
            if not summ:
                continue
            rows.append(f"| {run} | {NAMES[s]} | {summ['correct']} | {summ['unanswered']} "
                        f"| {summ['input_tokens']:,} | {summ['output_tokens']:,} "
                        f"| {summ['median_seconds']} | {summ['total_seconds']} "
                        f"| {summ['cost_usd']:.4f} |")
    return "\n".join(rows)


def per_question_table(run: str = "1") -> str:
    data = {s: load(OUT / f"run{run}", s)[1] for s in ("s1", "s2", "s3")}
    rows = ["| Question | S1 | S2 | S3 | S3 rounds | S3 tool calls |",
            "|---|:---:|:---:|:---:|---:|---:|"]
    for i in range(1, 21):
        qid = f"Q-{i:02d}"
        cells = []
        for s in ("s1", "s2", "s3"):
            r = data[s].get(qid)
            cells.append("" if r is None else ("✓" if r["correct"] else
                                                ("✗ (unanswered)" if r["unanswered"] else "✗")))
        r3 = data["s3"].get(qid) or {}
        rows.append(f"| {qid} | {' | '.join(cells)} | {r3.get('calls', '')} "
                    f"| {len(r3.get('tool_calls', []))} |")
    return "\n".join(rows)


def wrong_answers(run: str = "1") -> str:
    lines = []
    for s in ("s1", "s2", "s3"):
        for qid, r in load(OUT / f"run{run}", s)[1].items():
            if not r["correct"]:
                lines.append(f"- run {run} {s} {qid}: got {r['parsed']} want "
                             f"({r['expected']['answer']}, {r['expected']['value']})"
                             + (f" — {r.get('vote_counts')}" if s == "s2" else ""))
    return "\n".join(lines) or "- none"


def c1_table() -> str:
    _, vague = load(OUT / "c1-vague", "s3")
    _, normal = load(OUT / "c1-normal", "s3")
    if not normal:  # same settings, normal description: reuse run 1
        _, normal = load(OUT / "run1", "s3")
    if not vague:
        return "(no C1 run yet)"
    rows = ["| Question | Calls (your description) | Calls (vague) | Answer (yours) "
            "| Answer (vague) |", "|---|---:|---:|---|---|"]
    for qid, rv in vague.items():
        rn = normal.get(qid, {})

        def fmt(r):
            if not r:
                return ""
            p = r.get("parsed")
            ans = f"{p[0]} \\| {p[1]}" if p else "unanswered"
            return ans + (" ✓" if r.get("correct") else " ✗")
        rows.append(f"| {qid} | {len(rn.get('tool_calls', []))} | "
                    f"{len(rv.get('tool_calls', []))} | {fmt(rn)} | {fmt(rv)} |")
    return "\n".join(rows)


def main() -> None:
    text = "\n\n".join([
        "## Main table\n\n" + main_table(),
        "## Per question (run 1)\n\n" + per_question_table("1"),
        "## Per question (run 2)\n\n" + per_question_table("2"),
        "## Wrong answers, run 1\n\n" + wrong_answers("1"),
        "## Wrong answers, run 2\n\n" + wrong_answers("2"),
        "## C1\n\n" + c1_table(),
    ])
    OUT.mkdir(exist_ok=True)
    (OUT / "report.md").write_text(text + "\n", encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
