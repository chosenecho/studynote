"""Trim the search index so the site serves it quickly.

Material indexes the markup of every page, so the raw index carries the HTML as well
as the text. The index is fetched the first time a reader opens search, which makes it
the single largest transfer on the site.

Stripping the tags is the real cut. Capping each entry at 1600 characters then trims
the tail of long sections: 682 entries, 372,701 characters of text left, 1.0 MB of JSON
and 275 KB after Brotli. The cap costs about 4% of term-page pairs — a term that
appears only deep inside a long exam page stops reaching it — so the number is a
measured trade, not a free win; `tools/checks/search_coverage.py` fails the build when
that loss grows.

The index is rebuilt on every run; this hook only rewrites the finished artifact, so
`mkdocs serve` and the source pages are untouched.
"""
import json
import re
from pathlib import Path

TAG = re.compile(r'<[^>]+>')
TAGNAME = re.compile(r'</?([a-zA-Z][a-zA-Z0-9-]*)')
SPACE = re.compile(r'\s+')
LIMIT = 1600
# Inline tags sit inside a word (`中<code>断</code>`), so dropping them without a
# replacement keeps the word whole. Block tags separate words, so they still need a
# space — removing those outright would weld the last word of one paragraph to the
# first word of the next and hide both from the tokenizer.
INLINE = frozenset('a abbr b cite code del em i ins kbd mark q s samp small span strong sub sup u var wbr'.split())


def strip_tags(text):
    def replace(match):
        name = TAGNAME.match(match.group(0))
        return '' if name and name.group(1).lower() in INLINE else ' '
    return TAG.sub(replace, text)


def trim(text):
    plain = SPACE.sub(' ', strip_tags(text)).strip()
    if len(plain) <= LIMIT:
        return plain
    cut = plain[:LIMIT]
    space = cut.rfind(' ')
    if space > LIMIT * 0.7:
        cut = cut[:space]
    return cut


def on_post_build(config):
    path = Path(config['site_dir']) / 'search' / 'search_index.json'
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding='utf-8'))
    for doc in data.get('docs', []):
        doc['text'] = trim(doc.get('text', ''))
    path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
