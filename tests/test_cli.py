import unittest

from careerflow.cli import read_multiline


class MultilineInputTest(unittest.TestCase):
    def test_collects_lines_and_preserves_blank_lines(self):
        lines = iter([
            "ABC AI Engineer",
            "",
            "자격요건: Python 개발 경험",
            "/end",
        ])

        result = read_multiline(lambda _prompt: next(lines), lambda _message: None)

        self.assertEqual(result, "ABC AI Engineer\n\n자격요건: Python 개발 경험")

    def test_can_cancel_multiline_input(self):
        lines = iter(["임시 내용", "/cancel"])

        result = read_multiline(lambda _prompt: next(lines), lambda _message: None)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
