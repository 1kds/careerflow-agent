import unittest
from unittest.mock import patch
from careerflow.web import analyze, extract_pdf, configuration, clean_web_summary
from careerflow.providers import ModelTurn, ModelToolCall


class WebTests(unittest.TestCase):
    def test_removes_closing_actions_only(self):
        text = '### 준비 작업\n검색 실험\n### 💡 다음에 할 수 있는 행동\n1. 승인해주세요.\n'
        self.assertEqual(clean_web_summary(text), '### 준비 작업\n검색 실험')
        self.assertEqual(clean_web_summary('분석 결과'), '분석 결과')
        self.assertIn('### 근거\n원문', clean_web_summary(text + '### 근거\n원문'))

    def test_demo_evidence(self):
        result = analyze({'mode': 'demo', 'resume': 'Python과 RAG 시스템을 구현한 프로젝트 경험이 있습니다.', 'posting': 'Python과 Docker를 활용하는 AI 서비스 개발자를 채용합니다.'})
        by_skill = {row['skill']: row for row in result['matches']}
        self.assertTrue(by_skill['Python']['found'])
        self.assertFalse(by_skill['Docker']['found'])
        self.assertEqual(result['mode'], 'demo')

    def test_invalid_text(self):
        with self.assertRaises(ValueError):
            analyze({'resume': '', 'posting': 'test'})

    def test_ai_requires_consent(self):
        with self.assertRaisesRegex(ValueError, '동의'):
            analyze({'resume': 'a'*40, 'posting': 'b'*40, 'mode': 'gemini'})

    def test_invalid_pdf(self):
        with self.assertRaises(ValueError):
            extract_pdf(b'not pdf')

    def test_config_never_exposes_keys(self):
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'secret-test-key'}, clear=True):
            self.assertEqual(configuration(), {'providers': {
                'gemini': {'configured': True}, 'openai': {'configured': False}}})

    def test_default_requires_consent(self):
        with self.assertRaisesRegex(ValueError, '동의'):
            analyze({'resume': 'a'*40, 'posting': 'b'*40})

    def test_missing_key_does_not_fall_back_to_keywords(self):
        with patch.dict('os.environ', {}, clear=True):
            with self.assertRaisesRegex(ValueError, '--ask-key'):
                analyze({'resume': 'a'*40, 'posting': 'b'*40, 'consent': True})

    def test_web_runs_model_and_real_tool_registry(self):
        from unittest.mock import Mock
        provider = Mock()
        provider.send_user.return_value = ModelTurn('', [ModelToolCall(
            'call-1', 'save_candidate_profile', {'name': '가상 지원자', 'resume_text': '테스트 이력서'})])
        provider.send_tool_results.return_value = ModelTurn('모델이 작성한 비교 결과', [])
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'test-only'}):
            with patch('careerflow.agent.create_provider', return_value=provider) as factory:
                result = analyze({'resume': 'a'*40, 'posting': 'b'*40, 'consent': True})
        self.assertEqual(factory.call_args.args[0], 'gemini')
        self.assertEqual(result['summary'], '모델이 작성한 비교 결과')
        self.assertEqual(result['events'], [{'tool': 'save_candidate_profile', 'ok': True}])
        provider.send_tool_results.assert_called_once()
        self.assertNotIn('matches', result)


if __name__ == '__main__':
    unittest.main()
