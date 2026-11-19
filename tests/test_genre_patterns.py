import json, unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
class GenreTests(unittest.TestCase):
 def test_theme_coverage(self):
  page=(root/'docs/index.html').read_text('utf-8')
  themes=json.loads((root/'docs/data/themes.json').read_text('utf-8'))['themes']
  for t in themes:self.assertIn('"'+t['id']+'":',page)
  self.assertEqual(len(themes),14)
 def test_no_book_loss(self):
  d=json.loads((root/'docs/data/books.json').read_text('utf-8'))
  self.assertEqual(len(d['books']),d['meta']['count'])
  self.assertGreaterEqual(len(d['books']),181)
  self.assertTrue(all(b['theme'] in {t['id'] for t in json.loads((root/'docs/data/themes.json').read_text('utf-8'))['themes']} for b in d['books']))
 def test_belongs_to_primary_theme(self):
  page=(root/'docs/index.html').read_text('utf-8')
  self.assertIn('motifSvg(b.theme)',page)
  self.assertIn('motifSvg(t.id)',page)
  self.assertNotIn('cover-v${index%6}',page)
if __name__=='__main__': unittest.main()
