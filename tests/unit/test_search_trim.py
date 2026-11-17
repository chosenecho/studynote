"""Regressions for the search-index trim at its pure-function seam.

The fixtures are synthetic markup shaped like the built index — a heading, a list of
short exam points, one long block — not copies of the course pages.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'tools/mkdocs/search_trim.py'


def load_module():
    spec = importlib.util.spec_from_file_location('search_trim', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TRIM = load_module()


def entry(blocks, tail=''):
    """Built-index markup: a heading, then one list item per point."""
    items = ''.join(f'<li><p>{text}。</p></li>' for text in blocks)
    return f'<h2 id="_1">第 1 节</h2><ol>{items}</ol><p>{tail}</p>'


class StripTagsTests(unittest.TestCase):
    def test_inline_tags_do_not_split_a_word(self):
        self.assertEqual(TRIM.plain_of('<p>中<code>断</code>处理</p>'), '中断处理')

    def test_block_tags_keep_words_apart(self):
        self.assertEqual(TRIM.plain_of('<p>缓存</p><p>命中</p>'), '缓存 命中')

    def test_whitespace_collapses(self):
        self.assertEqual(TRIM.plain_of('<p>a\n\n  b\tc</p>'), 'a b c')


class TrimTests(unittest.TestCase):
    def test_short_entry_is_kept_whole(self):
        text = entry(['短句一', '短句二'])
        self.assertEqual(TRIM.trim(text), TRIM.plain_of(text))

    def test_long_entry_keeps_every_point(self):
        blocks = [f'第 {index} 个考点的正文内容' * 12 for index in range(40)]
        trimmed = TRIM.trim(entry(blocks))
        for index in range(40):
            self.assertIn(f'第 {index} 个考点', trimmed)

    def test_term_in_the_tail_of_a_long_entry_survives(self):
        blocks = [f'第 {index} 个考点的正文内容' * 12 for index in range(40)]
        blocks.append('末考点讲的是缺页故障的断点位置')
        self.assertIn('缺页', TRIM.trim(entry(blocks)))

    def test_term_in_the_tail_of_a_long_block_survives(self):
        filler = '这一句只是填充正文，用来把关键词推到块的末尾。' * 12
        blocks = [f'第 {index} 个考点的正文内容' * 12 for index in range(40)]
        blocks.append(filler + '最后一句解释缺页中断。')
        self.assertIn('缺页', TRIM.trim(entry(blocks)))

    def test_trim_is_stable_on_its_own_output(self):
        # The hook runs once per build on the raw index. Running it on an entry it
        # already produced must keep that entry, not shrink it again.
        text = entry([f'第 {index} 个考点的正文内容' * 12 for index in range(40)])
        once = TRIM.trim(text)
        self.assertEqual(TRIM.trim(once), once)

    def test_entry_text_is_never_longer_than_its_plain_text(self):
        text = entry([f'第 {index} 个考点的正文内容' * 12 for index in range(40)])
        self.assertLessEqual(len(TRIM.trim(text)), len(TRIM.plain_of(text)))


if __name__ == '__main__':
    unittest.main()
