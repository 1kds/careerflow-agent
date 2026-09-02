from __future__ import annotations

from datetime import date
from typing import Any, Callable

from .db import Database


READ_TOOLS = {
    "get_job_posting",
    "get_candidate_profile",
    "get_job_requirements",
    "get_application_tasks",
}


def _function(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "strict": True,
    }


TOOL_DEFINITIONS = [
    _function("save_job_posting", "채용공고 원문과 메타데이터를 저장한다.", {
        "company": {"type": "string"}, "position": {"type": "string"},
        "posting_text": {"type": "string"},
        "deadline": {"type": ["string", "null"], "description": "YYYY-MM-DD 또는 null"},
    }, ["company", "position", "posting_text", "deadline"]),
    _function("get_job_posting", "저장된 채용공고를 조회한다.", {
        "job_id": {"type": "integer"},
    }, ["job_id"]),
    _function("save_candidate_profile", "사용자 이름과 이력서 원문을 저장한다.", {
        "name": {"type": "string"}, "resume_text": {"type": "string"},
    }, ["name", "resume_text"]),
    _function("get_candidate_profile", "저장된 이력서를 조회한다.", {
        "candidate_id": {"type": "integer"},
    }, ["candidate_id"]),
    _function("save_job_requirements", "모델이 공고에서 추출한 역량과 원문 근거를 저장한다.", {
        "job_id": {"type": "integer"},
        "requirements": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "normalized_name": {"type": "string"},
            "category": {"type": "string", "enum": ["technical_skill", "tool_platform", "job_experience", "domain_knowledge", "soft_skill", "qualification", "language"]},
            "importance": {"type": "string", "enum": ["required", "preferred", "responsibility", "unknown"]},
            "evidence": {"type": "string"},
        }, "required": ["name", "normalized_name", "category", "importance", "evidence"], "additionalProperties": False}},
    }, ["job_id", "requirements"]),
    _function("get_job_requirements", "공고에서 추출해 저장한 요구 역량을 조회한다.", {
        "job_id": {"type": "integer"},
    }, ["job_id"]),
    _function("save_match_result", "모델이 이력서와 공고를 비교한 근거 기반 결과를 저장한다.", {
        "job_id": {"type": "integer"}, "candidate_id": {"type": "integer"},
        "matches": {"type": "array", "items": {"type": "object", "properties": {
            "requirement": {"type": "string"},
            "status": {"type": "string", "enum": ["matched", "partial", "not_found", "needs_clarification"]},
            "job_evidence": {"type": "string"}, "resume_evidence": {"type": ["string", "null"]},
            "explanation": {"type": "string"},
        }, "required": ["requirement", "status", "job_evidence", "resume_evidence", "explanation"], "additionalProperties": False}},
    }, ["job_id", "candidate_id", "matches"]),
    _function("create_application_tasks", "사용자가 승인한 지원 준비 작업들을 등록한다.", {
        "job_id": {"type": "integer"},
        "tasks": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "due_date": {"type": "string", "description": "YYYY-MM-DD"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]}, "reason": {"type": "string"},
        }, "required": ["title", "due_date", "priority", "reason"], "additionalProperties": False}},
    }, ["job_id", "tasks"]),
    _function("get_application_tasks", "공고에 등록된 지원 준비 작업을 조회한다.", {
        "job_id": {"type": "integer"},
    }, ["job_id"]),
]


class ToolRegistry:
    def __init__(self, database: Database) -> None:
        self.db = database
        self.handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "save_job_posting": self.save_job_posting,
            "get_job_posting": self.get_job_posting,
            "save_candidate_profile": self.save_candidate_profile,
            "get_candidate_profile": self.get_candidate_profile,
            "save_job_requirements": self.save_job_requirements,
            "get_job_requirements": self.get_job_requirements,
            "save_match_result": self.save_match_result,
            "create_application_tasks": self.create_application_tasks,
            "get_application_tasks": self.get_application_tasks,
        }

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in self.handlers:
            return {"ok": False, "error": f"Unknown tool: {name}"}
        try:
            return self.handlers[name](**arguments)
        except (ValueError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    def save_job_posting(self, company: str, position: str, posting_text: str, deadline: str | None) -> dict[str, Any]:
        if deadline:
            date.fromisoformat(deadline)
        job_id = self.db.execute(
            "INSERT INTO job_postings(company, position, posting_text, deadline) VALUES (?, ?, ?, ?)",
            (company.strip(), position.strip(), posting_text.strip(), deadline),
        )
        return {"ok": True, "job_id": job_id}

    def get_job_posting(self, job_id: int) -> dict[str, Any]:
        item = self.db.fetch_one("SELECT * FROM job_postings WHERE id = ?", (job_id,))
        return {"ok": item is not None, "job_posting": item}

    def save_candidate_profile(self, name: str, resume_text: str) -> dict[str, Any]:
        candidate_id = self.db.execute(
            "INSERT INTO candidate_profiles(name, resume_text) VALUES (?, ?)", (name.strip(), resume_text.strip())
        )
        return {"ok": True, "candidate_id": candidate_id}

    def get_candidate_profile(self, candidate_id: int) -> dict[str, Any]:
        item = self.db.fetch_one("SELECT * FROM candidate_profiles WHERE id = ?", (candidate_id,))
        return {"ok": item is not None, "candidate_profile": item}

    def save_job_requirements(self, job_id: int, requirements: list[dict[str, Any]]) -> dict[str, Any]:
        posting = self.get_job_posting(job_id)["job_posting"]
        if not posting:
            raise ValueError("존재하지 않는 채용공고입니다.")
        saved, rejected = 0, []
        for item in requirements:
            if item["evidence"] not in posting["posting_text"]:
                rejected.append({"name": item["name"], "reason": "원문에서 evidence를 찾을 수 없음"})
                continue
            try:
                self.db.execute(
                    "INSERT OR IGNORE INTO job_requirements(job_id,name,normalized_name,category,importance,evidence) VALUES(?,?,?,?,?,?)",
                    (job_id, item["name"], item["normalized_name"], item["category"], item["importance"], item["evidence"]),
                )
                saved += 1
            except Exception as exc:
                rejected.append({"name": item["name"], "reason": str(exc)})
        return {"ok": not rejected, "saved_count": saved, "rejected": rejected}

    def get_job_requirements(self, job_id: int) -> dict[str, Any]:
        items = self.db.fetch_all("SELECT * FROM job_requirements WHERE job_id = ? ORDER BY id", (job_id,))
        return {"ok": True, "requirements": items}

    def save_match_result(self, job_id: int, candidate_id: int, matches: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.get_job_posting(job_id)["job_posting"]:
            raise ValueError("존재하지 않는 채용공고입니다.")
        if not self.get_candidate_profile(candidate_id)["candidate_profile"]:
            raise ValueError("존재하지 않는 이력서입니다.")
        for item in matches:
            self.db.execute(
                "INSERT INTO match_results(job_id,candidate_id,requirement,status,job_evidence,resume_evidence,explanation) VALUES(?,?,?,?,?,?,?)",
                (job_id, candidate_id, item["requirement"], item["status"], item["job_evidence"], item["resume_evidence"], item["explanation"]),
            )
        return {"ok": True, "saved_count": len(matches)}

    def create_application_tasks(self, job_id: int, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        posting = self.get_job_posting(job_id)["job_posting"]
        if not posting:
            raise ValueError("존재하지 않는 채용공고입니다.")
        deadline = date.fromisoformat(posting["deadline"]) if posting["deadline"] else None
        task_ids = []
        for task in tasks:
            due_date = date.fromisoformat(task["due_date"])
            if deadline and due_date > deadline:
                raise ValueError(f"'{task['title']}'의 일정이 지원 마감일보다 늦습니다.")
            task_ids.append(self.db.execute(
                "INSERT INTO application_tasks(job_id,title,due_date,priority,reason) VALUES(?,?,?,?,?)",
                (job_id, task["title"], task["due_date"], task["priority"], task["reason"]),
            ))
        return {"ok": True, "task_ids": task_ids}

    def get_application_tasks(self, job_id: int) -> dict[str, Any]:
        items = self.db.fetch_all("SELECT * FROM application_tasks WHERE job_id = ? ORDER BY due_date, id", (job_id,))
        return {"ok": True, "tasks": items}
