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

    @staticmethod
    def requirement(name="Python", evidence="Python 개발 경험"):
        return {
            "name": name,
            "normalized_name": name,
            "category": "technical_skill",
            "importance": "required",
            "evidence": evidence,
        }

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

    def test_deduplicates_same_job_posting(self):
        first = self.registry.save_job_posting(
            " ABC ", "AI Engineer", "자격요건:\nPython 개발 경험", "2026-09-20"
        )
        second = self.registry.save_job_posting(
            "abc", " AI  Engineer ", "자격요건: Python 개발 경험", "2026-09-20"
        )

        self.assertTrue(first["ok"] and second["ok"])
        self.assertFalse(first["deduplicated"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(first["job_id"], second["job_id"])
        self.assertEqual(len(self.registry.db.fetch_all("SELECT id FROM job_postings")), 1)

    def test_rejects_different_content_for_same_job_identity(self):
        first = self.registry.save_job_posting("ABC", "개발자", "Python 개발 경험", None)
        second = self.registry.save_job_posting("abc", "개발자", "Python과 AWS 경험", None)

        self.assertFalse(second["ok"])
        self.assertEqual(second["existing_job_id"], first["job_id"])
        self.assertIn("update_job_posting", second["error"])
        self.assertEqual(len(self.registry.db.fetch_all("SELECT id FROM job_postings")), 1)

    def test_saves_posting_and_analysis_with_one_tool(self):
        requirements = [self.requirement()]
        first = self.registry.execute("save_job_posting_analysis", {
            "company": "ABC",
            "position": "AI Engineer",
            "posting_text": "자격요건: Python 개발 경험",
            "deadline": "2026-09-20",
            "requirements": requirements,
        })
        second = self.registry.execute("save_job_posting_analysis", {
            "company": "abc",
            "position": "AI Engineer",
            "posting_text": "자격요건: Python 개발 경험",
            "deadline": "2026-09-20",
            "requirements": requirements,
        })

        self.assertTrue(first["ok"] and second["ok"])
        self.assertEqual(first["requirements_saved"], 1)
        self.assertTrue(second["deduplicated"])
        self.assertEqual(second["requirements_deduplicated"], 1)
        self.assertEqual(len(self.registry.get_job_requirements(first["job_id"])["requirements"]), 1)

    def test_updates_posting_and_invalidates_derived_results(self):
        old_text = "자격요건: Python 개발 경험"
        job = self.registry.save_job_posting_analysis(
            "ABC", "개발자", old_text, "2026-09-20", [self.requirement()]
        )
        candidate = self.registry.save_candidate_profile("홍길동", "Python 경험")
        self.registry.save_match_result(job["job_id"], candidate["candidate_id"], [{
            "requirement": "Python",
            "status": "matched",
            "job_evidence": "Python 개발 경험",
            "resume_evidence": "Python 경험",
            "explanation": "경험이 있음",
        }])
        self.registry.create_application_tasks(job["job_id"], [{
            "title": "이력서 보완",
            "due_date": "2026-09-10",
            "priority": "high",
            "reason": "테스트",
        }])
        new_text = "자격요건: Python 개발 경험. 우대사항: AWS 운영 경험"
        result = self.registry.update_job_posting(
            job["job_id"], "ABC", "수정된 개발자", new_text, "2026-09-22", [
                self.requirement(),
                {
                    "name": "AWS",
                    "normalized_name": "AWS",
                    "category": "tool_platform",
                    "importance": "preferred",
                    "evidence": "AWS 운영 경험",
                },
            ],
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["requirements_saved"], 2)
        self.assertEqual(result["match_results_deleted"], 1)
        self.assertEqual(result["tasks_require_review"], 1)
        self.assertEqual(
            self.registry.get_job_posting(job["job_id"])["job_posting"]["position"],
            "수정된 개발자",
        )
        self.assertEqual(len(self.registry.get_job_requirements(job["job_id"])["requirements"]), 2)
        self.assertEqual(len(self.registry.db.fetch_all("SELECT id FROM match_results")), 0)
        self.assertEqual(len(self.registry.get_application_tasks(job["job_id"])["tasks"]), 1)

    def test_update_rejects_requirement_without_source_evidence(self):
        job = self.registry.save_job_posting("ABC", "개발자", "Python 개발 경험", None)
        result = self.registry.execute("update_job_posting", {
            "job_id": job["job_id"],
            "company": "ABC",
            "position": "개발자",
            "posting_text": "Python 개발 경험",
            "deadline": None,
            "requirements": [self.requirement("AWS", "AWS 운영 경험")],
        })

        self.assertFalse(result["ok"])
        self.assertEqual(self.registry.get_job_posting(job["job_id"])["job_posting"]["posting_text"], "Python 개발 경험")

    def test_reports_duplicate_requirement_count_correctly(self):
        job = self.registry.save_job_posting("ABC", "개발자", "Python 개발 경험", None)
        first = self.registry.save_job_requirements(job["job_id"], [self.requirement()])
        second = self.registry.save_job_requirements(job["job_id"], [self.requirement()])

        self.assertEqual(first["saved_count"], 1)
        self.assertEqual(second["saved_count"], 0)
        self.assertEqual(second["deduplicated_count"], 1)


if __name__ == "__main__":
    unittest.main()
