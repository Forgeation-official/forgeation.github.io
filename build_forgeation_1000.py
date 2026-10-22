#!/usr/bin/env python3
"""Incrementally build Forgeation's genuine-book metadata catalog from Gutendex.

Run repeatedly using the GitHub Actions workflow until 1000 records are saved.
Existing books, themes and 360-degree site files are preserved.
"""
import json
import pathlib
import time
import urllib.error
import urllib.request
import urllib.parse

BASE = pathlib.Path(__file__).resolve().parent
CATALOG = BASE / 'forgeation-library-books.json'
STATE = BASE / 'forgeation-library-progress.json'
TARGET = 1000
MAX_PAGES_PER_RUN = 12
FETCH_TIMEOUT = 15
MAX_ATTEMPTS = 3
SKIP_AFTER_FAILED_RUNS = 2  # 記録した上で取得不能ページを飛ばす（無限停止防止）
START_URL = 'https://gutendex.com/books/?languages=ja%2Cen&sort=popular'
HEADERS = {'User-Agent': 'ForgeationLibraryCatalogBuilder/4.0 (metadata only)',
           'Accept': 'application/json'}


def save_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def area_for(subjects, title):
    s = (' '.join(subjects) + ' ' + title).lower()
    groups = [
        (1, ('astronom', 'space', 'planet', 'physics', 'chemistry', 'science', 'biology')),
        (3, ('history', 'war ', 'geograph', 'travel', 'politic', 'econom')),
        (4, ('computer', 'mathematic', 'programming', 'engineering', 'technology')),
        (5, ('philosoph', 'religion', 'psycholog', 'ethic')),
        (6, ('children', 'juvenile', 'fairy', 'fable', 'picture book')),
        (7, ('art ', 'music', 'theater', 'theatre', 'film', 'cinema')),
        (8, ('medicine', 'medical', 'health', 'nursing', 'anatom')),
    ]
    for area, terms in groups:
        if any(term in s for term in terms):
            return area
    return 2


def fetch(url):
    for attempt in range(MAX_ATTEMPTS):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT) as response:
                data = json.load(response)
                if not isinstance(data, dict) or not isinstance(data.get('results'), list):
                    raise ValueError('Unexpected Gutendex response')
                return data
        except (OSError, ValueError, urllib.error.URLError) as error:
            print(f'Fetch attempt {attempt + 1}/{MAX_ATTEMPTS} failed: {error}', flush=True)
            if attempt + 1 < MAX_ATTEMPTS:
                time.sleep((2, 5)[attempt])
    return None


def next_page_url(url):
    """同じ検索条件のまま page を1つ進める。失敗ページの救済策。"""
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname not in ('gutendex.com', 'www.gutendex.com'):
        raise ValueError('Unexpected catalog host; refusing to change cursor')
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    try:
        page = int(params.get('page', ['1'])[0])
    except (ValueError, TypeError):
        page = 1
    params['page'] = [str(page + 1)]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                                   urllib.parse.urlencode(params, doseq=True), parsed.fragment))


# Open Library search is a secondary source for bibliographic metadata only.
# It does not authorize displaying copyrighted book text or cover images.
OL_QUERIES = [
    'subject:fiction', 'subject:history', 'subject:science',
    'subject:juvenile_fiction', 'subject:philosophy', 'subject:poetry',
    'subject:biography', 'subject:mathematics', 'subject:art',
    'subject:technology', 'subject:travel', 'subject:music',
]
OL_PAGE_SIZE = 50
OL_MAX_PAGES_PER_RUN = 5


def fetch_openlibrary(url):
    for attempt in range(2):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=18) as response:
                data = json.load(response)
            if not isinstance(data, dict) or not isinstance(data.get('docs'), list):
                raise ValueError('Unexpected Open Library response')
            return data
        except (OSError, ValueError, urllib.error.URLError) as error:
            print(f'Open Library attempt {attempt + 1}/2 failed: {error}', flush=True)
            if attempt == 0:
                time.sleep(2)
    return None


def collect_openlibrary(books, seen, state):
    """Incremental fallback; preserves existing entries and distinct progress."""
    query_index = int(state.get('ol_query_index') or 0)
    page = max(1, int(state.get('ol_page') or 1))
    fetched = 0
    added = 0
    while len(books) < TARGET and fetched < OL_MAX_PAGES_PER_RUN and query_index < len(OL_QUERIES):
        query = OL_QUERIES[query_index]
        params = urllib.parse.urlencode({
            'q': query, 'page': page, 'limit': OL_PAGE_SIZE,
            'fields': 'key,title,author_name,subject,language,first_publish_year',
        })
        url = 'https://openlibrary.org/search.json?' + params
        data = fetch_openlibrary(url)
        if data is None:
            print('Open Library unavailable; preserving fallback cursor.', flush=True)
            break
        docs = data['docs']
        for item in docs:
            if len(books) >= TARGET:
                break
            title = str(item.get('title') or '').strip()
            authors = item.get('author_name') or []
            author = ', '.join(str(a) for a in authors[:3]).strip() or '著者情報なし'
            key = (title.casefold(), author.casefold())
            work_key = str(item.get('key') or '')
            if not title or key in seen or not work_key.startswith('/works/'):
                continue
            seen.add(key)
            subjects = item.get('subject') or []
            languages = item.get('language') or []
            work_url = 'https://openlibrary.org' + work_key
            books.append({
                'id': 'ol:' + work_key.split('/')[-1],
                'title': title, 'author': author,
                'area': area_for(subjects, title),
                'genre': ' / '.join(str(x) for x in subjects[:2]) if subjects else 'Open Library',
                'desc': 'Open Libraryの書誌情報。館内に本文は収録していません。',
                'availability': 'external_bibliography',
                'fullTextIncluded': False,
                'searchUrl': work_url,
                'source': 'Open Library',
                'sourceId': work_key,
                'languages': languages,
                'chapters': [
                    {'title': '書誌情報（本文ではありません）',
                     'text': f'書名：{title}\n著者：{author}\n提供元：Open Library\n※館内には本文を収録していません。'},
                    {'title': '作品情報を見る',
                     'text': f'書誌情報と利用可能な閲覧形式は作品ページで確認してください。\n{work_url}'}
                ],
            })
            added += 1
        fetched += 1
        if len(docs) < OL_PAGE_SIZE or page * OL_PAGE_SIZE >= int(data.get('numFound') or data.get('num_found') or 0):
            query_index += 1
            page = 1
        else:
            page += 1
        print(f'Open Library pages: {fetched}; added: {added}; total: {len(books)}', flush=True)
        time.sleep(1)
    state['ol_query_index'] = query_index
    state['ol_page'] = page
    return added



# Verified/common Japanese publication titles or established Japanese names.
# Unknown works keep their original title: never fabricate an official Japanese title.
JAPANESE_TITLES = {
    'the wonderful wizard of oz': 'オズの魔法使い',
    "grimms' fairy tales": 'グリム童話',
    'the secret of chimneys': 'チムニーズ館の秘密',
    'beowulf: an anglo-saxon epic poem': 'ベーオウルフ',
    'beowulf': 'ベーオウルフ',
    'the mysteries of udolpho': 'ユードルフォの謎',
    'great expectations': '大いなる遺産',
    'pride and prejudice': '高慢と偏見',
    'alice’s adventures in wonderland': '不思議の国のアリス',
    "alice's adventures in wonderland": '不思議の国のアリス',
    'through the looking-glass': '鏡の国のアリス',
    'the adventures of sherlock holmes': 'シャーロック・ホームズの冒険',
    'the memoirs of sherlock holmes': 'シャーロック・ホームズの回想',
    'the hound of the baskervilles': 'バスカヴィル家の犬',
    'a study in scarlet': '緋色の研究',
    'the sign of the four': '四つの署名',
    'the war of the worlds': '宇宙戦争',
    'the time machine': 'タイム・マシン',
    'the invisible man': '透明人間',
    'the island of doctor moreau': 'モロー博士の島',
    'the picture of dorian gray': 'ドリアン・グレイの肖像',
    'the importance of being earnest': '真面目が肝心',
    'dracula': 'ドラキュラ',
    'frankenstein; or, the modern prometheus': 'フランケンシュタイン',
    'frankenstein': 'フランケンシュタイン',
    'moby dick; or, the whale': '白鯨',
    'moby dick': '白鯨',
    'little women': '若草物語',
    'the secret garden': '秘密の花園',
    'a little princess': '小公女',
    'anne of green gables': '赤毛のアン',
    'the adventures of tom sawyer': 'トム・ソーヤーの冒険',
    'adventures of huckleberry finn': 'ハックルベリー・フィンの冒険',
    'the prince and the pauper': '王子と乞食',
    'treasure island': '宝島',
    'the strange case of dr. jekyll and mr. hyde': 'ジキル博士とハイド氏',
    'strange case of dr jekyll and mr hyde': 'ジキル博士とハイド氏',
    'the call of the wild': '野性の呼び声',
    'white fang': '白い牙',
    'the jungle book': 'ジャングル・ブック',
    'the happy prince and other tales': '幸福な王子',
    'the happy prince': '幸福な王子',
    'the count of monte cristo': 'モンテ・クリスト伯',
    'the three musketeers': '三銃士',
    'les misérables': 'レ・ミゼラブル',
    'the phantom of the opera': 'オペラ座の怪人',
    'the scarlet letter': '緋文字',
    'the great gatsby': 'グレート・ギャツビー',
    'the metamorphosis': '変身',
    'the trial': '審判',
    'the castle': '城',
    'the brothers karamazov': 'カラマーゾフの兄弟',
    'crime and punishment': '罪と罰',
    'the idiot': '白痴',
    'war and peace': '戦争と平和',
    'anna karenina': 'アンナ・カレーニナ',
    'the death of ivan ilyich': 'イワン・イリイチの死',
    'the art of war': '孫子',
    'the republic': '国家',
    'the prince': '君主論',
    'the origin of species': '種の起源',
    'a christmas carol': 'クリスマス・キャロル',
    'oliver twist': 'オリバー・ツイスト',
    'david copperfield': 'デイヴィッド・コパフィールド',
    'a tale of two cities': '二都物語',
    'the old man and the sea': '老人と海',
    'the odyssey': 'オデュッセイア',
    'the iliad': 'イリアス',
    'the divine comedy': '神曲',
    'the adventures of pinocchio': 'ピノッキオの冒険',
    'peter pan': 'ピーター・パン',
    'the wonderful adventures of nils': 'ニルスのふしぎな旅',
    'the wind in the willows': 'たのしい川べ',
    'the wizard of oz': 'オズの魔法使い',
    'the yellow wallpaper': '黄色い壁紙',
    'the turn of the screw': 'ねじの回転',
    'the woman in white': '白衣の女',
    'the moonstone': '月長石',
    'the last of the mohicans': 'モヒカン族の最後',
    'the legend of sleepy hollow': 'スリーピー・ホロウの伝説',
    'the tale of peter rabbit': 'ピーターラビットのおはなし',
    'the railway children': '鉄道きょうだい',
    'the red badge of courage': '赤い武功章',
    'the awakening': '目覚め',
    'the house of the seven gables': '七破風の屋敷',
    'the adventures of robin hood': 'ロビン・フッドの冒険',
}


def japanese_display(book):
    """Retain source title, and add a reliable Japanese display field when known."""
    original = str(book.get('titleOriginal') or book.get('title') or '').strip()
    if not original:
        return False
    key = ' '.join(original.casefold().replace('’', "'").split())
    japanese = JAPANESE_TITLES.get(key)
    if not japanese:
        # Match subtitle variants only for distinctive titles, never generic titles.
        for candidate in ('beowulf:', 'frankenstein;', 'moby dick;',
                          'the wonderful wizard of oz:', 'the mysteries of udolpho:'):
            if key.startswith(candidate):
                japanese = JAPANESE_TITLES.get(candidate[:-1])
                break
    if japanese:
        book['titleOriginal'] = original
        book['titleJa'] = japanese
        book['titleJaStatus'] = 'established'
        # Existing library renders `title` on the spine; preserve source in titleOriginal.
        book['title'] = japanese
        return True
    if book.get('titleJaStatus') == 'established':
        return False
    # No invented translation: unknown originals remain visible until verified.
    book['titleOriginal'] = original
    book['titleJaStatus'] = 'unverified'
    return False


def main():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    books = catalog['books']
    if not isinstance(books, list):
        raise ValueError('Catalog books must be a list')
    seen = {(str(b.get('titleOriginal') or b.get('title', '')).casefold().strip(),
             str(b.get('author', '')).casefold().strip()) for b in books}
    # The workflow may commit only the catalog JSON, not the separate state file.
    # Keep progress in the catalog itself so it survives each GitHub Actions run.
    embedded = catalog.get('collectionProgress') or {}
    disk_state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    state = dict(disk_state)
    state.update(embedded)  # committed catalog is the authoritative cursor
    if len(books) >= 653 and 'ol_page' not in state:
        # Migration from the original fallback: pages 1-5 already collected.
        state['ol_query_index'] = 0
        state['ol_page'] = 6
        print('Migrated Open Library cursor to page 6 (653-book catalog).', flush=True)
    url = state.get('next_url') or START_URL
    pages = 0
    failed_url = state.get('failed_url')
    failed_runs = int(state.get('failed_runs') or 0)
    skipped_pages = state.get('skipped_pages') or []
    if not isinstance(skipped_pages, list):
        skipped_pages = []
    print(f'Start: {len(books)}/{TARGET} books; cursor: {url}', flush=True)

    while url and len(books) < TARGET and pages < MAX_PAGES_PER_RUN:
        data = fetch(url)
        if data is None:
            failed_runs = failed_runs + 1 if failed_url == url else 1
            failed_url = url
            if failed_runs >= SKIP_AFTER_FAILED_RUNS:
                # 2回の実行で同じページを取得できなければ、欠番を明示して前進する。
                # 他のページが取得できる場合だけ有効。通信障害全体の解決ではない。
                print(f'WARNING: page unavailable for {failed_runs} runs; skipping: {url}', flush=True)
                if url not in skipped_pages:
                    skipped_pages.append(url)
                url = next_page_url(url)
                failed_url = None
                failed_runs = 0
            else:
                print('Network timeout: keeping cursor for retry on next run.', flush=True)
            break
        failed_url = None
        failed_runs = 0
        for item in data['results']:
            if len(books) >= TARGET:
                break
            title = str(item.get('title') or '').strip()
            authors = item.get('authors') or []
            author = ', '.join(str(a.get('name') or '') for a in authors).strip() or '著者情報なし'
            key = (title.casefold(), author.casefold())
            if not title or key in seen or not isinstance(item.get('id'), int):
                continue
            seen.add(key)
            gid = item['id']
            subjects = item.get('subjects') or []
            languages = item.get('languages') or []
            gutenberg_url = f'https://www.gutenberg.org/ebooks/{gid}'
            books.append({
                'id': 100000 + gid,
                'title': title,
                'author': author,
                'area': area_for(subjects, title),
                'genre': ' / '.join(subjects[:2]) if subjects else 'Project Gutenberg',
                'desc': f'Project Gutenbergの実在書籍（ID: {gid}）。館内に本文は収録していません。',
                'availability': 'external_public_domain',
                'fullTextIncluded': False,
                'searchUrl': gutenberg_url,
                'source': 'Project Gutenberg',
                'sourceId': gid,
                'languages': languages,
                'chapters': [
                    {'title': '書誌情報（本文ではありません）',
                     'text': f'書名：{title}\n著者：{author}\n提供元：Project Gutenberg\n作品番号：{gid}\n言語：{", ".join(languages)}\n※館内には本文を収録していません。'},
                    {'title': '正規の書籍を読む',
                     'text': f'閲覧形式と利用条件は作品ページで確認してください。\n{gutenberg_url}\n※国・地域により著作権の扱いが異なります。'}
                ]
            })
        pages += 1
        url = data.get('next')
        print(f'Fetched page this run {pages}; total books: {len(books)}', flush=True)

    # Use Open Library if Gutendex is unavailable or yielded too few records.
    # Source cursor is retained so either source can resume independently.
    fallback_state = dict(state)
    if len(books) < TARGET:
        added = collect_openlibrary(books, seen, fallback_state)
        print(f'Fallback added {added} bibliographic records.', flush=True)

    # Localize existing AND newly fetched entries on every run.
    localized = sum(bool(japanese_display(book)) for book in books)
    print(f'Japanese spine titles: {localized}/{len(books)}; unknown originals retained.', flush=True)

    # Save BOTH catalog and cursor. GitHub Actions commits them together.
    catalog['books'] = books[:TARGET]
    catalog['description'] = f'実在書籍の書誌データ {len(catalog["books"])}件。本文の転載なし。'
    catalog['version'] = 3
    catalog['titleDisplayPolicy'] = 'Japanese established titles where verified; original title otherwise'
    fallback_state.update({'next_url': url if len(books) < TARGET else None,
                           'count': len(catalog['books']), 'target': TARGET,
                           'failed_url': failed_url, 'failed_runs': failed_runs,
                           'skipped_pages': skipped_pages})
    catalog['collectionProgress'] = fallback_state
    save_json(CATALOG, catalog)
    save_json(STATE, fallback_state)
    print(f'Saved {len(catalog["books"])}/{TARGET} books.', flush=True)
    if skipped_pages:
        print(f'WARNING: {len(skipped_pages)} page(s) skipped due to repeated timeouts.', flush=True)
    if len(catalog['books']) == TARGET:
        print('COMPLETE: 1000 real bibliographic records saved.', flush=True)
    elif not url and fallback_state['ol_query_index'] >= len(OL_QUERIES):
        print('Sources exhausted before 1000. Review source queries.', flush=True)
    else:
        print('PARTIAL: run this workflow again to continue.', flush=True)


if __name__ == '__main__':
    main()
