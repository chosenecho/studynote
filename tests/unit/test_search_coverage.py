"""Regression tripwires for body/index recall and excluded-page chrome."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    'search_coverage', Path(__file__).resolve().parents[2] / 'tools/checks/search_coverage.py')
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)


class CoverageTests(unittest.TestCase):
    def test_full_recall_passes(self):
        result = COVERAGE.evaluate({'a/': '定义 TCP 缺页'}, {'a/': '定义 tcp 缺页'}, ('TCP', '缺页'))
        self.assertEqual((result['pairs'], result['lost'], result['errors']), (2, 0, []))

    def test_single_loss_below_old_six_percent_budget_fails(self):
        pages = {f'{i}/': '缺页' for i in range(100)}
        indexed = dict(pages)
        indexed['99/'] = ''
        result = COVERAGE.evaluate(pages, indexed, ('缺页',))
        self.assertEqual(result['lost'], 1)
        self.assertEqual(len(result['errors']), 2)
        self.assertEqual(COVERAGE.LOST_BUDGET, 0)
        self.assertEqual(COVERAGE.TERM_BUDGET, 0)

    def test_missing_index_page_counts_as_loss(self):
        result = COVERAGE.evaluate({'a/': '尾部定义缺页'}, {}, ('缺页',))
        self.assertEqual(result['rows'][0][3], ['a/'])
        self.assertTrue(result['errors'])

    def test_term_absent_from_body_is_not_a_pair(self):
        result = COVERAGE.evaluate({'a/': '缓存'}, {'a/': '缓存'}, ('缺页',))
        self.assertEqual((result['pairs'], result['lost'], result['errors']), (0, 0, []))

    def test_chrome_and_excluded_content_are_not_body_truth(self):
        parser = COVERAGE.Content()
        parser.feed('<nav>目录</nav><article><h1>缓存</h1>'
                    '<nav>目录</nav><div data-search-exclude><p>缺页</p></div>'
                    '<script>加密</script><p>中<code>断</code></p></article><footer>TCP</footer>')
        text = ' '.join(''.join(parser.chunks).split())
        self.assertIn('缓存', text)
        self.assertIn('中断', text)
        for term in ('目录', '缺页', '加密', 'TCP'):
            self.assertNotIn(term, text)


if __name__ == '__main__':
    unittest.main()
