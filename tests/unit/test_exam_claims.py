"""E5 regressions at the existing pure-audit and temporary-directory CLI seams.

All question/paper identifiers below are synthetic fixtures, not real evidence.
The checker validates presence/shape, not ID authenticity or statistical truth.
"""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'tools/checks/exam_claims.py'
ANCHOR = '<!-- 真题: FIXTURE-Q1 -->'
SCOPE = '<!-- 真题范围: 年份=2020-2025; 试卷=FIXTURE-A/B; 样本量=12 -->'
EVIDENCE = ANCHOR + SCOPE


def load_module():
    spec = importlib.util.spec_from_file_location('exam_claims_gate', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExamClaimsCliTests(unittest.TestCase):
    def run_checker(self, text, *args):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'tools/checks/exam_claims.py'
            script.parent.mkdir(parents=True)
            shutil.copyfile(MODULE, script)
            page = root / 'docs/courses/sample/exam/01.md'
            page.parent.mkdir(parents=True)
            page.write_text(text, encoding='utf-8')
            return subprocess.run([sys.executable, '-X', 'utf8', str(script), *args],
                                  capture_output=True, text=True, encoding='utf-8')

    def audit(self, text):
        return load_module().check_lines(text.splitlines(), 'fixture.md')

    def assert_counts(self, result, checked, guarded, warnings):
        self.assertEqual(checked, result['checked'])
        self.assertEqual(guarded, result['guarded'])
        self.assertEqual(warnings, len(result['warnings']))

    # Preserve the previous round's eleven behavioral regressions, with the new
    # scope requirement in cases that formerly accepted a question anchor alone.
    def test_common_exam_column_body_is_an_unguarded_claim(self):
        result = self.audit('| 术语 | 常考 |\n| --- | --- |\n| 网络 | 简答 |')
        self.assert_counts(result, 1, 0, 1)
        self.assertIn('fixture.md:3: 常考', result['warnings'][0])

    def test_header_claim_applies_to_body_rows_without_the_keyword(self):
        result = self.audit('| 术语 | 必背一句话 | 常考 |\n| --- | --- | --- |\n'
                            '| 缓存 | 命中率越高越好 | 填空 |')
        self.assert_counts(result, 1, 0, 1)
        self.assertIn('fixture.md:3: 常考', result['warnings'][0])

    def test_row_evidence_covers_its_own_inherited_claim(self):
        result = self.audit('| 术语 | 常考 |\n| --- | --- |\n'
                            f'| 缓存 | 填空 {EVIDENCE} |')
        self.assert_counts(result, 1, 1, 0)

    def test_neighbouring_row_evidence_does_not_shield_other_rows(self):
        result = self.audit('| 术语 | 常考 |\n| --- | --- |\n'
                            '| 甲 | 填空 |\n'
                            f'| 乙 | 填空 {EVIDENCE} |\n'
                            '| 丙 | 填空 |')
        self.assert_counts(result, 3, 1, 2)
        self.assertTrue(result['warnings'][0].startswith('fixture.md:3:'))
        self.assertTrue(result['warnings'][1].startswith('fixture.md:5:'))

    def test_technical_table_and_false_friends_are_not_claims(self):
        result = self.audit('| 参数 | 说明 |\n| --- | --- |\n'
                            '| 带宽 | 最高频率与最低频率之差，单位 Hz |\n'
                            '| 采样频率 | 不应低于信号最高频率的两倍 |\n'
                            '| 分组长度 | 以太网采用 1518 字节上限 |\n'
                            '| 滤波器 | 高频带、高频电路、高频信号与甚高频 |\n'
                            '| 编码 | 提高频带利用率 |')
        self.assert_counts(result, 0, 0, 0)

    def test_prose_claim_keeps_nearby_comment_convention(self):
        self.assert_counts(self.audit('近年来常考，务必掌握。'), 1, 0, 1)
        self.assert_counts(self.audit('近年来常考，务必掌握。\n' + ANCHOR + '\n' + SCOPE),
                           1, 1, 0)

    def test_import_has_no_io_or_exit_side_effects(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('read on import')), \
                patch.object(Path, 'glob', side_effect=AssertionError('glob on import')), \
                patch('builtins.print') as output:
            module = load_module()
        self.assertTrue(callable(module.main))
        self.assertTrue(callable(module.check_lines))
        output.assert_not_called()

    def test_empty_anchor_is_not_evidence(self):
        for anchor in ('<!-- 真题: -->', '<!-- 真题：   -->', '<!-- exam: -->',
                       '<!-- 真题: FIXTURE-Q1', '<!-- 真题: \n -->'):
            with self.subTest(anchor=anchor):
                self.assert_counts(self.audit('常考。' + anchor + SCOPE), 1, 0, 1)

    def test_table_semantics_reset_at_next_table_and_code_blocks_are_skipped(self):
        result = self.audit(
            '术语 | **常考**\n:--- | ---:\n网络 | 简答\n\n'
            '| 参数 | 说明 |\n| --- | --- |\n| 带宽 | 最高频率与最低频率之差 |\n\n'
            '```markdown\n| 术语 | 常考 |\n| --- | --- |\n| 示例 | 简答 |\n```\n'
            '~~~markdown\n每年必考\n~~~\n    每年必考')
        self.assert_counts(result, 1, 0, 1)

    def test_pure_audit_reports_fixed_line_numbers_without_mutation(self):
        module = load_module()
        lines = ['| 术语 | 常考 |', '| --- | --- |', '| 网络 | 简答 |']
        before = list(lines)
        with patch.object(Path, 'read_text', side_effect=AssertionError('audit I/O')):
            result = module.check_lines(lines, 'fixture.md')
        self.assertEqual(before, lines)
        self.assert_counts(result, 1, 0, 1)
        self.assertTrue(result['warnings'][0].startswith('fixture.md:3: 常考 → needs '))
        self.assertTrue(result['warnings'][0].endswith(' | | 网络 | 简答 |'))

    def test_strict_fails_while_default_only_warns(self):
        text = '| 术语 | 常考 |\n| --- | --- |\n| 网络 | 简答 |\n'
        for args, expected in (((), 0), (('--strict',), 1)):
            result = self.run_checker(text, *args)
            self.assertEqual(expected, result.returncode, result.stderr)
            self.assertIn('warn docs/courses/sample/exam/01.md:3: 常考', result.stdout)

    # E5: no exemption for old 常考 headers; only explicit suggestions are advice.
    def test_explicit_question_type_advice_is_not_frequency(self):
        for heading in ('题型建议', '建议题型'):
            result = self.audit(f'| 术语 | {heading} |\n| --- | --- |\n| 网络 | 简答、简单应用 |')
            self.assert_counts(result, 0, 0, 0)
            self.assertEqual([{'line': 3, 'kind': 'advice'}], result['classifications'])
        self.assert_counts(self.audit('建议按简答题型练习，重点掌握定义。'), 0, 0, 0)

    def test_advice_label_never_overrides_real_frequency_language(self):
        for text in ('题型建议：近年来常考简答。',
                     '| 术语 | 题型建议 |\n| --- | --- |\n| 网络 | 每年必考 |',
                     '| 术语 | 常考（题型建议） |\n| --- | --- |\n| 网络 | 简答 |'):
            self.assert_counts(self.audit(text), 1, 0, 1)

    def test_other_statistics_and_technical_usage_are_not_exam_frequency(self):
        result = self.audit('近年来网络用户增长，每年增加约 10%。\n'
                            '缓存命中率为 80%，统计样本量为 100。\n'
                            '最高频率为 20kHz，高频电路处理高频信号。')
        self.assert_counts(result, 0, 0, 0)
        self.assertEqual(['statistic'] * 3, [r['kind'] for r in result['classifications']])

    def test_real_frequency_variants_are_not_missed(self):
        for text in ('近五年考了3次。', '历年出现率为 80%。', '本章每年都考。',
                     '该考点连续三年出现。', '真题中出现了3次。', '此题从未考过。',
                     '考试频率很高。', '常考简答题。', '这道题是高频考点。',
                     '该知识点反复考查。', '每次考试都会涉及。'):
            with self.subTest(text=text):
                self.assert_counts(self.audit(text), 1, 0, 1)

    def test_anchor_alone_does_not_supply_scope(self):
        result = self.audit('近年每年都考。' + ANCHOR)
        self.assert_counts(result, 1, 0, 1)
        self.assertIn('needs a statistical scope', result['warnings'][0])
        self.assertTrue(result['classifications'][0]['anchor'])
        self.assertFalse(result['classifications'][0]['scope'])

    def test_scope_alone_is_not_a_question_anchor(self):
        result = self.audit('常考。' + SCOPE)
        self.assert_counts(result, 1, 0, 1)
        self.assertIn('needs <!-- 真题: ID -->', result['warnings'][0])
        self.assertNotIn('a statistical scope', result['warnings'][0])

    def test_inline_complete_evidence_is_guarded(self):
        self.assert_counts(self.audit('常考。' + EVIDENCE), 1, 1, 0)
        self.assert_counts(self.audit('常考。<!-- exam: SYNTHETIC-NOT-A-REAL-ID -->' + SCOPE),
                           1, 1, 0)

    def test_scope_requires_three_fields_and_valid_values(self):
        broken = (
            '', '<!-- 真题范围: -->', '<!-- 真题范围: 有统计 -->',
            '<!-- 真题范围: 年份=2020-2025; 样本量=12 -->',
            '<!-- 真题范围: 试卷=FIXTURE-A/B; 样本量=12 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=FIXTURE-A/B -->',
            '<!-- 真题范围: 年份=近五年; 试卷=FIXTURE-A/B; 样本量=12 -->',
            '<!-- 真题范围: 年份=2025-2020; 试卷=FIXTURE-A/B; 样本量=12 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=; 样本量=12 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=...; 样本量=12 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=见上文; 样本量=12 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=FIXTURE; 样本量=若干 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=FIXTURE; 样本量=0 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=FIXTURE; 样本量=-1 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=FIXTURE; 样本量=1.5 -->',
            '<!-- 真题范围: 年份=2020-2025; 试卷=FIXTURE; 样本量=1; 样本量=2 -->',
        )
        for scope in broken:
            with self.subTest(scope=scope):
                result = self.audit('常考。' + ANCHOR + scope)
                self.assert_counts(result, 1, 0, 1)
                self.assertIn('a statistical scope', result['warnings'][0])

    def test_scope_accepts_single_year_unicode_delimiters_and_positive_sample(self):
        for scope in ('<!-- 真题范围：年份＝2024；试卷＝FIXTURE；样本量＝1 -->',
                      '<!-- 真题范围: 样本量=12; 试卷=FIXTURE; 年份=2020至2025 -->'):
            with self.subTest(scope=scope):
                self.assert_counts(self.audit('常考。' + ANCHOR + scope), 1, 1, 0)

    def test_separate_partial_scopes_cannot_be_merged(self):
        result = self.audit('常考。' + ANCHOR +
                            '<!-- 真题范围: 年份=2020-2025 -->' +
                            '<!-- 真题范围: 试卷=FIXTURE; 样本量=12 -->')
        self.assert_counts(result, 1, 0, 1)

    def test_scope_and_anchor_cannot_be_borrowed_from_adjacent_row_or_header(self):
        for first, second in ((ANCHOR, SCOPE), (EVIDENCE, ''), ('', EVIDENCE)):
            result = self.audit('| 术语 | 常考 |\n| --- | --- |\n'
                                f'| 甲 | 简答 {first} |\n| 乙 | 简答 {second} |')
            self.assertEqual(2, result['checked'])
            self.assertEqual(1 if EVIDENCE in (first, second) else 0, result['guarded'])
        result = self.audit(f'| 术语 | 常考 {EVIDENCE} |\n| --- | --- |\n| 网络 | 简答 |')
        self.assert_counts(result, 1, 0, 1)

    def test_prose_window_does_not_cross_other_claim_or_table_or_code(self):
        for boundary in ('常考。', '| 参数 | 值 |', '```markdown', '# 下一节', '普通段落。'):
            result = self.audit('每年都考。\n' + boundary + '\n' + EVIDENCE)
            self.assertTrue(result['warnings'][0].startswith('fixture.md:1:'))
            self.assertFalse(result['classifications'][0]['anchor'])
        self.assert_counts(self.audit('常考。\n\n\n\n' + EVIDENCE), 1, 0, 1)

    def test_historical_and_deferred_comments_never_exempt_claims(self):
        for label in ('历史声称: 2023 版遗留', '暂缓: 等原卷', '待回填: 等人工核对'):
            result = self.audit(f'常考。<!-- {label} -->')
            self.assert_counts(result, 1, 0, 1)
            self.assertEqual('frequency', result['classifications'][0]['kind'])

    def test_cli_complete_evidence_and_advice_are_strict_successes(self):
        for text in ('每年都考。' + EVIDENCE,
                     '| 术语 | 题型建议 |\n| --- | --- |\n| 网络 | 简答 |'):
            result = self.run_checker(text, '--strict')
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertNotIn('warn ', result.stdout)
            self.assertIn('question IDs and statistical truth are not verified', result.stdout)

    def test_cli_anchor_only_warns_default_zero_strict_one(self):
        for args, expected in (((), 0), (('--strict',), 1)):
            result = self.run_checker('常考。' + ANCHOR, *args)
            self.assertEqual(expected, result.returncode, result.stderr)
            self.assertIn('needs a statistical scope', result.stdout)

    # E4: the rewritten 题型建议 note must not re-introduce a frequency claim.
    def test_non_statistical_disclaimer_is_not_a_frequency_claim(self):
        note = '题型建议用于选择自测方式，不代表历年出题频率或命题预测。'
        result = self.audit(note)
        self.assert_counts(result, 0, 0, 0)
        self.assertEqual([{'line': 1, 'kind': 'advice'}], result['classifications'])
        self.assert_counts(self.audit('| 术语 | 题型建议 |\n| --- | --- |\n| 网络 | 简答 |\n\n'
                                      + note), 0, 0, 0)

    def test_disclaimer_never_exempts_an_actual_frequency_claim(self):
        for text in ('常考，不代表历年出题频率或命题预测。',
                     '每年必考。题型建议不代表命题预测。',
                     '常考。该句不代表命题预测。'):
            with self.subTest(text=text):
                self.assert_counts(self.audit(text), 1, 0, 1)

    def test_negated_prose_is_not_a_must_test_claim(self):
        result = self.audit('互联时不必考虑各种帧结构和地址类型。')
        self.assert_counts(result, 0, 0, 0)
        self.assert_counts(self.audit('本章必考。'), 1, 0, 1)


if __name__ == '__main__':
    unittest.main()
