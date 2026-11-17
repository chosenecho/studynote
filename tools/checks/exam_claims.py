"""Audit exam-frequency claims, not technical frequencies or question-type advice.

Real frequency claims require two separate comments in the same evidence window::

    <!-- 真题: QUESTION_ID -->
    <!-- 真题范围: 年份=2020-2025; 试卷=PAPER_SET; 样本量=12 -->

All three scope fields are mandatory. Years must be an ordered four-digit year
range (a single year is allowed), papers a non-placeholder set description, and
sample size a positive integer. This checks evidence presence/shape only, NOT
question-ID authenticity or whether the stated statistics are correct.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = ('近年', '近五年', '没出过', '未考过', '从未考', '考过', '常考',
          '每年', '每次考', '多年', '反复考', '高频', '高频考点', '必考', '考频')
FALSE_FRIENDS = ('最高频率', '超高频', '甚高频', '高频带', '高频信号', '高频电路',
                 '高频分量', '高频载波', '高频振荡', '高频滤波', '提高频带')
COMMENTS = re.compile(r'<!--.*?-->', re.DOTALL)
ANCHOR = re.compile(r'<!--\s*(?:真题|exam)\s*[:：]\s*([^<>]*?)\s*-->', re.DOTALL)
SCOPE = re.compile(r'<!--\s*真题范围\s*[:：]\s*([^<>]*?)\s*-->', re.DOTALL)
YEARS = re.compile(r'((?:19|20)\d{2})(?:\s*[-–—~～至]\s*((?:19|20)\d{2}))?')
PLACEHOLDER = re.compile(r'^(?:\.{3}|…+|待.*|未知|不详|见.*|同上|若干|无|N/?A|[?？-]+)$', re.I)
EXPLICIT = re.compile(r'常考|必考|高频|考频|考过|未考过|从未考|没出过|反复考|每次考|逢考')
# 不必考虑 is ordinary prose, not a 必考 claim.
NEGATED_CLAIM = re.compile(r'不必(?=考)')
CONTEXTUAL = re.compile(
    r'(?:近[一二三四五六七八九十\d]*年|历年|每年|多年|连续.{0,8}年).{0,30}(?:考|出题|出现)|'
    r'(?:考题|考试|真题|试卷).{0,30}(?:频率|比例|占比|出现|\d+\s*次)|'
    r'(?:考了|考查了?|考察了?).{0,10}[一二三四五六七八九十\d]+\s*次')
STATISTIC = re.compile(r'频率|[占命中出现]率|占比|统计|\d+(?:\.\d+)?\s*%|近年|每年|多年')
ADVICE = re.compile(r'题型建议|建议题型|建议.{0,12}(?:简答|填空|选择|计算|应用|题型)')
DISCLAIMER = re.compile(r'不代表[^。！？；\n]{0,20}(?:频率|频次|命题预测)')
SEPARATOR = re.compile(r':?-{3,}:?')
SCOPE_HINT = '<!-- 真题范围: 年份=2020-2025; 试卷=...; 样本量=... -->'


def claim_words(line):
    """Find real exam-frequency signals, excluding comments and technical terms.

    A bare 常考 header still makes a historical frequency claim even if all its
    cells contain question types. Only an explicitly relabelled 题型建议 is advice.
    """
    text = COMMENTS.sub('', line)
    # Remove only the negated clause, never exempt the entire line.
    text = DISCLAIMER.sub('', text)
    text = NEGATED_CLAIM.sub('', text)
    for friend in FALSE_FRIENDS:
        text = text.replace(friend, '')
    if not (EXPLICIT.search(text) or CONTEXTUAL.search(text)):
        return []
    words = [word for word in CLAIMS if word in text]
    return words or ['考试频次']


def table_cells(line):
    """Split a Markdown table row, preserving escaped pipes inside cells."""
    if '|' not in line:
        return []
    return [cell.strip() for cell in re.split(r'(?<!\\)\|', line.strip().strip('|'))]


def scope_complete(value):
    """Validate required fields in ONE scope; never merge partial comments."""
    fields = {}
    for part in re.split(r'[;；]', value):
        key, sep, field = part.replace('＝', '=').partition('=')
        if not sep or key.strip() in fields:
            return False
        fields[key.strip()] = field.strip()
    years = YEARS.fullmatch(fields.get('年份', ''))
    papers = fields.get('试卷', '')
    sample = fields.get('样本量', '')
    return bool(years and (not years[2] or int(years[1]) <= int(years[2]))
                and papers and not PLACEHOLDER.fullmatch(papers)
                and re.fullmatch(r'[1-9]\d*', sample))


def check_lines(lines, rel):
    """Pure audit; keep checked/guarded/warnings and add a classification ledger.

    Table header frequency/advice semantics apply to every body row. Evidence
    belongs to that row only. Prose retains the next-three-lines comment window,
    stopping at another claim, heading, table, code fence or ordinary prose.
    Historical/deferred labels never bypass frequency evidence requirements.
    """
    warnings, classifications = [], []
    checked = guarded = 0
    disclaimer = False
    table_claims, table_advice = [], False
    in_table = False
    fence = None
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        marker = re.match(r'(`{3,}|~{3,})', stripped)
        if marker:
            if fence is None:
                fence = marker.group()[0]
            elif marker.group()[0] == fence:
                fence = None
            in_table, table_claims, table_advice = False, [], False
            continue
        if fence is not None:
            continue
        cells = table_cells(line)
        next_cells = table_cells(lines[index + 1]) if index + 1 < len(lines) else []
        if cells and next_cells and len(cells) == len(next_cells) and all(
                SEPARATOR.fullmatch(cell) for cell in next_cells):
            in_table = True
            header = COMMENTS.sub('', ' '.join(cells))
            table_claims = claim_words(header)
            table_advice = bool(ADVICE.search(header))
            continue
        if cells and all(SEPARATOR.fullmatch(cell) for cell in cells):
            continue
        if not cells:
            in_table, table_claims, table_advice = False, [], False
        if stripped.startswith('#') or line.startswith('    '):
            continue
        found = list(dict.fromkeys((table_claims if in_table else []) + claim_words(line)))
        visible = COMMENTS.sub('', line)
        advice = (in_table and table_advice) or bool(ADVICE.search(visible))
        if not found:
            kind = 'advice' if advice else 'statistic' if STATISTIC.search(visible) else None
            if kind:
                classifications.append({'line': index + 1, 'kind': kind})
            continue
        checked += 1
        window = [line]
        if not cells:
            for nearby in lines[index + 1:index + 4]:
                if not nearby.strip():
                    continue
                if not nearby.lstrip().startswith('<!--') or claim_words(nearby):
                    break
                window.append(nearby)
        evidence = '\n'.join(window)
        anchor = any(match.group(1).strip() for match in ANCHOR.finditer(evidence))
        scope = any(scope_complete(match.group(1)) for match in SCOPE.finditer(evidence))
        classifications.append({'line': index + 1, 'kind': 'frequency',
                                'anchor': anchor, 'scope': scope})
        if anchor and scope:
            guarded += 1
            continue
        missing = []
        if not anchor:
            missing.append('<!-- 真题: ID -->')
        if not scope:
            missing.append('a statistical scope ' + SCOPE_HINT)
        snippet = line.strip()[:70]
        warnings.append(f'{rel}:{index + 1}: {"/".join(found)} → needs '
                        f'{" and ".join(missing)} | {snippet}')
    return {'checked': checked, 'guarded': guarded, 'warnings': warnings,
            'classifications': classifications}


def main(argv=None, root=ROOT):
    """Default warns with exit 0; --strict exits 1 on any missing evidence."""
    argv = sys.argv[1:] if argv is None else argv
    checked = guarded = 0
    warnings = []
    kinds = {'frequency': 0, 'advice': 0, 'statistic': 0}
    for page in sorted((root / 'docs/courses').glob('*/exam/*.md')):
        if page.name == 'index.md':
            continue
        result = check_lines(page.read_text(encoding='utf-8').splitlines(),
                             page.relative_to(root).as_posix())
        checked += result['checked']
        guarded += result['guarded']
        warnings.extend(result['warnings'])
        for item in result['classifications']:
            kinds[item['kind']] += 1
    print(f'Exam claims: {checked} claim lines, {guarded} with anchor and scope, '
          f'{len(warnings)} without complete evidence')
    print(f'Classification: {kinds["frequency"]} frequency, {kinds["advice"]} advice, '
          f'{kinds["statistic"]} other statistics/technical lines')
    print('Evidence presence/shape only; question IDs and statistical truth are not verified.')
    for warning in warnings:
        print('warn ' + warning)
    return int('--strict' in argv and bool(warnings))


if __name__ == '__main__':
    sys.exit(main())
