"""Remove search-index markup without discarding searchable section text.

A 1600-character prefix cap lost 21 of 507 term-page pairs in the frozen
2026-11-17 corpus. All 21 terms existed before trimming; none was a checker
false positive. Keep full plain text rather than sampling blocks: sampling can
silently discard a definition anywhere in a long section. The measured index-size
tradeoff is recorded by the E6 evaluation, not inferred from character counts.

SEARCH_TRIM_AUDIT_DIR optionally records the genuine pre-trim index for attribution.
Source pages, query behavior, titles, locations and other index fields are unchanged.
"""
import json
import os
import re
from pathlib import Path

TAG = re.compile(r'<[^>]+>')
TAGNAME = re.compile(r'</?([a-zA-Z][a-zA-Z0-9-]*)')
SPACE = re.compile(r'\s+')
INLINE = frozenset('a abbr b cite code del em i ins kbd mark q s samp small span strong sub sup u var wbr'.split())


def strip_tags(text):
    def replace(match):
        name = TAGNAME.match(match.group(0))
        return '' if name and name.group(1).lower() in INLINE else ' '
    return TAG.sub(replace, text)


def plain_of(text):
    return SPACE.sub(' ', strip_tags(text)).strip()


def trim(text):
    """Strip markup and redundant whitespace, never a section's textual tail."""
    return plain_of(text)


def on_post_build(config):
    path = Path(config['site_dir']) / 'search' / 'search_index.json'
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding='utf-8'))
    if audit_dir := os.environ.get('SEARCH_TRIM_AUDIT_DIR'):
        audit = Path(audit_dir)
        audit.mkdir(parents=True, exist_ok=True)
        (audit / 'untrimmed-index.json').write_text(
            json.dumps(data, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    for doc in data.get('docs', []):
        doc['text'] = trim(doc.get('text', ''))
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')),
                    encoding='utf-8')
