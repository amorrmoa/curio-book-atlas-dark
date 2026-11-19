#!/usr/bin/env python3
"""Build a self-contained, dependency-free 2D concept sea chart from the Curio Excel master.
Usage: python build_curio_idea_map.py curio_catalog.xlsx
Writes curio-idea-atlas.html beside this script. Python standard library only.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import html
import json
import math
from pathlib import Path
import re
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
DEFAULT_XLSX=HERE/'curio_catalog(4).xlsx'
DEFAULT_HTML=HERE/'curio-idea-atlas.html'
TEMPLATE=HERE/'curio-idea-atlas.template.html'

STOPWORDS=set('''
a an the of in on and to at by for with without into from against through toward across between over under up upon
as or nor not than which what who where when why whose how whose there their our your his her its are was were been being
is has have had all some any other more most new old this that these those each both every also such much many
le la les des du de del della delle dei degli dell di da il lo gli uno una un une en et y e los las el der die das dem den
des deux un uno ein eine einem einem einer und von zu zur zum aus im auf bei et al
vol volume edition complete archive introduction guide reader survey selected new revised
early modern history histories cultural culture study studies art arts visual book books research
world worlds europe european global century centuries twentieth nineteenth eighteenth seventeenth
century ancient contemporary age ages story stories title view views essays essay toward making
their his other new little big middle point points life lives part first second third
search edition complete a1 b1 una volta once'''.split())
# Keep terms that actually occur in a title; a small priority list retains rare but useful topics.
SPECIAL=set('''
wax ceroplastica cera wunderkammer curiosities curiosity cabinet cabinets occult supernatural alchemy
kircher optics optical anatomy anatomical grotesque monster monsters beast beasts labyrinth
emblem emblems shadow shadows cinema magic phantoms phantom spirit spirits miniature
microscope microscopy telescope diagram diagrams imaginary imagination illusion machines machine
mechanism instruments instrument illustration printing museum museums gothic insects dinosaurs
fashion fashioning nature naturewriting surrealist surrealism celestial ritual painting photography
body bodies death medicine medical ghost ghosts musical music sound literature library
architecture garden gardens collecting collection witchcraft ritual perform performance theater theatre
marvel marvels curiosity performance archive ecology ecology creatures creature exotic automata
technology visuality material decorative wonder wonders botany botanical zoology naturalism
'''.split())
CANON={
 'bodies':'body','arts':'art','artists':'artist','books':'book','images':'image','machines':'machine',
 'creatures':'creature','beasts':'beast','instruments':'instrument','sounds':'sound',
 'gardens':'garden','cities':'city','photographs':'photography','paintings':'painting',
 'sciences':'science','emblems':'emblem','labyrinths':'labyrinth','monsters':'monster',
 'theatre':'theater','theatres':'theater','theaters':'theater','musical':'music','museums':'museum',
 'phantoms':'phantom','spirits':'spirit','shadows':'shadow','cabinets':'cabinet',
 'ceroplastica':'wax','cera':'wax','optical':'optics','anatomical':'anatomy','wonders':'wonder',
 'curiosities':'curiosity','collecting':'collection','creatures':'creature',
 'eighteenth-century':'18th century','seventeenth-century':'17th century',
 'nineteenth-century':'19th century',
}
PALETTE=['#c7ecf5','#ffcbd9','#f5ddae','#c8d5ff','#d8d1f6','#bce7dc','#f0bfc9','#d2e8b8',
         '#eac7ef','#a4d9ed','#f9d0b1','#c9d8f7','#bce8dc','#e0d3bd']
THEME_NAMES=[
 '驚異の部屋・蒐集','変身・異形・グロテスク','魔術・神秘・信仰','博物誌・自然・動物',
 '身体・解剖・感覚','書物・図像・出版文化','映画・映像・メディア','都市・社会・政治文化',
 '演劇・見世物・祝祭','音楽・音響・サブカルチャー','建築・空間・庭園','絵画・装飾・美術史',
 '時間・記憶・歴史意識','機械・技術・科学史'
]
ANCHORS=[(230,170),(480,142),(735,205),(1050,170),(180,380),(450,355),(740,387),(1060,386),
         (230,625),(485,602),(760,610),(1060,622),(610,780),(980,780)]
TOKEN_RE=re.compile(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ'’\-]*")
W_NS='{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'


def xlsx_rows(path:Path):
    """Read the first worksheet of Excel master using zipfile/XML (no external dependencies)."""
    with zipfile.ZipFile(path) as z:
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in root.findall(W_NS+'si'):
                shared.append(''.join((t.text or '') for t in si.iter(W_NS+'t')))
        # Use sheet1, matching the workbook's first tab. Re-evaluate if name changes.
        sheet_name='xl/worksheets/sheet1.xml'
        if sheet_name not in z.namelist():
            raise ValueError('最初のシートが見つかりません')
        root=ET.fromstring(z.read(sheet_name))
        def col_index(ref:str):
            a=re.match(r'[A-Z]+',ref)
            if not a:return 0
            j=0
            for c in a.group():j=j*26+ord(c)-64
            return j-1
        data=[]
        for row in root.iter(W_NS+'row'):
            cell_dict={}
            for c in row.findall(W_NS+'c'):
                ix=col_index(c.get('r','A'))
                typ=c.get('t','')
                if typ=='inlineStr':
                    val=''.join((t.text or '') for t in c.iter(W_NS+'t'))
                else:
                    v=c.find(W_NS+'v')
                    val=v.text if v is not None and v.text is not None else ''
                    if typ=='s' and val!='':val=shared[int(val)]
                cell_dict[ix]=val
            if cell_dict:
                data.append([cell_dict.get(i,'') for i in range(max(cell_dict)+1)])
        if not data:return []
        hdr=[str(h).strip() for h in data[0]]
        rows=[]
        for idx,arr in enumerate(data[1:],start=2):
            r={key: (str(arr[i]).strip() if i<len(arr) else '') for i,key in enumerate(hdr)}
            if r.get('書名'):
                rows.append(r)
        return rows


def token_list(title):
    tokens=[]
    for word in TOKEN_RE.findall(unicodedata.normalize('NFKC',title)):
        word=word.strip("'’-").lower()
        word=CANON.get(word,word)
        if word in STOPWORDS or (len(word)<4 and word not in SPECIAL and word not in {'art','eye','ink'}):continue
        if re.fullmatch(r'[ivxlcm]+',word):continue
        if word.endswith('ies') and len(word)>5: word=word[:-3]+'y'
        elif word.endswith('s') and len(word)>5 and not word.endswith(('ss','us','is')):word=word[:-1]
        word=CANON.get(word,word)
        if word not in STOPWORDS:
            tokens.append(word)
    return list(dict.fromkeys(tokens))


def split_themes(text):return [x.strip() for x in re.split(r'[、,;/／]+',text or '') if x.strip()]

def stable_frac(s):return int.from_bytes(hashlib.blake2b(s.encode(),digest_size=8).digest(),'big')/2**64

def clamp(v,a,b):return max(a,min(b,v))

def build_map(books):
    counts=Counter(); book_terms={}; theme_hist={}; book_by_id={}
    for idx,book in enumerate(books):
        ident=book.get('ID') or f'curio-{idx+1:04d}'
        book['ID']=ident
        terms=set(token_list(book['書名']))
        book_terms[ident]=terms
        counts.update(terms)
        book_by_id[ident]=book
    # Prioritize recurrent title words; retain rare domain-specific words and avoid generic filler.
    ranked=[]
    for word,ct in counts.items():
        if ct < 2 and word not in SPECIAL: continue
        if word in STOPWORDS or (ct==1 and word not in SPECIAL):continue
        domain_boost = 3.5 if word in SPECIAL else 0
        if len(word)>8: domain_boost+=.4
        ranked.append((word,ct,ct*2.0+domain_boost))
    ranked.sort(key=lambda t:(-t[2],-t[1],t[0]))
    # Expand vocabulary as the catalog grows, while keeping the map usable.
    max_concepts=min(220,max(105,len(books)//2))
    ranked=ranked[:max_concepts]
    vocab={word for word,_,_ in ranked}
    concept_books=defaultdict(list)
    concept_theme=defaultdict(Counter)
    co=Counter()
    for b in books:
        bid=b['ID']
        toks=sorted(book_terms[bid] & vocab)
        for t in toks:
            concept_books[t].append(bid)
            concept_theme[t][b.get('主テーマ','')] += 1
            for r in split_themes(b.get('関連テーマ','')):
                concept_theme[t][r]+=.30
        for i,one in enumerate(toks):
            for two in toks[i+1:]:co[(one,two)]+=1
    words=[word for word,_,_ in ranked]
    theme_idx={t:i for i,t in enumerate(THEME_NAMES)}
    # Cosine of theme distributions + shared title, no claim of learned semantic embeddings.
    edge_scores={}
    for i,a in enumerate(words):
        ca=concept_theme[a]
        za=math.sqrt(sum(v*v for v in ca.values())) or 1
        for b in words[i+1:]:
            cb=concept_theme[b]
            zb=math.sqrt(sum(v*v for v in cb.values())) or 1
            sim=sum(v*cb.get(t,0) for t,v in ca.items())/(za*zb)
            joint=co.get((a,b),co.get((b,a),0))
            score=sim*.68 + min(joint,3)*.65
            if score>0.13:
                edge_scores[(a,b)]=score
    edges=set()
    for a in words:
        sims=[]
        for (x,y),weight in edge_scores.items():
            if x==a:sims.append((y,weight))
            if y==a:sims.append((x,weight))
        sims.sort(key=lambda z:-z[1])
        for b,sim in sims[:3]:edges.add(tuple(sorted((a,b))))
    # Initial geographic anchors from dominant category; stable hash-driven spread.
    coords={}
    for word in words:
        primary=concept_theme[word].most_common(2)
        anchor=ANCHORS[theme_idx.get(primary[0][0],len(ANCHORS)-1)] if primary else ANCHORS[0]
        if len(primary)>1 and primary[1][0] in theme_idx:
            second=ANCHORS[theme_idx[primary[1][0]]]
            mix=min(.23, .20*primary[1][1]/max(primary[0][1],1))
            anchor=(anchor[0]*(1-mix)+second[0]*mix, anchor[1]*(1-mix)+second[1]*mix)
        a=stable_frac(word+'-angle')*2*math.pi
        r=48+stable_frac(word+'-radius')*107
        coords[word]=[anchor[0]+r*math.cos(a), anchor[1]+r*math.sin(a)]
    # Smoothing and physical collision resolution; deterministic offline, zero browser CPU cost.
    edge_pairs=[(a,b,edge_scores.get((a,b),edge_scores.get((b,a),.1))) for a,b in edges]
    for iteration in range(95):
        forces={w:[0.,0.] for w in words}
        for a,b,sim in edge_pairs:
            ax,ay=coords[a];bx,by=coords[b];dx=bx-ax;dy=by-ay
            d=math.hypot(dx,dy)+1e-6
            k=.006*min(sim,1.8)*(d-180)
            fx=k*dx/d;fy=k*dy/d
            forces[a][0]+=fx;forces[a][1]+=fy;forces[b][0]-=fx;forces[b][1]-=fy
        for i,a in enumerate(words):
            ax,ay=coords[a]
            for b in words[i+1:]:
                bx,by=coords[b];dx=ax-bx;dy=ay-by
                d=math.hypot(dx,dy)+1e-5
                if d<76:
                    k=(76-d)*.08
                    fx=k*dx/d;fy=k*dy/d
                    forces[a][0]+=fx;forces[a][1]+=fy;forces[b][0]-=fx;forces[b][1]-=fy
        for w in words:
            x,y=coords[w];fx,fy=forces[w]
            coords[w]=[clamp(x+clamp(fx,-6,6),75,1290),clamp(y+clamp(fy,-6,6),96,850)]
    # Greedy label collisions: displace along short spiral. Concept circles remain near thematic anchors.
    placed=[]
    positions={}
    for w in sorted(words,key=lambda a:(-counts[a],-len(concept_books[a]),a)):
        x,y=coords[w]
        label_width=22+len('Wax / Ceroplastics' if w=='wax' else w.title())*8.3
        def overlap(px,py):
            rect=(px-7,py-12,px+label_width,py+12)
            n=0
            for r in placed:
                if rect[0]<r[2]+7 and rect[2]+7>r[0] and rect[1]<r[3]+6 and rect[3]+6>r[1]:n+=1
            return n
        best=(10**9,x,y)
        for k in range(500):
            a=(k*2.3999632+stable_frac(w)*2*math.pi)
            r=(k**.5)*16
            px=clamp(x+math.cos(a)*r,65,1310-label_width)
            py=clamp(y+math.sin(a)*r,70,860)
            ov=overlap(px,py)
            rating=ov*1000+k
            if rating<best[0]:best=(rating,px,py)
            if ov==0:break
        _,px,py=best
        positions[w]=[round(px,1),round(py,1)]
        placed.append((px-7,py-12,px+label_width,py+12))
    concepts=[]
    for word,ct,score in ranked:
        tm=concept_theme[word]
        dominant=tm.most_common(1)[0][0] if tm else ''
        idx=theme_idx.get(dominant,0)
        label=word.title().replace('Wax','Wax').replace('18Th','18th')
        if word=='wax':label='Wax / Ceroplastics'
        concepts.append({'id':word,'label':label,'x':positions[word][0],'y':positions[word][1],
                         'count':len(concept_books[word]),'color':PALETTE[idx],
                         'major':ct>=3 or word in SPECIAL,
                         'books':concept_books[word],
                         'theme':dominant})
    edges_out=[]
    for a,b in sorted(edges):
        w=edge_scores.get((a,b),edge_scores.get((b,a),.2))
        edges_out.append({'a':a,'b':b,'weight':round(w,3)})
    book_out=[]
    for b in books:
        book_out.append({'id':b['ID'],'title':b['書名'],'author':b.get('著者名',''),
                         'publisher':b.get('出版社',''),'year':b.get('刊行年',''),
                         'theme':b.get('主テーマ',''),'url':b.get('版元URL',''),
                         'concepts':sorted(book_terms[b['ID']] & vocab)})
    return {'meta':{'books':len(books),'concepts':len(concepts)},'concepts':concepts,'edges':edges_out,'books':book_out}


def main():
    p=argparse.ArgumentParser(description='Build Curio Concept Sea Atlas from Excel')
    p.add_argument('xlsx',nargs='?',default=str(DEFAULT_XLSX),help='Excel master path')
    p.add_argument('--output',default=str(DEFAULT_HTML),help='Output HTML path')
    args=p.parse_args()
    rows=xlsx_rows(Path(args.xlsx))
    if not rows:raise SystemExit('書誌データが空です')
    data=build_map(rows)
    tpl=TEMPLATE.read_text(encoding='utf-8')
    asset=HERE/'camel-book-sea.webp'
    if asset.exists():
        encoded=base64.b64encode(asset.read_bytes()).decode('ascii')
        tpl=tpl.replace('__CAMEL_ASSET__', 'data:image/webp;base64,'+encoded)
    else:
        raise SystemExit('駱駝イラスト camel-book-sea.webp が見つかりません')
    safe_json=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    out=tpl.replace('/* __EMBED_DATA__ */',f'const ATLAS_DATA={safe_json};')
    if out==tpl:raise SystemExit('HTMLテンプレートにデータ埋め込み位置がありません')
    Path(args.output).write_text(out,encoding='utf-8')
    (Path(args.output).parent/'curio-idea-atlas-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'OK: {len(rows)}冊 / {len(data["concepts"])}概念 / {len(data["edges"])}航路')
    print('HTML:',args.output)
if __name__=='__main__':main()
