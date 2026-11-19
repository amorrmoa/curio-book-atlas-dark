import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
class PublisherAtlasTests(unittest.TestCase):
    def test_page_and_link_file_exist(self):
        self.assertTrue((ROOT/'docs/publishers.html').is_file())
        self.assertTrue((ROOT/'docs/data/publisher_links.js').is_file())

    def test_main_page_link_and_search_accepts_publisher(self):
        main = (ROOT/'docs/index.html').read_text()
        self.assertIn('href="publishers.html"',main)
        self.assertIn("get('publisher')",main)
        self.assertIn("$('search').value=publisherFromAtlas", main)

    def test_publisher_page_uses_master_catalog(self):
        page=(ROOT/'docs/publishers.html').read_text()
        self.assertIn('./data/catalog.js',page)
        self.assertIn('new Set(names)', page)
        self.assertIn('publisher_links.js',page)
        self.assertIn('出版社CSV',page)

    def test_all_external_links_are_https(self):
        links=(ROOT/'docs/data/publisher_links.js').read_text()
        urls=re.findall(r"url:'([^']+)'",links)
        self.assertGreaterEqual(len(urls), 15)
        for url in urls:
            self.assertTrue(url.startswith('https://'), url)

    def test_public_books_unchanged(self):
        books=json.loads((ROOT/'docs/data/books.json').read_text())['books']
        self.assertGreaterEqual(len(books),181)
        self.assertEqual(len(books),json.loads((ROOT/'docs/data/books.json').read_text())['meta']['count'])

if __name__=='__main__':unittest.main()
