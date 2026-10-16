#!/usr/bin/env python3
"""Build a verified 1000-title catalog from Project Gutenberg via Gutendex.
Run in an environment with internet access: python build_forgeation_1000.py
"""
import json, urllib.request, urllib.parse, time, pathlib
BASE=pathlib.Path(__file__).resolve().parent
SOURCE=BASE/'forgeation-library-books.json'
original=json.loads(SOURCE.read_text(encoding='utf-8'))
existing=original['books']
TARGET=1000
seen={(str(x.get('title','')).casefold().strip(),str(x.get('author','')).casefold().strip()) for x in existing}
books=list(existing)
url='https://gutendex.com/books/?languages=ja%2Cen&sort=popular'
headers={'User-Agent':'ForgeationLibraryCatalogBuilder/1.0 (metadata only)'}

def area_for(subjects,title):
 s=(' '.join(subjects)+' '+title).lower()
 if any(w in s for w in ('astronom','space','planet','physics','chemistry','science','biology')):return 1
 if any(w in s for w in ('history','war ','geograph','travel','politic','econom')):return 3
 if any(w in s for w in ('computer','mathematic','programming','engineering','technology')):return 4
 if any(w in s for w in ('philosoph','religion','psycholog','ethic')):return 5
 if any(w in s for w in ('children','juvenile','fairy','fable','picture book')):return 6
 if any(w in s for w in ('art ','music','theater','theatre','film','cinema')):return 7
 if any(w in s for w in ('medicine','medical','health','nursing','anatom')):return 8
 return 2

page=0
while url and len(books)<TARGET:
 page+=1
 for attempt in range(4):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as r:
    data=json.load(r)
   break
  except Exception as e:
   if attempt==3:raise RuntimeError(f'Catalog fetch failed at page {page}: {e}')
   time.sleep(2**attempt)
 for b in data.get('results',[]):
  if len(books)>=TARGET:break
  title=b.get('title','').strip(); authors=b.get('authors') or []
  author=', '.join(a.get('name','') for a in authors).strip() or '著者情報なし'
  key=(title.casefold(),author.casefold())
  if not title or key in seen:continue
  seen.add(key)
  gid=b['id']; languages=b.get('languages',[])
  gutenberg_url=f'https://www.gutenberg.org/ebooks/{gid}'
  subject=b.get('subjects',[])
  area=area_for(subject,title)
  entry={
   'id':100000+gid, 'title':title,'author':author,'area':area,
   'genre':' / '.join(subject[:2]) if subject else 'Project Gutenberg',
   'desc':f'Project Gutenbergで公開されている実在書籍（ID: {gid}）。この館内に本文は収録していません。',
   'availability':'external_public_domain', 'fullTextIncluded':False,
   'searchUrl':gutenberg_url, 'source':'Project Gutenberg',
   'sourceId':gid,'languages':languages,
   'chapters':[
    {'title':'書誌情報（本文ではありません）','text':f'書名：{title}\n著者：{author}\n提供元：Project Gutenberg\n作品番号：{gid}\n言語：{", ".join(languages)}\n※館内には本文を収録していません。'},
    {'title':'正規の書籍を読む','text':f'Project Gutenbergの作品ページで閲覧形式と利用条件を確認できます。\n{gutenberg_url}\n※国・地域により著作権の扱いが異なります。'}
   ]
  }
  books.append(entry)
 url=data.get('next')
 print(f'Fetched page {page}, books: {len(books)}',flush=True)
 if page>100:break
if len(books)<TARGET:raise RuntimeError(f'Only {len(books)} titles found. Existing JSON not overwritten.')
original['books']=books[:TARGET]
original['description']='実在書籍1000件の書誌データ（初期20冊＋Project Gutenbergで実在を確認した980冊）。本文の転載なし。'
original['version']=2
out=BASE/'forgeation-library-books-1000.json'
out.write_text(json.dumps(original,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Created {out}: {len(original["books"])} verified titles')
