import tempfile
import unittest
from pathlib import Path
from careerflow.demo_jobs import demo_jobs, seed_demo_jobs
from careerflow.web_store import WebStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / 'web.db'
        self.store = WebStore(self.path)
        self.payload = {'company': '샘플', 'position': 'AI', 'posting': '공고 내용', 'deadline': '2026-12-01', 'resume': 'private resume'}
        self.id = self.store.save(self.payload, {'summary': '비교 결과', 'suggestions': []})

    def test_persists_and_updates_without_duplicates(self):
        reopened = WebStore(self.path)
        self.assertEqual(len(reopened.jobs()), 1)
        self.assertEqual(reopened.detail(self.id)['result']['summary'], '비교 결과')
        self.assertEqual(reopened.save(self.payload, {'summary': '새 결과'}), self.id)
        self.assertEqual(len(reopened.jobs()), 1)
        self.assertNotIn('private resume', self.path.read_bytes().decode(errors='ignore'))

    def test_seeds_twenty_one_offline_demo_jobs_idempotently(self):
        self.assertEqual(len(demo_jobs()), 21)
        self.assertEqual(seed_demo_jobs(self.store), 21)
        self.assertEqual(seed_demo_jobs(self.store), 21)
        for category in ('ai_data', 'software', 'product', 'design', 'marketing', 'sales', 'business'):
            jobs = self.store.catalog(category)
            self.assertEqual(len(jobs), 3)
            self.assertTrue(all(job['source'] == 'demo' for job in jobs))
            detail = self.store.catalog_detail(jobs[0]['id'])
            self.assertEqual(detail['source_url'], '')
            self.assertGreaterEqual(len(detail['description']), 30)

    def test_demo_requires_a_local_description(self):
        saved = self.store.upsert_catalog([{
            'source': 'demo', 'source_id': 'invalid-demo', 'source_name': '데모',
            'description': '짧음', 'source_url': '',
        }], 'ai_data')
        self.assertEqual(saved, 0)

    def test_tasks_approval_dedup_status_and_deadline(self):
        task = {'job_id': self.id, 'title': '검색 실험', 'due_date': '2026-11-01'}
        with self.assertRaises(ValueError):
            self.store.add_task(task)
        task['approved'] = True
        self.store.add_task(task)
        self.store.add_task(task)
        self.assertEqual(len(self.store.tasks()), 1)
        task_id = self.store.tasks()[0]['id']
        for state in ('done', 'todo'):
            self.store.set_status({'task_id': task_id, 'status': state})
            self.assertEqual(self.store.tasks()[0]['status'], state)
        with self.assertRaises(ValueError):
            self.store.add_task({**task, 'due_date': '2026-12-02'})
        self.assertEqual(len(self.store.tasks()), 1)

    def test_unknown_targets(self):
        with self.assertRaises(ValueError):
            self.store.detail(999)
        with self.assertRaises(ValueError):
            self.store.set_status({'task_id': 999, 'status': 'done'})

    def test_registration_survives_reopen_and_different_date(self):
        task = {'job_id': self.id, 'title': '검색 실험', 'due_date': '2026-11-01', 'approved': True}
        self.store.add_task(task)
        reopened = WebStore(self.path)
        result = reopened.add_task({**task, 'due_date': '2026-11-02'})
        self.assertTrue(result['already_registered'])
        self.assertEqual(result['due_date'], '2026-11-01')
        self.assertEqual(len(reopened.detail(self.id)['tasks']), 1)

    def test_bulk_delete_only_selected_and_reregister(self):
        task = {'job_id': self.id, 'title': '검색 실험', 'due_date': '2026-11-01', 'approved': True}
        first = self.store.add_task(task)['task_id']
        second = self.store.add_task({**task, 'title': '문서 정리'})['task_id']
        self.assertEqual(self.store.delete_tasks({'task_ids': [first, first]})['deleted_count'], 1)
        self.assertEqual([t['id'] for t in self.store.tasks()], [second])
        self.assertEqual(len(self.store.detail(self.id)['tasks']), 1)
        self.assertEqual(len(self.store.jobs()), 1)
        with self.assertRaises(ValueError):
            self.store.set_status({'task_id': first, 'status': 'done'})
        self.store.add_task(task)
        self.assertEqual(len(self.store.tasks()), 2)
        for ids in ([], ['1'], [True], [-1], 'all'):
            with self.assertRaises(ValueError):
                self.store.delete_tasks({'task_ids': ids})


if __name__ == '__main__':
    unittest.main()
