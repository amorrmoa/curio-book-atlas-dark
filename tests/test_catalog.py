from pathlib import Path
import importlib.util
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('builder', ROOT/'tools/build_catalog.py')
import sys
builder = importlib.util.module_from_spec(spec)
sys.modules['builder'] = builder
spec.loader.exec_module(builder)

class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.themes=json.loads((ROOT/'docs/data/themes.json').read_text(encoding='utf-8'))['themes']

    def test_all_initial_books_import(self):
        rows=builder.parse_xlsx(ROOT/'data/curio_catalog.xlsx')
        catalog=builder.build(rows,self.themes)
        self.assertEqual(len(rows), len(catalog))
        self.assertGreaterEqual(len(catalog), 181)
        self.assertTrue(all(b['title'] and b['theme'] for b in catalog))
        self.assertEqual(len(catalog),len(set(b['id'] for b in catalog)))

    def test_no_unrecognized_topics(self):
        catalog=builder.build(builder.parse_xlsx(ROOT/'data/curio_catalog.xlsx'),self.themes)
        names={t['id'] for t in self.themes}
        self.assertTrue(all(x['theme'] in names for x in catalog))
        self.assertTrue(all(set(x['related'])<=names for x in catalog))

    def test_unrecognized_theme_fails_loudly(self):
        row={'書名':'New Test','著者名':'Tester','出版社':'Press','主テーマ':'存在しない分類'}
        with self.assertRaisesRegex(ValueError,'unknown theme'):
            builder.build([row],self.themes)

    def test_isbn_registered_and_valid(self):
        rows=builder.parse_xlsx(ROOT/'data/curio_catalog.xlsx')
        catalog=builder.build(rows,self.themes)
        self.assertEqual(sum(bool(r.get('ISBN')) for r in rows),sum(bool(x['isbn']) for x in catalog))
        self.assertGreaterEqual(sum(bool(x['isbn']) for x in catalog),121)
        self.assertTrue(all('暫定' not in str(b) for b in catalog))

    def test_invalid_isbn_rejected(self):
        row={'書名':'New Test','著者名':'Tester','出版社':'Press',
             '主テーマ':self.themes[0]['name'],'ISBN':'9780000000000'}
        with self.assertRaisesRegex(ValueError,'ISBN-13'):
            builder.build([row],self.themes)

    def test_duplicate_fails_loudly(self):
        row={'書名':'A Book','著者名':'A','出版社':'P','主テーマ':self.themes[0]['name']}
        with self.assertRaisesRegex(ValueError,'duplicate'):
            builder.build([row,row.copy()],self.themes)

    def test_bad_url_fails_loudly(self):
        row={'書名':'New Test','著者名':'Tester','出版社':'Press','主テーマ':self.themes[0]['name'],'版元URL':'javascript:alert(1)'}
        with self.assertRaisesRegex(ValueError,'URL must be'):
            builder.build([row],self.themes)

if __name__=='__main__':unittest.main()
