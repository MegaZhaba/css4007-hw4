"""Final question 3: how many tokens do the two tool definitions add to every S3 request?

1. Offline estimate: tiktoken (o200k_base) on the JSON of the definitions.
2. Measured: the same tiny request sent with and without tools=[...]; the
   difference in usage.prompt_tokens is what the API actually charges.

    python measure_tools.py            # both (needs OPENAI_API_KEY)
    python measure_tools.py --offline  # estimate only
"""
from __future__ import annotations

import json
import sys

import tiktoken

from tools import tool_definitions


def offline() -> dict:
    enc = tiktoken.get_encoding("o200k_base")
    out = {}
    for vague in (False, True):
        text = json.dumps(tool_definitions(vague=vague))
        out["vague" if vague else "normal"] = len(enc.encode(text))
    return out


def measured() -> dict:
    from strategies import Client

    client = Client()
    messages = [{"role": "user", "content": "Say OK."}]
    _, without, _ = client.chat(messages)
    out = {"without_tools": without["input_tokens"]}
    for vague in (False, True):
        _, with_tools, _ = client.chat(messages, tools=tool_definitions(vague=vague))
        key = "vague" if vague else "normal"
        out[f"with_tools_{key}"] = with_tools["input_tokens"]
        out[f"added_{key}"] = with_tools["input_tokens"] - without["input_tokens"]
    return out


if __name__ == "__main__":
    result = {"tiktoken_estimate_of_json": offline()}
    if "--offline" not in sys.argv:
        result["measured_prompt_tokens"] = measured()
    print(json.dumps(result, indent=2))
