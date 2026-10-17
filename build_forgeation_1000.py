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
HEADERS = {'User-Agent': 'ForgeationLibraryCatalogBuilder/3.0 (metadata only)',
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


def main():
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))
    books = catalog['books']
    if not isinstance(books, list):
        raise ValueError('Catalog books must be a list')
    seen = {(str(b.get('title', '')).casefold().strip(),
             str(b.get('author', '')).casefold().strip()) for b in books}
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
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

    # Save BOTH catalog and cursor. GitHub Actions commits them together.
    catalog['books'] = books[:TARGET]
    catalog['description'] = f'実在書籍の書誌データ {len(catalog["books"])}件。本文の転載なし。'
    catalog['version'] = 2
    save_json(CATALOG, catalog)
    save_json(STATE, {'next_url': url if len(books) < TARGET else None,
                      'count': len(catalog['books']), 'target': TARGET,
                      'failed_url': failed_url, 'failed_runs': failed_runs,
                      'skipped_pages': skipped_pages})
    print(f'Saved {len(catalog["books"])}/{TARGET} books.', flush=True)
    if skipped_pages:
        print(f'WARNING: {len(skipped_pages)} page(s) skipped due to repeated timeouts.', flush=True)
    if len(catalog['books']) == TARGET:
        print('COMPLETE: 1000 real bibliographic records saved.', flush=True)
    elif not url:
        print('Source exhausted before 1000. Review language filters.', flush=True)
    else:
        print('PARTIAL: run this workflow again to continue.', flush=True)


if __name__ == '__main__':
    main()
