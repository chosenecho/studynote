"""Keep the three pages of a chapter consistent: index counts, section labels, shared terms."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/eval/counts.json'
courses = json.loads((ROOT / 'config/courses.json').read_text(encoding='utf-8'))
errors, warnings = [], []
report = []


def numbered_items(block):
    return [int(n) for n in re.findall(r'^(\d+)\. ', block, re.M)]


def table_rows(block, header):
    rows = []
    for line in block.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if any(set(c) <= set('-: ') for c in cells) or cells[0] == header:
            continue
        rows.append(cells)
    return rows


for course in courses:
    folder = ROOT / 'docs/courses' / course['slug']
    index = (folder / 'exam/index.md').read_text(encoding='utf-8')
    cards = {}
    for number, backed, memo in re.findall(r'\(\s*(\d{2})\.md\)\*\*\n\n必背 (\d+) 条 · 默写 (\d+) 题', index):
        cards[int(number)] = (int(backed), int(memo))
    if len(cards) != course['chapters']:
        errors.append(f"{course['slug']}: exam index lists {len(cards)} cards for {course['chapters']} chapters")
    for chapter_no in range(1, course['chapters'] + 1):
        exam = (folder / 'exam' / f'{chapter_no:02}.md').read_text(encoding='utf-8')
        note = (folder / f'chapter-{chapter_no:02}.md').read_text(encoding='utf-8')
        backed_block = exam.split('## 必背清单', 1)[1].split('## 必背数字与公式', 1)[0]
        memo_block = exam.split('## 默写自测', 1)[1]
        backed = numbered_items(backed_block)
        memo = numbered_items(memo_block)
        actual = (max(backed), max(memo))
        card = cards.get(chapter_no)
        if card and card != actual:
            errors.append(f"{course['slug']} ch{chapter_no:02}: card {card} differs from lists {actual}")
        if backed != list(range(1, len(backed) + 1)):
            errors.append(f"{course['slug']} ch{chapter_no:02}: 必背清单 numbering has gaps")
        if memo != list(range(1, len(memo) + 1)):
            errors.append(f"{course['slug']} ch{chapter_no:02}: 默写自测 numbering has gaps")
        section_labels = [int(n) for n in re.findall(r'^\*\*第 (\d+) 节\*\*', backed_block, re.M)]
        objective_labels = [int(n) for n in re.findall(r'^\*\*考纲条目 (\d+)\*\*', backed_block, re.M)]
        sections_in_chapter = len(re.findall(r'^## \d+ .+? \{#s\d+\}$', note, re.M))
        if any(n < 1 or n > sections_in_chapter for n in section_labels):
            errors.append(f"{course['slug']} ch{chapter_no:02}: 必背清单 cites a section outside 1..{sections_in_chapter}")
        if section_labels != sorted(section_labels):
            errors.append(f"{course['slug']} ch{chapter_no:02}: 必背清单 section labels are out of order")
        if not section_labels and objective_labels:
            if objective_labels != sorted(objective_labels):
                errors.append(f"{course['slug']} ch{chapter_no:02}: 必背清单 考纲条目 labels are out of order")
        else:
            missing_sections = sorted(set(range(1, sections_in_chapter + 1)) - set(section_labels))
            if missing_sections:
                warnings.append(f"{course['slug']} ch{chapter_no:02}: no 必背清单 group for sections {missing_sections}")
        terms = [r[0] for r in table_rows(exam.split('## 必背名词', 1)[1].split('\n## ', 1)[0], '术语') if len(r) >= 2]
        absent = [t for t in terms if t and t not in note]
        if absent:
            warnings.append(f"{course['slug']} ch{chapter_no:02}: {len(absent)} terms absent from the chapter page: {absent[:6]}")
        report.append({
            'course': course['slug'],
            'chapter': chapter_no,
            'card': card,
            'backed': actual[0],
            'memo': actual[1],
            'section_labels': section_labels,
            'objective_labels': objective_labels,
            'terms': len(terms),
            'terms_absent': absent,
        })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
print(f'Counts: {len(report)} chapters checked, {len(warnings)} warnings, '
      f'{len(errors)} errors, report at {OUT.relative_to(ROOT).as_posix()}')
for line in warnings:
    print('warn ' + line)
for line in errors:
    print('error ' + line)
if errors:
    sys.exit(1)
