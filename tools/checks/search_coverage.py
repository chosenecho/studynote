"""Check that the shipped search index still reaches every page a term appears on.

The index is trimmed after the build (`tools/mkdocs/search_trim.py`): each entry keeps
its opening characters, so a term that only appears deeper in a long section drops out
of search. Nothing else notices — the build stays green and the page still renders.

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
# Measured 2026-11-16 on the 1600-character cap: 21 of 504 term-page pairs lost (4.2%),
# the worst single term losing 3 of 11. The budget is the tripwire, not the target.
LOST_BUDGET = 6.0
TERM_BUDGET = 40.0
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


if not INDEX.is_file():
    sys.exit('Search coverage needs a build: run npm run build first')

data = json.loads(INDEX.read_text(encoding='utf-8'))
sections = {}
for doc in data.get('docs', []):
    sections.setdefault(doc.get('location', '').split('#')[0], []).append(doc.get('text', ''))
indexed = {page: ' '.join(texts).lower() for page, texts in sections.items()}

errors = []
pages = {}
for page in indexed:
    path = SITE / page / 'index.html' if page else SITE / 'index.html'
    if not path.is_file():
        errors.append(f'{page or "/"}: indexed page has no built HTML at {path.relative_to(ROOT)}')
        continue
    pages[page] = page_text(path)

rows, pairs, lost = [], 0, 0
for term in TERMS:
    needle = term.lower()
    truth = {page for page, text in pages.items() if needle in text}
    kept = {page for page in truth if needle in indexed[page]}
    missing = truth - kept
    pairs += len(truth)
    lost += len(missing)
    rows.append((term, len(truth), len(kept), sorted(missing)))
    if truth and len(missing) / len(truth) * 100 > TERM_BUDGET:
        errors.append(f'{term}: {len(missing)} of {len(truth)} pages lost, over {TERM_BUDGET:.0f}%')

for term, truth, kept, missing in rows:
    if missing:
        print(f'  {term}: {kept}/{truth} pages, lost {", ".join(missing[:4])}'
              + (' …' if len(missing) > 4 else ''))

share = lost / pairs * 100 if pairs else 0
if share > LOST_BUDGET:
    errors.append(f'{lost} of {pairs} term-page pairs lost ({share:.1f}%), over {LOST_BUDGET:.1f}%')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'Search coverage passed: {len(TERMS)} terms, {pairs} term-page pairs, '
      f'{lost} lost ({share:.1f}%)')
