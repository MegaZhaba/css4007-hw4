"""The three strategies (S1 direct, S2 think-and-vote, S3 tools) and the model client.

Every strategy returns a dict with the same keys, so run.py can score and log
them the same way:
    {"answer_text", "parsed", "unanswered", "usage", "seconds", "calls", ...}
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter

from tools import load_corpus, run_tool, tool_definitions

MODEL = os.getenv("MODEL", "gpt-5.6-luna")
TEMPERATURE = 1.0          # same for every strategy; S2 needs it > 0 so samples vary
K_SAMPLES = 5              # S2
MAX_ROUNDS = 10            # S3: model calls per question before we give up
MAX_COMPLETION_TOKENS = 4000
# gpt-5.6-luna refuses function tools in Chat Completions unless reasoning_effort="none",
# so S3 needs "none"; S1 and S2 use the same value to keep the comparison fair.
REASONING_EFFORT = os.getenv("REASONING_EFFORT") or "none"

ANSWER_FORMAT = (
    "End your reply with exactly one final line in this format:\n"
    "ANSWER: <district name, or yes/no> | <number>\n"
    "The number is the quantity the question asks for, without units or thousands "
    "separators. Do not round it to fewer than 3 decimal places unless it is a whole "
    "number (e.g. 'ANSWER: Ossbridge | 4.613' or 'ANSWER: yes | 14069')."
)

BASE_RULES = (
    "You answer questions about the Nine Rivers Region, a fictional region. Its facts "
    "are only in the region's documents, so never use outside knowledge and never "
    "guess a number."
)

DIRECT_INSTRUCTION = "Answer directly. Do not show your working."
COT_INSTRUCTION = (
    "Think step by step: first write down each fact you need and the document it comes "
    "from, then do the arithmetic one step at a time, then compare."
)
TOOLS_INSTRUCTION = (
    "You do not have the documents. You have two tools: use `lookup` for every fact you "
    "need and `calculate` for every arithmetic step. Do not do arithmetic in your head."
)


def corpus_block() -> str:
    lines = [f"[{d['id']}] {d['title']}\n{d['text']}" for d in load_corpus()]
    return "DOCUMENTS:\n\n" + "\n\n".join(lines)


def system_prompt(with_documents: bool) -> str:
    parts = [BASE_RULES]
    if with_documents:
        parts.append(corpus_block())
    else:
        parts.append(TOOLS_INSTRUCTION)
    parts.append(ANSWER_FORMAT)
    return "\n\n".join(parts)


# ----------------------------------------------------------------------------
# Answer parsing
# ----------------------------------------------------------------------------

ANSWER_RE = re.compile(
    r"ANSWER:\s*\**\s*(?P<name>[^|\n]+?)\s*\|\s*(?P<num>[-+]?[\d,]*\.?\d+(?:[eE][-+]?\d+)?)"
)


def parse_answer(text: str | None):
    """(name, number) from the last ANSWER line, or None."""
    if not text:
        return None
    matches = list(ANSWER_RE.finditer(text))
    if not matches:
        return None
    m = matches[-1]
    name = m.group("name").strip().strip("*`'\" ").rstrip(".")
    try:
        number = float(m.group("num").replace(",", ""))
    except ValueError:
        return None
    return name, number


# ----------------------------------------------------------------------------
# Model client
# ----------------------------------------------------------------------------

class Client:
    """Thin wrapper around Chat Completions: retries, usage accounting, and
    dropping parameters the model refuses (recorded in `self.dropped`)."""

    def __init__(self, model: str = MODEL):
        from dotenv import load_dotenv
        from openai import OpenAI

        load_dotenv()
        self.client = OpenAI()
        self.model = model
        self.dropped: set[str] = set()

    def settings(self) -> dict:
        return {
            "model": self.model,
            "temperature": None if "temperature" in self.dropped else TEMPERATURE,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "reasoning_effort": REASONING_EFFORT,
            "k": K_SAMPLES,
            "max_rounds": MAX_ROUNDS,
            "dropped_parameters": sorted(self.dropped),
        }

    def chat(self, messages: list[dict], tools: list[dict] | None = None):
        """One API call -> (assistant message, usage dict, seconds)."""
        import openai

        params = {"model": self.model, "messages": messages,
                  "max_completion_tokens": MAX_COMPLETION_TOKENS}
        if "temperature" not in self.dropped:
            params["temperature"] = TEMPERATURE
        if REASONING_EFFORT and "reasoning_effort" not in self.dropped:
            params["reasoning_effort"] = REASONING_EFFORT
        if tools:
            params["tools"] = tools

        for attempt in range(6):
            start = time.perf_counter()
            try:
                resp = self.client.chat.completions.create(**params)
            except openai.BadRequestError as exc:
                msg = str(exc).lower()
                dropped = False
                for p in ("temperature", "reasoning_effort"):
                    if p in params and p in msg:
                        params.pop(p)
                        self.dropped.add(p)
                        dropped = True
                if dropped:
                    continue
                raise
            except (openai.RateLimitError, openai.APIConnectionError,
                    openai.APITimeoutError, openai.InternalServerError):
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
                continue
            seconds = time.perf_counter() - start
            u = resp.usage
            usage = {
                "input_tokens": u.prompt_tokens,
                "output_tokens": u.completion_tokens,
                "cached_tokens": getattr(getattr(u, "prompt_tokens_details", None),
                                         "cached_tokens", 0) or 0,
                "reasoning_tokens": getattr(getattr(u, "completion_tokens_details", None),
                                            "reasoning_tokens", 0) or 0,
            }
            return resp.choices[0].message, usage, seconds
        raise RuntimeError("API call failed after retries")


def add_usage(total: dict, usage: dict) -> None:
    for k, v in usage.items():
        total[k] = total.get(k, 0) + v


# ----------------------------------------------------------------------------
# S1 — direct
# ----------------------------------------------------------------------------

def s1_direct(client: Client, question: str, **_) -> dict:
    messages = [
        {"role": "system", "content": system_prompt(with_documents=True)},
        {"role": "user", "content": f"{question}\n\n{DIRECT_INSTRUCTION}"},
    ]
    start = time.perf_counter()
    msg, usage, _sec = client.chat(messages)
    parsed = parse_answer(msg.content)
    return {
        "answer_text": msg.content,
        "parsed": parsed,
        "unanswered": parsed is None,
        "usage": usage,
        "seconds": time.perf_counter() - start,
        "calls": 1,
        "messages": messages + [{"role": "assistant", "content": msg.content}],
    }


# ----------------------------------------------------------------------------
# S2 — chain of thought + self-consistency (k samples, majority vote)
# ----------------------------------------------------------------------------

def vote(parsed_samples: list, decimals: int):
    """Most common (name, number rounded to the answer precision); ties -> earliest."""
    keys = [(p[0].lower(), round(p[1], decimals)) for p in parsed_samples if p]
    if not keys:
        return None, {}
    counts = Counter(keys)
    best = max(counts.values())
    winner = next(k for k in keys if counts[k] == best)
    name = next(p[0] for p in parsed_samples if p and p[0].lower() == winner[0])
    return (name, winner[1]), {f"{k[0]} | {k[1]}": v for k, v in counts.items()}


def s2_vote(client: Client, question: str, decimals: int = 2, **_) -> dict:
    messages = [
        {"role": "system", "content": system_prompt(with_documents=True)},
        {"role": "user", "content": f"{question}\n\n{COT_INSTRUCTION}"},
    ]
    start = time.perf_counter()
    total: dict = {}
    samples = []
    for i in range(K_SAMPLES):
        msg, usage, sec = client.chat(messages)
        add_usage(total, usage)
        samples.append({"sample": i + 1, "text": msg.content,
                        "parsed": parse_answer(msg.content), "usage": usage,
                        "seconds": round(sec, 3)})
    parsed, counts = vote([s["parsed"] for s in samples], decimals)
    return {
        "answer_text": f"majority vote over {K_SAMPLES} samples: {counts}",
        "parsed": parsed,
        "unanswered": parsed is None,
        "usage": total,
        "seconds": time.perf_counter() - start,
        "calls": K_SAMPLES,
        "vote_counts": counts,
        "samples": samples,
        "messages": messages,
    }


# ----------------------------------------------------------------------------
# S3 — tool-calling loop
# ----------------------------------------------------------------------------

def _assistant_dict(msg) -> dict:
    """The assistant message exactly as the model sent it (content + tool_calls)."""
    d = {"role": "assistant", "content": msg.content}
    if msg.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return d


def s3_tools(client: Client, question: str, vague: bool = False, **_) -> dict:
    tools = tool_definitions(vague=vague)
    messages = [
        {"role": "system", "content": system_prompt(with_documents=False)},
        {"role": "user", "content": question},
    ]
    start = time.perf_counter()
    total: dict = {}
    rounds = []
    tool_log = []
    final_text = None

    for round_no in range(1, MAX_ROUNDS + 1):
        msg, usage, sec = client.chat(messages, tools=tools)
        add_usage(total, usage)
        rounds.append({"round": round_no, "usage": usage, "seconds": round(sec, 3),
                       "tool_calls": len(msg.tool_calls or [])})
        messages.append(_assistant_dict(msg))

        if not msg.tool_calls:
            final_text = msg.content
            break

        # Answer EVERY tool_call_id, in order, even when the call is invalid.
        for tc in msg.tool_calls:
            t0 = time.perf_counter()
            result = run_tool(tc.function.name, tc.function.arguments)
            ms = (time.perf_counter() - t0) * 1000
            tool_log.append({"round": round_no, "id": tc.id, "tool": tc.function.name,
                             "arguments": tc.function.arguments, "result": result,
                             "ms": round(ms, 3)})
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(result, ensure_ascii=False)})

    parsed = parse_answer(final_text)
    return {
        "answer_text": final_text,
        "parsed": parsed,
        "unanswered": parsed is None,
        "hit_round_limit": final_text is None,
        "usage": total,
        "seconds": time.perf_counter() - start,
        "calls": len(rounds),
        "rounds": rounds,
        "tool_calls": tool_log,
        "messages": messages,
    }


STRATEGIES = {"s1": s1_direct, "s2": s2_vote, "s3": s3_tools}
