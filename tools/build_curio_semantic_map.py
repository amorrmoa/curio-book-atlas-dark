#!/usr/bin/env python3
"""Generate a semantic 2-D ocean concept map for Curio Book Atlas.

--backend semantic: real multilingual embeddings and UMAP; Fails if unavailable.
--backend preview: explicitly marked lexical/theme approximation, no network.

Each edition can be generated from master.xlsx or a prior catalog JSON. Existing
concept positions are aligned by a similarity transform and retained on update.
"""
from __future__ import annotations
import argparse
import base64
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import os

import numpy as np
from sklearn.preprocessing import normalize
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.metrics.pairwise import cosine_similarity

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import build_curio_idea_map as source

MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
SEED=42
W,H=1360,900


def vectorize(data, backend):
    words=data['concepts']; books=data['books']
    byid={b['id']:b for b in books}
    allthemes=sorted(set(b['theme'] for b in books if b['theme']))
    # Explicitly separate a name and its contextual book evidence.
    concept_labels=[c['label'].replace(' / Ceroplastics',' / wax modeling') for c in words]
    titles=[b['title'] for b in books]
    texts=concept_labels+titles+allthemes
    if backend=='semantic':
        try:
            from sentence_transformers import SentenceTransformer
            model=SentenceTransformer(MODEL,device='cpu')
            representations=np.asarray(model.encode(texts, batch_size=32, show_progress_bar=False,normalize_embeddings=True),dtype='float64')
        except Exception as exc:
            raise RuntimeError('多言語モデルを取得・実行できません。GitHub Actionsの依存関係/通信を確認してください。') from exc
    else:
        # Unambiguously labelled local approximation: character and word TF-IDF,
        # book evidence and themes. This is NOT a pretrained semantic embedding.
        corpus=[' '.join([x,x]) for x in concept_labels]+titles+allthemes
        char=TfidfVectorizer(analyzer='char',ngram_range=(2,5),min_df=1,sublinear_tf=True)
        word=TfidfVectorizer(analyzer='word',ngram_range=(1,2),token_pattern=r'(?u)\b\w\w+\b',sublinear_tf=True)
        from scipy.sparse import hstack
        X=hstack([char.fit_transform(corpus),word.fit_transform(corpus)],format='csr')
        components=min(64, X.shape[0]-1,X.shape[1]-1)
        representations=TruncatedSVD(n_components=components,random_state=SEED).fit_transform(X)
        representations=normalize(representations)
    n=len(words);m=len(books)
    book_vec=representations[n:n+m]
    theme_vec={t:representations[n+m+i] for i,t in enumerate(allthemes)}
    books_index={b['id']:i for i,b in enumerate(books)}
    total=[]
    for i,c in enumerate(words):
        bidx=[books_index[b] for b in c['books'] if b in books_index]
        context=normalize(book_vec[bidx].mean(axis=0).reshape(1,-1))[0] if bidx else representations[i]
        # The name anchors meaning; book and topic context disambiguate polysemy.
        th=theme_vec.get(c.get('theme',''))
        combo=.50*representations[i]+.40*context+(.10*th if th is not None else 0)
        total.append(combo)
    return normalize(np.array(total,dtype='float64'))


def semantic_edges(data,vectors):
    concepts=data['concepts']; N=len(concepts)
    ids=[c['id'] for c in concepts]
    C=cosine_similarity(vectors)
    overlap={}
    for i in range(N):
        a=set(concepts[i]['books'])
        for j in range(i+1,N):
            overlap[(i,j)]=len(a.intersection(concepts[j]['books']))
    candidates={}
    for i in range(N):
        for j in range(i+1,N):
            shared=overlap[(i,j)]
            score=round(float(C[i,j]),4)
            # Evidence: semantic embedding + shared books; overlapping terms are stronger.
            weight=.84*max(score,0)+.16*(1-math.exp(-shared*.7))
            candidates[(i,j)]=(weight,score,shared)
    chosen=set()
    for i in range(N):
        ranked=[]
        for j in range(N):
            if j==i:continue
            a,b=sorted((i,j));val=candidates[(a,b)]
            ranked.append((val[0],j))
        ranked.sort(key=lambda p:(-p[0],ids[p[1]]))
        for val,j in ranked[:3]:
            a,b=sorted((i,j));
            if val>=.28 or j==ranked[0][1]: chosen.add((a,b))
    edges=[]
    for i,j in sorted(chosen):
        weight,sim,shared=candidates[(i,j)]
        edges.append({'a':ids[i],'b':ids[j],'weight':round(weight,3),
                      'similarity':sim,'sharedBooks':shared,
                      'relation':'shared-books' if shared else 'semantic'})
    return edges


def layout(vectors,backend):
    if len(vectors)<4:
        xs=np.arange(len(vectors),dtype='float64')
        return np.stack((xs,np.sin(xs)),axis=1)
    if backend=='semantic':
        try:
            import umap
            reducer=umap.UMAP(n_neighbors=min(13,len(vectors)-1),n_components=2,
                             min_dist=.16,metric='cosine',random_state=SEED)
            emb=np.asarray(reducer.fit_transform(vectors),dtype='float64')
        except Exception as exc:
            raise RuntimeError('UMAPの計算に失敗しました。') from exc
    else:
        # Local preview does not claim UMAP or full semantic distances.
        from sklearn.manifold import SpectralEmbedding
        cos=np.maximum(0,cosine_similarity(vectors))
        np.fill_diagonal(cos,1)
        # positive affinity graph, deterministic spectral embedding
        emb=SpectralEmbedding(n_components=2,affinity='precomputed',random_state=SEED).fit_transform(cos)
    return emb


def normalize_canvas(xy):
    # Rescale isotropically to avoid misrepresenting angles/relative distances.
    emb=np.asarray(xy,dtype=float)
    emb=emb-np.mean(emb,axis=0)
    ext=emb.max(axis=0)-emb.min(axis=0)
    if ext[1]>ext[0]*1.6:
        emb=emb[:,[1,0]]
    # Avoid a single outlier compressing the remaining 90 concepts into a knot.
    low=np.quantile(emb,.07,axis=0);hi=np.quantile(emb,.93,axis=0)
    clipped=np.clip(emb,low,hi)
    ranges=clipped.max(axis=0)-clipped.min(axis=0)
    scale=min(840/max(ranges[0],1e-7),560/max(ranges[1],1e-7))
    emb=clipped*scale
    emb-=np.mean(emb,axis=0)
    emb[:,0]+=840
    emb[:,1]+=445
    return emb


def similarity_align(new, old):
    # Orthogonal Procrustes + scalar + translation minimizes shifting of old points.
    x=np.array(new,float); y=np.array(old,float)
    mx=x.mean(axis=0);my=y.mean(axis=0)
    x0=x-mx;y0=y-my
    u,s,vt=np.linalg.svd(x0.T@y0)
    rot=u@vt
    factor=float(np.sum(s)/max(np.sum(x0*x0),1e-9))
    factor=max(.60,min(1.35,factor))
    return (np.asarray(new)-mx)@rot*factor+my


def relax_labels(data, coords, old_positions=None):
    concepts=data['concepts'];ids=[c['id'] for c in concepts]
    points={id_:np.array(coords[k],float) for k,id_ in enumerate(ids)}
    prev=old_positions or {}
    # Only visible text receives collision repulsion. Dots stay selectable.
    major=[c for c in concepts if c['major']]
    for it in range(230):
        delta={i:np.zeros(2,dtype=float) for i in ids}
        for i, ca in enumerate(major):
            a=ca['id'];ax,ay=points[a]
            aw=26+len(ca['label'])*9.4
            for cb in major[i+1:]:
                b=cb['id'];bx,by=points[b]
                bw=26+len(cb['label'])*9.4
                # Label boxes start slightly right of each node circle.
                ovx=min(ax+aw,bx+bw)-max(ax,bx)
                ovy=26-abs(ay-by)
                if ovx>0 and ovy>0:
                    dx=ax-bx;dy=ay-by
                    if abs(dy)<4:dy=(1 if a<b else -1)*4
                    step=np.array([.16*(ovx+8)*np.sign(dx),
                                   (ovy+5)*.78*np.sign(dy)])
                    # Push both nodes off the overlap without discarding neighborhoods.
                    delta[a]+=step; delta[b]-=step
        for id_ in ids:
            p=points[id_]
            step=np.clip(delta[id_],-3.8,3.8)
            if id_ in prev:
                original=np.array([prev[id_]['x'],prev[id_]['y']],float)
                nextp=p+step*.25
                displacement=nextp-original
                length=np.linalg.norm(displacement)
                if length>25:nextp=original+displacement/length*25
                points[id_]=nextp
            else:
                points[id_]=p+step*.54
            points[id_][0]=np.clip(points[id_][0],355,1220)
            points[id_][1]=np.clip(points[id_][1],98,775)
    return points


def rebuild(input_path,out,template,camel,backend,previous_data=None):
    input_path=Path(input_path)
    if input_path.suffix.lower()=='.xlsx':
        books=source.xlsx_rows(input_path)
    else:
        raw=json.loads(input_path.read_text(encoding='utf-8'))
        if isinstance(raw,dict):raw=raw.get('books',raw.get('items',[]))
        if not isinstance(raw,list):raise ValueError('Unsupported JSON book data')
        books=[]
        for idx,b in enumerate(raw):
            books.append({'ID':str(b.get('id') or b.get('ID') or f'curio-{idx+1:03d}'),
              '書名':str(b.get('title') or b.get('書名') or ''),
              '著者名':str(b.get('author') or b.get('著者名') or ''),
              '出版社':str(b.get('publisher') or b.get('出版社') or ''),
              '刊行年':str(b.get('year') or b.get('刊行年') or ''),
              '主テーマ':str(b.get('theme') or b.get('主テーマ') or ''),
              '関連テーマ':str(b.get('relatedThemes') or b.get('関連テーマ') or ''),
              '版元URL':str(b.get('url') or b.get('版元URL') or '')})
        books=[b for b in books if b['書名']]
    if len(books)<1:raise ValueError('No books found')
    old=source.build_map(books)
    # Keep every node searchable, but use editorially balanced labels to avoid
    # illegible typography. Hidden labels appear on hover / keyboard focus.
    rank=sorted(old['concepts'], key=lambda c:(-c['count'], -len(c['label'])**-1, c['id']))
    visible_ids=set(c['id'] for c in rank[:44])
    for c in old['concepts']:
        c['major']=c['id'] in visible_ids
    vec=vectorize(old,backend)
    emb=normalize_canvas(layout(vec,backend))
    previous={}
    if previous_data and Path(previous_data).exists():
        prevdata=json.loads(Path(previous_data).read_text(encoding='utf-8'))
        if prevdata.get('meta',{}).get('method')==backend:
            previous={c['id']:c for c in prevdata.get('concepts',[])}
    ids=[c['id'] for c in old['concepts']]
    shared=[(i,previous[x]) for i,x in enumerate(ids) if x in previous]
    if len(shared)>=4:
        aligned=similarity_align(emb[[x for x,y in shared]],[[p['x'],p['y']] for k,p in shared])
        # The transform estimated on matched points is applied to all current points.
        new_partial=emb[[i for i,p in shared]]
        mx=np.mean(new_partial,axis=0);my=np.mean(np.array([[p['x'],p['y']] for i,p in shared]),axis=0)
        x0=new_partial-mx; y0=np.array([[p['x'],p['y']] for i,p in shared])-my
        u,s,vt=np.linalg.svd(x0.T@y0);rot=u@vt
        scale=max(.60,min(1.35,float(np.sum(s)/max(np.sum(x0*x0),1e-9))))
        emb=(emb-mx)@rot*scale+my
        for i,cid in enumerate(ids):
            if cid in previous:
                emb[i]=.88*np.array([previous[cid]['x'],previous[cid]['y']]) + .12*emb[i]
    pts=relax_labels(old,emb,previous)
    edges=semantic_edges(old,vec)
    for i,c in enumerate(old['concepts']):
        c['x']=round(float(pts[c['id']][0]),1)
        c['y']=round(float(pts[c['id']][1]),1)
    old['edges']=edges
    old['meta'].update({'method':backend,
        'layout': 'multilingual-semantic-umap' if backend=='semantic' else 'lexical-theme-preview',
        'model':MODEL if backend=='semantic' else 'tfidf-spectral (preview only)',
        'map_version':3,
        'seed':SEED,
        'source':input_path.name,
        'edges':len(edges)})
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    html=Path(template).read_text(encoding='utf-8')
    asset=base64.b64encode(Path(camel).read_bytes()).decode('ascii')
    html=html.replace('__CAMEL_ASSET__','data:image/webp;base64,'+asset)
    safe_json=json.dumps(old,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    html=html.replace('/* __EMBED_DATA__ */','const ATLAS_DATA='+safe_json+';')
    if '__EMBED_DATA__' in html or '__CAMEL_ASSET__' in html:raise ValueError('Missing template replacement')
    out.write_text(html,encoding='utf-8')
    dat=out.with_name('curio-idea-atlas-data.json')
    dat.write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'OK: {len(books)} books, {len(ids)} concepts, {len(edges)} routes | {old["meta"]["layout"]}')
    return old


def choose_master():
    root=HERE.parent
    # Prefer the source containing the most complete / newest catalog.
    # Do not silently re-use the map's own old embedded JSON when another
    # qualified source exists: that would freeze the book count after 190.
    preferred=[root/'data'/'curio_catalog.xlsx',root/'curio_catalog.xlsx',root/'data'/'curio_catalog_master.xlsx']
    excel_files=sorted(set(f for f in root.rglob('*.xlsx') if '.git' not in f.parts))
    candidates=[]
    for f in excel_files:
        try:
            rs=source.xlsx_rows(f)
            if len(rs)>=1 and '書名' in rs[0]:
                # On first deployment keep an included 190-book seed as fallback,
                # but never let it override an equally sized live catalog.
                rank = 2 if f.name == 'curio_idea_atlas_seed.xlsx' else (5 if f in preferred else 4)
                candidates.append((len(rs),rank,f))
        except Exception:continue
    for f in sorted(set(list((root/'docs').rglob('*.json'))+list((root/'data').rglob('*.json')) if (root/'data').exists() else list((root/'docs').rglob('*.json')))):
        if not any(t in f.name.lower() for t in ['book','catalog','manual','idea-atlas-data']):continue
        try:
            obj=json.loads(f.read_text(encoding='utf-8'))
            if isinstance(obj,dict):obj=obj.get('books',obj.get('items',[]))
            if not isinstance(obj,list):continue
            count=sum(bool(b.get('title') or b.get('書名')) for b in obj if isinstance(b,dict))
            if count>=1:
                priority=1 if f.name=='curio-idea-atlas-data.json' else 3
                candidates.append((count,priority,f))
        except Exception:continue
    if not candidates:
        raise RuntimeError('最新のExcelまたは書誌JSONが見つかりません。--input で指定してください。')
    candidates.sort(key=lambda item:(-item[0],-item[1],str(item[2])))
    best=candidates[0]
    tied=[c for c in candidates if c[0]==best[0] and c[1]==best[1]]
    if len(tied)>1:
        raise RuntimeError('マスター候補が同数です: '+', '.join(str(c[2]) for c in tied)+'. --input で指定してください。')
    print('Using catalog:',best[2],f'({best[0]} books)')
    return best[2]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',default=None)
    p.add_argument('--out',default=str(HERE.parent/'docs'/'curio-idea-atlas.html'))
    p.add_argument('--template',default=str(HERE/'curio-idea-atlas.template.html'))
    p.add_argument('--camel',default=str(HERE/'camel-book-sea.webp'))
    p.add_argument('--backend',choices=['semantic','preview'],default='semantic')
    p.add_argument('--previous',default=None)
    args=p.parse_args()
    out=Path(args.out)
    previous=args.previous or out.with_name('curio-idea-atlas-data.json')
    rebuild(args.input or choose_master(),out,args.template,args.camel,args.backend,previous)

if __name__=='__main__':main()
