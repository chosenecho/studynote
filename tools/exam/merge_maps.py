"""Merge per-course exam mapping drafts into config/exam-map.json.

Each draft lives at tools/exam/map/<code>.json and holds one course entry:
{"code": "02318", "name": "...", "papers": [...]}
This script validates the drafts, keeps the existing 13511 entry untouched,
replaces any course whose code matches a draft, and sorts courses by code.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAP = ROOT / 'config/exam-map.json'
DRAFTS = ROOT / 'tools/exam/map'
STATUSES = {'source-checked', 'mapping-pending', 'blocked-pending-source'}
UNREGISTERED = '未登记'


def fail(message):
    print(f'merge_maps: {message}')
    sys.exit(1)


def check_draft(draft, chapters, levels):
    code = draft.get('code') or fail('draft without code')
    problems = []
    if not draft.get('name'):
        problems.append(f'{code}: missing name')
    paper_ids = set()
    question_ids = set()
    for paper in draft.get('papers', []):
        pid = paper.get('paper_id')
        if not pid:
            problems.append(f'{code}: paper without paper_id')
        if pid in paper_ids:
            problems.append(f'{code}: duplicate paper {pid}')
        paper_ids.add(pid)
        if not paper.get('period'):
            problems.append(f'{code}/{pid}: missing period')
        for question in paper.get('questions', []):
            qid = question.get('question_id')
            if not qid:
                problems.append(f'{code}/{pid}: question without question_id')
                continue
            if qid in question_ids:
                problems.append(f'{code}: duplicate question_id {qid}')
            question_ids.add(qid)
            status = question.get('review_status')
            if status not in STATUSES:
                problems.append(f'{code}/{qid}: review_status {status!r}')
            level = question.get('syllabus_level')
            if level not in levels:
                problems.append(f'{code}/{qid}: syllabus_level {level!r}')
            chs = question.get('chapter_refs') or []
            if not chs:
                problems.append(f'{code}/{qid}: empty chapter_refs')
            for ch in chs:
                if not isinstance(ch, int) or ch not in chapters:
                    problems.append(f'{code}/{qid}: chapter_refs {ch!r} outside the course')
            for ref in question.get('section_refs') or []:
                if not isinstance(ref, str) or '.' not in ref:
                    problems.append(f'{code}/{qid}: section_refs {ref!r} is not "<chapter>.<section>"')
                elif int(ref.split('.')[0]) not in chs:
                    problems.append(f'{code}/{qid}: section_refs {ref} not covered by chapter_refs')
    return problems


def main():
    if not DRAFTS.is_dir():
        fail(f'no drafts at {DRAFTS.relative_to(ROOT).as_posix()}')
    syllabus = json.loads((ROOT / 'config/syllabus.json').read_text(encoding='utf-8'))
    course_chapters = {}
    course_levels = {}
    for chapter in syllabus['chapters']:
        prefix = chapter['id'].split('-')[0].upper()
        course_chapters.setdefault(prefix, set()).add(int(chapter['id'].split('-')[1]))
        levels = course_levels.setdefault(prefix, set())
        for section in chapter['sections']:
            levels.update(section.get('levels', []))
        for objective in chapter.get('objectives', []):
            levels.update(objective.get('levels', []))
    prefix_of_code = {'02323': 'OS', '02318': 'CO', '02141': 'CN', '13511': 'MM'}

    data = json.loads(MAP.read_text(encoding='utf-8')) if MAP.is_file() else {'version': 1, 'courses': []}
    existing = {course['code']: course for course in data.get('courses', [])}

    problems = []
    merged = []
    for path in sorted(DRAFTS.glob('*.json')):
        draft = json.loads(path.read_text(encoding='utf-8'))
        code = draft.get('code', '')
        chapters = course_chapters.get(prefix_of_code.get(code, ''), set())
        if not chapters:
            problems.append(f'{code}: no chapter registry in config/syllabus.json')
        problems += check_draft(draft, chapters, course_levels.get(prefix_of_code.get(code, ''), set()) | {UNREGISTERED})
        merged.append(draft)

    if problems:
        print('\n'.join(problems))
        fail(f'{len(problems)} problems in drafts, nothing written')

    by_code = {course['code']: course for course in merged}
    for code, course in existing.items():
        by_code.setdefault(code, course)
    data['courses'] = [by_code[code] for code in sorted(by_code)]
    MAP.parent.mkdir(parents=True, exist_ok=True)
    MAP.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False) + '\n', encoding='utf-8')

    for code in sorted(by_code):
        course = by_code[code]
        questions = sum(len(paper.get('questions', [])) for paper in course.get('papers', []))
        checked = sum(1 for paper in course.get('papers', []) for q in paper.get('questions', [])
                      if q.get('review_status') == 'source-checked')
        print(f"merge_maps: {code} {len(course.get('papers', []))} papers, "
              f"{questions} questions, {checked} source-checked")
    print(f"merge_maps: wrote {MAP.relative_to(ROOT).as_posix()}")


if __name__ == '__main__':
    main()
