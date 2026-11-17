"""Check that the shipped search index still reaches every page a term appears on.

The index is normalized after the build (`tools/mkdocs/search_trim.py`). A former
prefix cap dropped terms deep inside long sections while the pages still rendered.
The full-text baseline retains all measured pairs; any new loss now fails.

This compares the built pages against the built index and fails when that loss grows
past the recorded budget. Truth is the page's own `<article>`, which is exactly what
the index was generated from, so the comparison does not depend on Markdown syntax.
"""
from html.parser import HTMLParser
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'dist'
INDEX = SITE / 'search' / 'search_index.json'
TERMS = ('死锁', '缓存', '索引', '帧', '中断', '抖动', '调度', '页表', 'TLB', '采样', '缺页', '进程',
         '文件', '目录', '磁盘', '编码', '路由', 'TCP', '压缩', '加密', '吞吐量', '信号量', '子网',
         '存储器', '流水线', 'DMA', '图像', 'SPOOLing')
# Frozen 2026-11-17 corpus: the old cap lost 21/507 pairs; full text loses 0/507.
# Zero is the default for both global and per-term regressions.
LOST_BUDGET = 0.0
TERM_BUDGET = 0.0
BLOCK = ('p', 'div', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'pre', 'td', 'th', 'br')
# The index leaves out the breadcrumb nav and anything marked excluded, so the page
# text has to leave them out too or every page looks like it mentions 目录.
SKIP = ('script', 'style', 'nav')
VOID = frozenset('area base br col embed hr img input link meta param source track wbr'.split())


class Content(HTMLParser):
    """Text of the page's <article>, leaving out the header, nav and footer."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.stack = []
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if not self.depth:
            if tag == 'article':
                self.depth = 1
                self.stack.append((tag, False))
            return
        if tag in VOID:
            if tag in BLOCK:
                self.chunks.append(' ')
            return
        self.stack.append((tag, tag in SKIP or any(name == 'data-search-exclude' for name, _ in attrs)))
        if tag in BLOCK:
            self.chunks.append(' ')

    def handle_endtag(self, tag):
        if not self.depth:
            return
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break
        if tag == 'article':
            self.depth -= 1
        if tag in BLOCK:
            self.chunks.append(' ')

    def handle_data(self, data):
        if self.depth and not any(skip for _, skip in self.stack):
            self.chunks.append(data)


def page_text(path):
    parser = Content()
    parser.feed(path.read_text(encoding='utf-8'))
    return ' '.join(''.join(parser.chunks).split()).lower()


def evaluate(pages, indexed, terms=TERMS, lost_budget=LOST_BUDGET, term_budget=TERM_BUDGET):
    """Compare body truth to shipped index text; return evidence without side effects."""
    rows, errors, pairs, lost = [], [], 0, 0
    for term in terms:
        needle = term.lower()
        truth = {page for page, text in pages.items() if needle in text.lower()}
        kept = {page for page in truth if needle in indexed.get(page, '').lower()}
        missing = sorted(truth - kept)
        pairs += len(truth)
        lost += len(missing)
        rows.append((term, len(truth), len(kept), missing))
        if truth and len(missing) / len(truth) * 100 > term_budget:
            errors.append(f'{term}: {len(missing)} of {len(truth)} pages lost, over {term_budget:.0f}%')
    share = lost / pairs * 100 if pairs else 0
    if share > lost_budget:
        errors.append(f'{lost} of {pairs} term-page pairs lost ({share:.1f}%), over {lost_budget:.1f}%')
    return {'rows': rows, 'pairs': pairs, 'lost': lost, 'share': share, 'errors': errors}


def main():
    if not INDEX.is_file():
        print('Search coverage needs a build: run npm run build first')
        return 1
    data = json.loads(INDEX.read_text(encoding='utf-8'))
    sections = {}
    for doc in data.get('docs', []):
        sections.setdefault(doc.get('location', '').split('#')[0], []).append(doc.get('text', ''))
    indexed = {page: ' '.join(texts).lower() for page, texts in sections.items()}
    errors, pages = [], {}
    for page in indexed:
        path = SITE / page / 'index.html' if page else SITE / 'index.html'
        if not path.is_file():
            errors.append(f'{page or "/"}: indexed page has no built HTML at {path.relative_to(ROOT)}')
            continue
        pages[page] = page_text(path)
    result = evaluate(pages, indexed)
    errors.extend(result['errors'])
    for term, truth, kept, missing in result['rows']:
        if missing:
            print(f'  {term}: {kept}/{truth} pages, lost {", ".join(missing[:4])}'
                  + (' …' if len(missing) > 4 else ''))
    if errors:
        print('\n'.join(errors))
        return 1
    print(f'Search coverage passed: {len(TERMS)} terms, {result["pairs"]} term-page pairs, '
          f'{result["lost"]} lost ({result["share"]:.1f}%)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
