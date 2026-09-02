from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from .prompts import SYSTEM_PROMPT
from .tools import TOOL_DEFINITIONS, ToolRegistry


SENSITIVE_TRACE_KEYS = {"name", "resume_text", "resume_evidence", "posting_text"}


def redact_trace_data(value: Any) -> Any:
    """발표·디버그 로그에 개인 데이터 원문이 노출되지 않도록 마스킹한다."""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key in SENSITIVE_TRACE_KEYS else redact_trace_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_trace_data(item) for item in value]
    return value


class CareerFlowAgent:
    def __init__(self, registry: ToolRegistry, model: str | None = None, client: Any | None = None) -> None:
        self.registry = registry
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
        self.client = client or OpenAI()
        self.history: list[Any] = []

    def run(self, user_message: str, *, trace: bool = False, max_rounds: int = 10) -> str:
        self.history.append({"role": "user", "content": user_message})

        for _ in range(max_rounds):
            response = self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=self.history,
                tools=TOOL_DEFINITIONS,
            )
            self.history.extend(response.output)
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                return response.output_text

            for call in calls:
                arguments = json.loads(call.arguments)
                if trace:
                    safe_arguments = redact_trace_data(arguments)
                    print(f"[tool] {call.name}({json.dumps(safe_arguments, ensure_ascii=False)})")
                result = self.registry.execute(call.name, arguments)
                if trace:
                    safe_result = redact_trace_data(result)
                    print(f"[result] {json.dumps(safe_result, ensure_ascii=False)}")
                self.history.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                })

        raise RuntimeError("툴 호출 횟수 제한을 초과했습니다.")
