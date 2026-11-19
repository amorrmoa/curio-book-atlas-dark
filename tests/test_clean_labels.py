"""Regression checks for user-facing catalog chrome; no network required."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / 'docs' / 'index.html').read_text(encoding='utf-8')


class SimpleLabelsTests(unittest.TestCase):
    def test_no_fake_book_cover_letters_or_bibliography_labels(self):
        self.assertNotIn('BIBLIOGRAPHY', HTML)
        self.assertNotIn('ABCDEFGHIJKLMNOPQRSTUVWXYZ', HTML)
        self.assertNotIn('cover-mark', HTML)
        self.assertNotIn('CURIO / ${esc(', HTML)
        self.assertIn('aria-hidden="true"', HTML)

    def test_monthly_browsing_and_themes_retained(self):
        self.assertIn('id="month-nav"', HTML)
        self.assertIn('id="theme-grid"', HTML)
        self.assertIn('id="search"', HTML)
        data = json.loads((ROOT / 'docs' / 'data' / 'books.json').read_text(encoding='utf-8'))
        self.assertEqual(data['meta']['count'], len(data['books']))
        self.assertGreaterEqual(len(data['books']),181)
        self.assertGreaterEqual(sum(bool(b.get('isbn')) for b in data['books']),121)
        themes = json.loads((ROOT / 'docs' / 'data' / 'themes.json').read_text(encoding='utf-8'))
        self.assertEqual(14, len(themes['themes']))

if __name__ == '__main__':
    unittest.main()
