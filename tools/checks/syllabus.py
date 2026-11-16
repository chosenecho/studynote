"""Audit syllabus coverage: learning-navigation rows against registry, sections and practice."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'artifacts/eval/syllabus-coverage.json'
syllabus = json.loads((ROOT / 'config/syllabus.json').read_text(encoding='utf-8'))
courses = json.loads((ROOT / 'config/courses.json').read_text(encoding='utf-8'))
slug_by_id = {c['id']: c['slug'] for c in courses}
LEVELS = {'识记', '领会', '简单应用', '综合应用'}
errors = []
matrix = []
coded = uncoded = 0


def nav_block(text):
    """Return (header_label, rows) for the single 学习导航 table."""
    if text.count('## 学习导航') != 1:
        return None
    block = text.split('## 学习导航', 1)[1].split('\n## ', 1)[0]
    header = ''
    rows = []
    for line in block.splitlines():
        if not line.startswith('|'):
            continue
        cells = [c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells) != 4:
            continue
        if cells[2] == '讲解':
            header = cells[0]
            continue
        if any(set(c) <= set('-: ') for c in cells):
            continue
        rows.append(cells)
    return header, rows


for chapter in syllabus['chapters']:
    path = ROOT / chapter['path']
    text = path.read_text(encoding='utf-8')
    label = chapter['id']
    sections = chapter['sections']
    practice = chapter['practice']
    objectives = chapter.get('objectives') or []
    rows = nav_block(text)
    if rows is None:
        errors.append(f'{label}: missing a single 学习导航 block')
        continue
    header_label, rows = rows
    if not rows:
        errors.append(f'{label}: 学习导航 has no entries')
        continue
    header_kind = 'objectives-table' if header_label == '大纲条目索引' else 'topic-table'
    topics = chapter.get('topics') or []
    if topics:
        if len(rows) != len(topics):
            errors.append(f'{label}: navigation has {len(rows)} rows for {len(topics)} registered topics')
        for index, (row, topic) in enumerate(zip(rows, topics)):
            anchors = [int(n) for n in re.findall(r'#s(\d+)', row[2])]
            levels_list = [x for x in row[1].split('、') if x]
            if row[0] != topic.get('name'):
                errors.append(f"{label}: topic {index+1} name '{row[0]}' differs from registry '{topic.get('name')}'")
            if anchors != topic.get('sections'):
                errors.append(f"{label}: topic {index+1} sections {anchors} differ from registry {topic.get('sections')}")
            if levels_list != topic.get('levels'):
                errors.append(f"{label}: topic {index+1} levels {levels_list} differ from registry {topic.get('levels')}")
    elif header_kind == 'topic-table':
        errors.append(f'{label}: topic-style navigation without a registered topics list')
    if header_kind == 'objectives-table' and objectives and len(rows) != len(objectives):
        errors.append(f'{label}: navigation has {len(rows)} rows for {len(objectives)} objectives')
    number_of_section = {s['number']: s for s in sections}
    practice_of_number = {q['number']: q for q in practice}
    covered = []
    cited = set()
    row_reports = []
    for row in rows:
        entry, levels, explain, practice_cell = row
        anchors = [int(n) for n in re.findall(r'#s(\d+)', explain)]
        levels_list = [x for x in levels.split('、') if x]
        refs = [int(n) for n in re.findall(r'\d+', practice_cell)]
        if not entry:
            errors.append(f'{label}: navigation row has an empty syllabus entry')
        if not anchors:
            errors.append(f'{label}: row "{entry}" explains no section')
        for anchor in anchors:
            if anchor not in number_of_section:
                errors.append(f'{label}: row "{entry}" points at unknown section {anchor}')
        if not levels_list or set(levels_list) - LEVELS:
            errors.append(f'{label}: row "{entry}" level "{levels}" is outside the level vocabulary')
        if not refs:
            errors.append(f'{label}: row "{entry}" lists no practice')
        for ref in refs:
            spec = practice_of_number.get(ref)
            if spec is None:
                errors.append(f'{label}: row "{entry}" cites practice {ref}, which is not registered')
            elif not set(spec['sections']) & set(anchors):
                errors.append(f'{label}: row "{entry}" cites practice {ref} outside its sections')
            else:
                cited.add(ref)
        covered.extend(anchors)
        for scope in number_of_section.get(anchors[0], {'scope': []})['scope'] if anchors else []:
            for part in [p for p in scope.split('、') if p.strip()]:
                if re.match(r'^\s*\d+(\.\d+)*\s', part):
                    coded += 1
                else:
                    uncoded += 1
        row_reports.append({
            'entry': entry,
            'levels': levels_list,
            'sections': anchors,
            'practice': refs,
        })
    if len(covered) != len(set(covered)):
        errors.append(f'{label}: some sections appear in two navigation rows')
    missing = sorted(set(number_of_section) - set(covered))
    if missing:
        errors.append(f'{label}: sections without a navigation row: {missing}')
    uncovered = sorted(set(practice_of_number) - cited)
    if uncovered:
        errors.append(f'{label}: practice not cited by any row: {uncovered}')
    exam_path = path.parent / 'exam' / f"{re.search(r'chapter-(\d{2})', path.name)[1]}.md"
    exam_tags = re.findall(r'【考纲 ([^】]+)】', exam_path.read_text(encoding='utf-8')) if exam_path.is_file() else []
    matrix.append({
        'id': label,
        'course': slug_by_id[label.split('-')[0]],
        'table_kind': header_kind,
        'sections': len(sections),
        'objectives': len(objectives),
        'topics': len(topics),
        'practice': len(practice),
        'rows': len(rows),
        'exam_tag_count': len(exam_tags),
        'rows_detail': row_reports,
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({
    'chapters': len(matrix),
    'coded_scope_items': coded,
    'plain_scope_items': uncoded,
    'matrix': matrix,
}, ensure_ascii=False, indent=1), encoding='utf-8')

print(f"Syllabus matrix: {len(matrix)} chapters, {coded} coded scope items, "
      f"{uncoded} plain items, written to {OUT.relative_to(ROOT).as_posix()}")
if errors:
    print('\n'.join(errors))
    sys.exit(1)
