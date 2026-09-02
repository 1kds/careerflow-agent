import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from careerflow.agent import CareerFlowAgent
from careerflow.db import Database
from careerflow.providers import GeminiProvider, gemini_tool_definitions
from careerflow.tools import TOOL_DEFINITIONS, ToolRegistry


class FakeStep(SimpleNamespace):
    def model_dump(self):
        return vars(self).copy()


class FakeInteractions:
    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            step = FakeStep(
                type="function_call",
                id="gemini_call_001",
                name="save_candidate_profile",
                arguments={"name": "홍길동", "resume_text": "Python 프로젝트"},
            )
            return SimpleNamespace(id="interaction_001", steps=[step], output_text="")
        return SimpleNamespace(
            id="interaction_002",
            steps=[FakeStep(type="model_output", content=[])],
            output_text="이력서를 저장했습니다. candidate_id는 1입니다.",
        )


class GeminiProviderTest(unittest.TestCase):
    def test_converts_strict_nullable_schema_for_gemini(self):
        tools = gemini_tool_definitions()
        save_job = next(tool for tool in tools if tool["name"] == "save_job_posting")

        self.assertNotIn("strict", save_job)
        self.assertNotIn("additionalProperties", save_job["parameters"])
        self.assertEqual(save_job["parameters"]["properties"]["deadline"]["type"], "string")
        self.assertNotIn("deadline", save_job["parameters"]["required"])
        original_save_job = next(
            tool for tool in TOOL_DEFINITIONS if tool["name"] == "save_job_posting"
        )
        self.assertTrue(original_save_job["strict"])
        self.assertIn("deadline", original_save_job["parameters"]["required"])

    def test_executes_gemini_tool_call_and_continues_interaction(self):
        with tempfile.TemporaryDirectory() as tempdir:
            interactions = FakeInteractions()
            client = SimpleNamespace(interactions=interactions)
            provider = GeminiProvider(model="gemini-test", client=client)
            registry = ToolRegistry(Database(Path(tempdir) / "test.db"))
            agent = CareerFlowAgent(registry, provider=provider)

            result = agent.run("홍길동의 이력서를 저장해줘: Python 프로젝트")

            self.assertIn("저장했습니다", result)
            self.assertEqual(len(interactions.requests), 2)
            follow_up = interactions.requests[1]
            self.assertFalse(follow_up["store"])
            self.assertNotIn("previous_interaction_id", follow_up)
            self.assertEqual(follow_up["input"][0]["type"], "user_input")
            self.assertEqual(follow_up["input"][1]["type"], "function_call")
            function_result = follow_up["input"][2]
            self.assertEqual(function_result["type"], "function_result")
            self.assertEqual(function_result["call_id"], "gemini_call_001")
            self.assertEqual(function_result["name"], "save_candidate_profile")
            self.assertIn('"candidate_id": 1', function_result["result"][0]["text"])
            self.assertEqual(follow_up["tools"], provider.tools)
            self.assertTrue(follow_up["system_instruction"])
            self.assertEqual(registry.get_candidate_profile(1)["candidate_profile"]["name"], "홍길동")


if __name__ == "__main__":
    unittest.main()
