#!/usr/bin/env python3
"""Excel -> static Curio Book Atlas catalog. No network access and no auto-discovery.

Supports ordinary Excel .xlsx files using only Python's standard library. Input is
`data/curio_catalog.xlsx`, worksheet `書誌と分類`, with named column headers.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'data' / 'curio_catalog.xlsx'
THEMES = ROOT / 'docs' / 'data' / 'themes.json'
BOOKS = ROOT / 'docs' / 'data' / 'books.json'
JS = ROOT / 'docs' / 'data' / 'catalog.js'
MAIN_SHEET = '書誌と分類'
X = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def colno(address: str) -> int:
    m = re.match(r'([A-Z]+)', address)
    if not m:
        raise ValueError(f'Excel address invalid: {address!r}')
    val = 0
    for c in m.group(1): val = val * 26 + ord(c) - 64
    return val-1


def parse_xlsx(path: Path, sheet_name: str = MAIN_SHEET) -> list[dict]:
    if not path.exists(): raise FileNotFoundError(path)
    with ZipFile(path) as z:
        names = set(z.namelist())
        strings = []
        if 'xl/sharedStrings.xml' in names:
            shared = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in shared.findall(f'{X}si'):
                strings.append(''.join(t.text or '' for t in si.iter(f'{X}t')))
        book = ET.fromstring(z.read('xl/workbook.xml'))
        rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        relmap = {el.attrib['Id']:el.attrib['Target'] for el in rels.findall(f'{P}Relationship')}
        sheets = book.find(f'{X}sheets')
        selected = next((s for s in sheets if s.attrib.get('name') == sheet_name), None)
        if selected is None:
            raise ValueError(f'Sheet {sheet_name!r} was not found. Available: {[s.attrib.get("name") for s in sheets]}')
        target = relmap[selected.attrib[f'{R}id']]
        if target.startswith('/'): filename = target.lstrip('/')
        else: filename = 'xl/' + target.lstrip('/')
        tree = ET.fromstring(z.read(filename))
        found_rows = []
        for el in tree.findall(f'.//{X}sheetData/{X}row'):
            row = {}
            for cell in el.findall(f'{X}c'):
                ci = colno(cell.attrib['r'])
                kind = cell.attrib.get('t','')
                v = cell.find(f'{X}v')
                if kind == 'inlineStr':
                    inline = cell.find(f'{X}is')
                    value = ''.join(t.text or '' for t in inline.iter(f'{X}t')) if inline is not None else ''
                elif v is None:
                    value = ''
                elif kind == 's': value = strings[int(v.text or '0')]
                elif kind in ('str','e'): value = v.text or ''
                elif kind == 'b': value = (v.text == '1')
                else:
                    raw = v.text or ''
                    try: value = int(raw) if re.fullmatch(r'-?\d+', raw) else float(raw)
                    except (TypeError,ValueError): value = raw
                row[ci] = value
            found_rows.append(row)
    if not found_rows: raise ValueError('No data rows in spreadsheet')
    keys = {k:str(v).strip() for k,v in found_rows[0].items() if str(v).strip()}
    result=[]
    for raw in found_rows[1:]:
        obj={column:raw.get(i,'') for i,column in keys.items()}
        if any(str(v).strip() for v in obj.values()):result.append(obj)
    return result


def normalized(s: str) -> str:
    return re.sub(r'[^a-z0-9\u3040-\u30ff\u3400-\u9fff]', '', s.casefold())


def clean_year(value, max_value, name, line):
    if value in (None, ''): return None
    try:
        x = int(value)
        if not (1 <= x <= max_value):raise ValueError()
    except (TypeError,ValueError):
        raise ValueError(f'Row {line}: invalid {name} {value!r}')
    return x


def safe_http_url(raw: object, line: int) -> str:
    value = str(raw or '').strip()
    if not value: return ''
    u = urlsplit(value)
    if u.scheme not in ('http','https') or not u.netloc:
        raise ValueError(f'Row {line}: URL must be http(s): {value}')
    return value


def validated_isbn(value: object, line: int) -> str:
    raw = str(value or '').strip()
    if not raw: return ''
    isbn = re.sub(r'[\s-]', '', raw)
    if not re.fullmatch(r'97[89][0-9]{10}', isbn):
        raise ValueError(f'Row {line}: invalid ISBN-13: {raw!r}')
    checksum=(10 - sum(int(c)*(1 if i % 2 == 0 else 3) for i,c in enumerate(isbn[:12])) % 10) % 10
    if checksum != int(isbn[12]):
        raise ValueError(f'Row {line}: bad ISBN-13 checksum: {raw!r}')
    return isbn


def build(rows: list[dict], definitions: list[dict]) -> list[dict]:
    by_name={t['name']:t['id'] for t in definitions}
    by_name.update({t['id']:t['id'] for t in definitions})
    output=[]
    seen=set(); ids=set()
    required=['書名','著者名','出版社','主テーマ']
    for name in required:
        if not rows or name not in rows[0]:raise ValueError(f'Missing column: {name}')
    for line, r in enumerate(rows,2):
        title = str(r.get('書名') or '').strip()
        if not title:continue
        author = str(r.get('著者名') or '').strip()
        publisher = str(r.get('出版社') or '').strip()
        key=normalized(title)+'|'+normalized(author)
        if key in seen: raise ValueError(f'Row {line}: duplicate title/author: {title}')
        seen.add(key)
        year=clean_year(r.get('刊行年'),3000,'year',line)
        month=clean_year(r.get('刊行月'),12,'month',line)
        group=str(r.get('主テーマ') or '').strip()
        if group and group not in by_name:raise ValueError(f'Row {line}: unknown theme {group!r}; see テーマ一覧')
        theme=by_name.get(group,'unclassified')
        rel=str(r.get('関連テーマ') or '').strip()
        related=[]
        for tag in re.split(r'[、,，;；|]+',rel):
            tag=tag.strip()
            if not tag:continue
            if tag not in by_name:raise ValueError(f'Row {line}: unknown related theme {tag!r}')
            tid=by_name[tag]
            if tid not in related and tid != theme:related.append(tid)
        provided_id=str(r.get('ID') or '').strip()
        ident=provided_id or ('extra-'+hashlib.sha1(key.encode('utf-8')).hexdigest()[:10])
        if ident in ids:raise ValueError(f'Row {line}: duplicated ID {ident!r}')
        ids.add(ident)
        output.append({'id':ident,'title':title,'author':author,'publisher':publisher,'year':year,
            'month':month,'source_url':safe_http_url(r.get('版元URL'),line),
            'isbn':validated_isbn(r.get('ISBN'),line),
            'isbn_source_url':safe_http_url(r.get('ISBN出典URL'),line),
            'isbn_method':str(r.get('ISBN取得方法') or '').strip(),
            'theme':theme,'related':related,'origin':'manual_excel'})
    if not output:raise ValueError('Zero books found; refusing to replace the existing catalog.')
    return output


def main():
    ap=argparse.ArgumentParser(description='Update website from manually maintained Excel')
    ap.add_argument('--input',type=Path,default=CATALOG)
    ap.add_argument('--check',action='store_true',help='Validate only, do not modify output files')
    args=ap.parse_args()
    definitions=json.loads(THEMES.read_text(encoding='utf-8'))['themes']
    rows=parse_xlsx(args.input)
    items=build(rows,definitions)
    payload={'meta':{'catalog':'Curio Book Atlas',
        'updated_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'source':args.input.name,'count':len(items),
        'notice':'月別書誌リストと14テーマを掲載。ISBNの未確認項目は空欄とし、取得根拠は各書籍の詳細に記載。'},'books':items}
    print(f'Validated {len(items)} books; {sum(bool(x["isbn"]) for x in items)} ISBNs; {sum(bool(x["source_url"]) for x in items)} publisher URLs; {len(definitions)} themes.')
    if args.check:return
    BOOKS.parent.mkdir(parents=True,exist_ok=True)
    BOOKS.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    JS.write_text('window.CURIO_ATLAS = '+json.dumps({'meta':payload['meta'],'books':items,'themes':definitions},ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    print(f'Wrote {BOOKS} and {JS}')

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        sys.exit(1)
