"""月別トップページの構造とデータ整合性をオフラインで検証。"""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HTML=(ROOT/'docs/index.html').read_text(encoding='utf-8')
DATA=json.loads((ROOT/'docs/data/books.json').read_text(encoding='utf-8'))
THEMES=json.loads((ROOT/'docs/data/themes.json').read_text(encoding='utf-8'))['themes']

class MonthlyPageTests(unittest.TestCase):
    def test_every_book_has_month_or_undated_bucket(self):
        self.assertEqual(len(DATA['books']),181)
        for b in DATA['books']:
            self.assertIn(b['theme'],{t['id'] for t in THEMES})
            self.assertIn(b.get('year'),(2026,2027))
            self.assertTrue(b.get('month') is None or 1 <= b.get('month') <= 12)
    def test_month_controls_are_present(self):
        for marker in ['id="month-groups"','id="month-nav"','id="feature-books"','id="theme-select"','id="theme-grid"']:
            self.assertIn(marker,HTML)
    def test_topic_catalog_preserved(self):
        self.assertEqual(len(THEMES),14)
        self.assertEqual(len({t['id'] for t in THEMES}),14)

if __name__=='__main__':unittest.main()
