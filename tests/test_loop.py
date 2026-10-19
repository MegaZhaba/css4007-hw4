"""Tests for the loop, the answer parser, voting and scoring, with a fake model
(no API key, no network)."""
from types import SimpleNamespace as NS

from run import is_correct
from strategies import MAX_ROUNDS, parse_answer, s3_tools, vote


def tool_call(id_, name, args):
    return NS(id=id_, type="function", function=NS(name=name, arguments=args))


class FakeClient:
    """Plays back scripted assistant messages and records what it was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []

    def chat(self, messages, tools=None):
        self.sent.append([dict(m) for m in messages])
        msg = self.script.pop(0) if self.script else self.loop_msg()
        return msg, {"input_tokens": 100, "output_tokens": 10}, 0.01

    @staticmethod
    def loop_msg():
        return NS(content=None, tool_calls=[tool_call("x", "calculate", '{"expression": "1+1"}')])


def test_loop_answers_every_tool_call_id_and_keeps_assistant_message():
    script = [
        NS(content=None, tool_calls=[
            tool_call("c1", "lookup", '{"district": "Brightwater", "field": "area_km2"}'),
            tool_call("c2", "lookup", '{"district": "Millbrook", "field": "area_km2"}'),
            tool_call("c3", "calculate", "not json"),
        ]),
        NS(content="Millbrook is denser.\nANSWER: Millbrook | 0.556", tool_calls=None),
    ]
    client = FakeClient(script)
    r = s3_tools(client, "Q-09?")
    second_request = client.sent[1]
    assistant = second_request[2]
    assert assistant["role"] == "assistant"
    assert [tc["id"] for tc in assistant["tool_calls"]] == ["c1", "c2", "c3"]
    assert assistant["tool_calls"][2]["function"]["arguments"] == "not json"  # unchanged
    tool_msgs = [m for m in second_request if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2", "c3"]
    assert "921.4" in tool_msgs[0]["content"]
    assert "valid JSON" in tool_msgs[2]["content"]
    assert r["parsed"] == ("Millbrook", 0.556)
    assert r["usage"] == {"input_tokens": 200, "output_tokens": 20}
    assert len(r["tool_calls"]) == 3 and all("ms" in t for t in r["tool_calls"])


def test_loop_stops_at_round_limit_and_marks_unanswered():
    client = FakeClient([])
    r = s3_tools(client, "never ends")
    assert r["calls"] == MAX_ROUNDS
    assert r["unanswered"] and r["hit_round_limit"]


def test_parse_answer():
    assert parse_answer("blah\nANSWER: Ossbridge | 4.613") == ("Ossbridge", 4.613)
    assert parse_answer("**ANSWER: yes | 14,069**") == ("yes", 14069.0)
    assert parse_answer("ANSWER: a | 1\nANSWER: Redfen | 56.12") == ("Redfen", 56.12)
    assert parse_answer("no answer here") is None
    assert parse_answer(None) is None


def test_vote_majority_and_tie_break():
    samples = [("Millbrook", 0.556), ("Millbrook", 0.5557), ("Millbrook", 0.08),
               None, ("Brightwater", 0.08)]
    assert vote(samples, 1)[0] == ("Millbrook", 0.6)
    assert vote([("A", 1.0), ("B", 2.0)], 0)[0] == ("A", 1.0)
    assert vote([None, None], 1)[0] is None


def test_scoring_rule():
    q = {"answer": "Millbrook", "value": 0.6, "decimals": 1}
    assert is_correct(("Millbrook", 0.5557), q)
    assert is_correct(("millbrook", 0.7), q)        # one unit in the last digit
    assert not is_correct(("Millbrook", 0.08), q)
    assert not is_correct(("Brightwater", 0.6), q)
    assert not is_correct(None, q)
    q3 = {"answer": "Lindenmoor", "value": 0.035, "decimals": 3}
    assert is_correct(("Lindenmoor", 0.0354), q3)
    assert not is_correct(("Lindenmoor", 0.04), q3)
