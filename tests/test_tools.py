import tempfile
import unittest
from pathlib import Path

from careerflow.db import Database
from careerflow.tools import ToolRegistry


class ToolRegistryTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.registry = ToolRegistry(Database(Path(self.tempdir.name) / "test.db"))

    def tearDown(self):
        self.tempdir.cleanup()

    def test_complete_storage_flow(self):
        posting_text = "자격요건: Python 개발 경험. 우대사항: AWS 운영 경험."
        job = self.registry.save_job_posting("ABC", "AI Engineer", posting_text, "2026-09-20")
        candidate = self.registry.save_candidate_profile("홍길동", "Python과 FastAPI 프로젝트 경험")
        requirements = self.registry.save_job_requirements(job["job_id"], [{
            "name": "Python", "normalized_name": "Python", "category": "technical_skill",
            "importance": "required", "evidence": "Python 개발 경험",
        }])
        match = self.registry.save_match_result(job["job_id"], candidate["candidate_id"], [{
            "requirement": "Python", "status": "matched", "job_evidence": "Python 개발 경험",
            "resume_evidence": "Python과 FastAPI 프로젝트 경험", "explanation": "명시적인 경험이 있음",
        }])
        tasks = self.registry.create_application_tasks(job["job_id"], [{
            "title": "이력서 보완", "due_date": "2026-09-10", "priority": "high", "reason": "경험을 구체화",
        }])
        self.assertTrue(job["ok"] and candidate["ok"] and requirements["ok"] and match["ok"] and tasks["ok"])

    def test_rejects_evidence_not_in_posting(self):
        job = self.registry.save_job_posting("ABC", "개발자", "Python 경험", None)
        result = self.registry.save_job_requirements(job["job_id"], [{
            "name": "AWS", "normalized_name": "AWS", "category": "tool_platform",
            "importance": "preferred", "evidence": "AWS 운영 경험",
        }])
        self.assertFalse(result["ok"])
        self.assertEqual(result["saved_count"], 0)

    def test_rejects_task_after_deadline(self):
        job = self.registry.save_job_posting("ABC", "개발자", "Python 경험", "2026-09-20")
        result = self.registry.execute("create_application_tasks", {"job_id": job["job_id"], "tasks": [{
            "title": "늦은 작업", "due_date": "2026-09-21", "priority": "high", "reason": "테스트",
        }]})
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
