import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from careerflow.agent import CareerFlowAgent, redact_trace_data
from careerflow.db import Database
from careerflow.tools import ToolRegistry


class FakeResponses:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            tool_call = SimpleNamespace(
                type="function_call",
                name="save_candidate_profile",
                arguments=json.dumps({"name": "홍길동", "resume_text": "Python 프로젝트"}, ensure_ascii=False),
                call_id="call_001",
            )
            return SimpleNamespace(output=[tool_call], output_text="")
        return SimpleNamespace(
            output=[SimpleNamespace(type="message")],
            output_text="이력서를 저장했습니다. candidate_id는 1입니다.",
        )


class AgentLoopTest(unittest.TestCase):
    def test_redacts_personal_data_from_trace(self):
        data = {
            "candidate_profile": {
                "name": "홍길동",
                "resume_text": "개인 이력서",
                "resume_evidence": "개인 이력서 인용문",
            },
            "posting_text": "긴 공고 원문",
            "job_id": 1,
        }
        redacted = redact_trace_data(data)
        self.assertEqual(redacted["candidate_profile"]["name"], "[REDACTED]")
        self.assertEqual(redacted["candidate_profile"]["resume_text"], "[REDACTED]")
        self.assertEqual(redacted["candidate_profile"]["resume_evidence"], "[REDACTED]")
        self.assertEqual(redacted["posting_text"], "[REDACTED]")
        self.assertEqual(redacted["job_id"], 1)

    def test_executes_tool_and_returns_final_text(self):
        with tempfile.TemporaryDirectory() as tempdir:
            registry = ToolRegistry(Database(Path(tempdir) / "test.db"))
            client = SimpleNamespace(responses=FakeResponses())
            agent = CareerFlowAgent(registry, client=client)

            result = agent.run("홍길동의 이력서를 저장해줘: Python 프로젝트", max_rounds=1)

            self.assertIn("저장했습니다", result)
            self.assertEqual(client.responses.calls, 2)
            self.assertEqual(registry.get_candidate_profile(1)["candidate_profile"]["name"], "홍길동")


if __name__ == "__main__":
    unittest.main()
