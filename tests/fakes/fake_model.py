"""
Fake Model Client for testing without network/model per testing playbook.
Returns scripted ModelResults including tool calls, malformed JSON, rate-limit, slow streams.
"""
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class FakeResult:
    content: str
    tool_calls: List[Dict] = None
    usage: Dict = None

    def __post_init__(self):
        if self.tool_calls is None:
            self.tool_calls = []
        if self.usage is None:
            self.usage = {"prompt_tokens": 10, "completion_tokens": 5}

class FakeModelClient:
    def __init__(self, scenario: str = "happy"):
        self.scenario = scenario

    def complete(self, messages, tools=None, response_schema=None, effort="medium", stream=False):
        if self.scenario == "happy":
            return FakeResult(content='{"statement":{"currency":"ZAR","opening_balance":"12340.55","closing_balance":"11890.55"},"rows":[{"line_ids":["L012"],"date":"2026-10-25","description":"WOOLWORTHS","amount":"450.00","direction":"debit","balance_after":"11890.55","source_quote":"L012 | 25 Oct | WOOLWORTHS | -450.00 | 11890.55"}],"unaccounted_lines":[],"warnings":[]}')
        elif self.scenario == "malformed":
            return FakeResult(content='NOT JSON {')
        elif self.scenario == "rate_limit":
            raise Exception("RateLimit 429")
        elif self.scenario == "tool_calls":
            return FakeResult(content="", tool_calls=[{"name":"search_transactions","arguments":{"query":"Woolworths"}}])
        else:
            return FakeResult(content="unknown scenario")
