"""Validate exam mappings independently of the optional read-only question bank.

Importing this module has no I/O side effects. ``audit`` returns diagnostics and
coverage Markdown; ``main`` loads files and publishes the report for the CLI.
"""
from contextlib import closing
import json
import math
import os
from pathlib import Path
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[2]
STATUSES = {'source-checked', 'mapping-pending', 'blocked-pending-source'}
QUESTION_TYPES = {
    'single_choice', 'multiple_choice', 'fill_blank', 'short_answer',
    'integration', 'term_explain', 'term_definition', 'calculation',
    'application', 'design', 'essay',
}
PREFIX_OF_CODE = {'02323': 'os', '02318': 'co', '02141': 'cn', '13511': 'mm'}
RECENT_FROM = (2020, 8)
# 13511's preserved source uses textbook subsections, not the syllabus's
# grouped section.number namespace (see its paper version_note). Check syntax
# and registered chapter ownership, but do not invent a subsection conversion.
TEXTBOOK_SECTION_CODES = {'13511'}


def _positive_int(value):
    return type(value) is int and value > 0


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _period(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}', value):
        return None
    year, month = map(int, value.split('-'))
    return (year, month) if year > 0 and 1 <= month <= 12 else None


def _registry(syllabus, errors):
    """Build registered chapters, sections and level vocabularies per course."""
    registry = {code: {} for code in PREFIX_OF_CODE}
    levels = {code: {'未登记'} for code in PREFIX_OF_CODE}
    code_of_prefix = {prefix: code for code, prefix in PREFIX_OF_CODE.items()}
    if not isinstance(syllabus, dict) or not isinstance(syllabus.get('chapters'), list):
        errors.append('syllabus: chapters must be a list')
        return registry, levels
    for chapter in syllabus['chapters']:
        if not isinstance(chapter, dict):
            errors.append('syllabus: chapter must be an object')
            continue
        match = re.fullmatch(r'([a-z]+)-([1-9][0-9]*)', str(chapter.get('id', '')).lower())
        if not match or match[1] not in code_of_prefix:
            errors.append(f"syllabus: unknown chapter id {chapter.get('id')!r}")
            continue
        code, number = code_of_prefix[match[1]], int(match[2])
        sections = chapter.get('sections')
        if not isinstance(sections, list):
            errors.append(f'syllabus: {chapter["id"]} sections must be a list')
            continue
        registered = set()
        for section in sections:
            if not isinstance(section, dict) or not _positive_int(section.get('number')):
                errors.append(f'syllabus: {chapter["id"]} invalid section number')
                continue
            registered.add(section['number'])
            for level in section.get('levels', []):
                if isinstance(level, str):
                    levels[code].add(level)
        for objective in chapter.get('objectives', []):
            if isinstance(objective, dict):
                for level in objective.get('levels', []):
                    if isinstance(level, str):
                        levels[code].add(level)
        registry[code][number] = {'sections': registered, 'title': chapter.get('title', '')}
    return registry, levels


def _validate_map(data, registry, levels, errors):
    if not isinstance(data, dict):
        errors.append('map must be an object')
        return
    if type(data.get('version')) is not int or data['version'] != 1:
        errors.append('map version must be integer 1')
    courses = data.get('courses')
    if not isinstance(courses, list) or not courses:
        errors.append('map courses must be a nonempty list')
        return
    codes, paper_ids, question_ids = set(), set(), set()
    for ci, course in enumerate(courses):
        label = f'courses[{ci}]'
        if not isinstance(course, dict):
            errors.append(f'{label}: course must be an object')
            continue
        code = course.get('code')
        if not _text(code):
            errors.append(f'{label}: code must be a nonempty string')
            code = ''
        if code in codes:
            errors.append(f'{label}: duplicate code {code}')
        codes.add(code)
        if code not in registry or not registry[code]:
            errors.append(f'{code}: no chapter registry in config/syllabus.json')
        if not _text(course.get('name')):
            errors.append(f'{code}: name must be a nonempty string')
        papers = course.get('papers')
        if not isinstance(papers, list) or not papers:
            errors.append(f'{code}: papers must be a nonempty list')
            continue
        for pi, paper in enumerate(papers):
            label = f'{code}/papers[{pi}]'
            if not isinstance(paper, dict):
                errors.append(f'{label}: paper must be an object')
                continue
            pid = paper.get('paper_id')
            if not _text(pid):
                errors.append(f'{label}: paper_id must be a nonempty string')
                pid = ''
            if pid in paper_ids:
                errors.append(f'{label}: duplicate paper_id {pid}')
            paper_ids.add(pid)
            label = f'{code}/{pid}'
            if _period(paper.get('period')) is None:
                errors.append(f'{label}: period must be valid YYYY-MM')
            questions = paper.get('questions')
            if not isinstance(questions, list) or not questions:
                errors.append(f'{label}: questions must be a nonempty list')
                continue
            question_numbers = set()
            for qi, question in enumerate(questions):
                qlabel = f'{label}/questions[{qi}]'
                if not isinstance(question, dict):
                    errors.append(f'{qlabel}: question must be an object')
                    continue
                qid = question.get('question_id')
                if not _text(qid):
                    errors.append(f'{qlabel}: question_id must be a nonempty string')
                    qid = ''
                if qid in question_ids:
                    errors.append(f'{qlabel}: duplicate question_id {qid}')
                question_ids.add(qid)
                qlabel = f'{label}/{qid}'
                qno = question.get('question_no')
                if not _positive_int(qno):
                    errors.append(f'{qlabel}: question_no must be a positive integer (not bool)')
                else:
                    if qno in question_numbers:
                        errors.append(f'{qlabel}: duplicate question_no {qno}')
                    question_numbers.add(qno)
                status = question.get('review_status')
                if not isinstance(status, str) or status not in STATUSES:
                    errors.append(f'{qlabel}: invalid review_status {status!r}')
                level = question.get('syllabus_level')
                if not isinstance(level, str) or level not in levels.get(code, set()):
                    errors.append(f'{qlabel}: invalid syllabus_level {level!r}')
                kind = question.get('type')
                if not isinstance(kind, str) or kind not in QUESTION_TYPES:
                    errors.append(f'{qlabel}: invalid type {kind!r}')
                points = question.get('points')
                # Zero is retained from source records with unrecorded scores.
                if (type(points) not in (int, float) or points < 0
                        or (type(points) is float and not math.isfinite(points))):
                    errors.append(f'{qlabel}: points must be a nonnegative finite number (not bool)')
                tags = question.get('topic_tags')
                if not isinstance(tags, list) or any(not _text(tag) for tag in tags):
                    errors.append(f'{qlabel}: topic_tags must be a list of nonempty strings')
                chapters = question.get('chapter_refs')
                if not isinstance(chapters, list):
                    errors.append(f'{qlabel}: chapter_refs must be a list')
                    chapters = []
                if not chapters and status == 'source-checked':
                    errors.append(f'{qlabel}: source-checked requires nonempty chapter_refs')
                valid_chapters = set()
                for chapter in chapters:
                    if not _positive_int(chapter) or chapter not in registry.get(code, {}):
                        errors.append(f'{qlabel}: chapter_refs {chapter!r} outside registered course')
                    elif chapter in valid_chapters:
                        errors.append(f'{qlabel}: duplicate chapter_refs {chapter}')
                    else:
                        valid_chapters.add(chapter)
                sections = question.get('section_refs')
                if not isinstance(sections, list):
                    errors.append(f'{qlabel}: section_refs must be a list')
                    continue
                seen_sections = set()
                pattern = (r'[1-9][0-9]*(?:\.[1-9][0-9]*)+'
                           if code in TEXTBOOK_SECTION_CODES
                           else r'[1-9][0-9]*\.[1-9][0-9]*')
                for ref in sections:
                    if not isinstance(ref, str) or not re.fullmatch(pattern, ref):
                        errors.append(f'{qlabel}: invalid section_refs {ref!r}')
                        continue
                    chapter, section = map(int, ref.split('.')[:2])
                    if ref in seen_sections:
                        errors.append(f'{qlabel}: duplicate section_refs {ref}')
                    seen_sections.add(ref)
                    if chapter not in valid_chapters:
                        errors.append(f'{qlabel}: section_refs {ref} not covered by chapter_refs')
                    elif (code not in TEXTBOOK_SECTION_CODES
                          and section not in registry[code][chapter]['sections']):
                        errors.append(f'{qlabel}: section_refs {ref} outside registered section range')


def _check_bank(courses, db_path, errors, warnings):
    """Snapshot bank metadata and close the read-only connection before checks."""
    try:
        path = Path(db_path).expanduser().resolve()
        if not path.is_file():
            raise ValueError('not a readable file')
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            rows = db.execute('select id, code, year, month, question_numbers from papers').fetchall()
    except (OSError, ValueError, TypeError, sqlite3.Error) as exc:
        errors.append(f'EXAM_DB {db_path!r}: {exc}')
        return
    papers = {pid: (code, year, month, numbers) for pid, code, year, month, numbers in rows}
    bank_codes = {row[1] for row in rows}
    for course in courses:
        code = course['code']
        if code not in bank_codes:
            warnings.append(f'{code}：该课程无本地题库，降级为仅映射文件统计与校验。')
        for paper in course['papers']:
            pid = paper['paper_id']
            bank = papers.get(pid)
            if bank is None:
                if code in bank_codes:
                    errors.append(f'{code}: paper {pid} is absent from EXAM_DB')
                continue
            bank_code, year, month, numbers = bank
            if bank_code != code:
                errors.append(f'{code}/{pid}: EXAM_DB paper code is {bank_code!r}')
            try:
                bank_period = (int(year), int(month))
            except (ValueError, TypeError, OverflowError):
                bank_period = None
            if bank_period != _period(paper['period']):
                errors.append(f'{code}/{pid}: EXAM_DB paper period differs from {paper["period"]}')
            known = {int(n) for n in re.findall(r'[0-9]+', str(numbers or ''))}
            for question in paper['questions']:
                if question['question_no'] not in known:
                    errors.append(f'{code}/{pid}: question {question["question_no"]} is not in papers.question_numbers')


def _coverage(courses, registry, warnings):
    start = f'{RECENT_FROM[0]}-{RECENT_FROM[1]:02d}'
    lines = ['# 真题覆盖统计（自动生成）', '',
             f'数据源：`config/exam-map.json`；固定统计窗口自 {start} 起（含当月），非滚动窗口。', '',
             f'| 课程代码 | 试卷 | 题号 | {start} 起题号 | source-checked | mapping-pending | blocked |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    totals = dict.fromkeys(('papers', 'questions', 'recent', 'checked', 'pending', 'blocked'), 0)
    hits, recent_hits = {}, {}
    for course in courses:
        code = course['code']
        per = dict.fromkeys(totals, 0)
        for paper in course['papers']:
            per['papers'] += 1
            recent = _period(paper['period']) >= RECENT_FROM
            for question in paper['questions']:
                per['questions'] += 1
                per['recent'] += int(recent)
                per[{'source-checked': 'checked', 'mapping-pending': 'pending',
                     'blocked-pending-source': 'blocked'}[question['review_status']]] += 1
                for chapter in question['chapter_refs']:
                    key = (code, chapter)
                    hits[key] = hits.get(key, 0) + 1
                    recent_hits[key] = recent_hits.get(key, 0) + int(recent)
        for key in totals:
            totals[key] += per[key]
        lines.append(f"| {code} | {per['papers']} | {per['questions']} | {per['recent']} | "
                     f"{per['checked']} | {per['pending']} | {per['blocked']} |")
    if warnings:
        lines += ['', '## 校验模式与降级说明', ''] + [f'- {warning}' for warning in warnings]
    if any(c['code'] in TEXTBOOK_SECTION_CODES for c in courses):
        lines += ['', '## 小节编号体系', '',
                  '13511 的 section_refs 为教材多级编号（如 1.1.1、8.14），与 syllabus.json 的分组小节编号不对应；'
                  '校验正整数编号语法、注册章范围及 chapter_refs 归属，不推断小节换算。'
                  '其他课程的小节须精确命中 syllabus.json 已注册的章与小节。']
    lines += ['', f"合计：{totals['papers']} 套，{totals['questions']} 题，其中 {start} 起 "
              f"{totals['recent']} 题；已核 {totals['checked']}，待映射 {totals['pending']}，"
              f"阻断 {totals['blocked']}。", '', '## 章节命中（全部试卷，按题号计数）', '',
              f'| 课程代码 | 章 | 命中题号数 | 其中 {start} 起 |', '| --- | ---: | ---: | ---: |']
    for (code, chapter), count in sorted(hits.items()):
        lines.append(f'| {code} | {chapter} | {count} | {recent_hits.get((code, chapter), 0)} |')
    gaps = [f'- {course["code"]} 第 {number} 章（{spec["title"]}）：{start} 起映射中没有题号落点。'
            for course in courses for number, spec in registry[course['code']].items()
            if not recent_hits.get((course['code'], number), 0)]
    if gaps:
        lines += ['', f'## {start} 起无题号落点的章', ''] + gaps
    return '\n'.join(lines) + '\n', totals


def audit(data, syllabus, db_path=None):
    """Return errors, warnings, report and totals without writing any files.

    ``None`` selects map-only mode; any supplied DB path must exist and be
    queryable. Malformed maps are rejected before statistics or DB comparison.
    """
    errors, warnings = [], []
    registry, levels = _registry(syllabus, errors)
    _validate_map(data, registry, levels, errors)
    result = {'errors': errors, 'warnings': warnings, 'report': '', 'totals': {}}
    if errors:
        return result
    if db_path is None:
        warnings.append('EXAM_DB 未指定：仅映射文件校验；未进行题库试卷与题号核对。')
    else:
        _check_bank(data['courses'], db_path, errors, warnings)
    result['report'], result['totals'] = _coverage(data['courses'], registry, warnings)
    return result


def main(root=ROOT, environ=None):
    """CLI entry point; return 0 for a passing gate, otherwise 1."""
    root = Path(root)
    environ = os.environ if environ is None else environ
    try:
        data = json.loads((root / 'config/exam-map.json').read_text(encoding='utf-8'))
        syllabus = json.loads((root / 'config/syllabus.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print(f'Exam map: input error: {exc}')
        return 1
    db_path = environ.get('EXAM_DB')
    if 'EXAM_DB' in environ and not db_path:
        print('Exam map: EXAM_DB is explicitly set but empty')
        return 1
    result = audit(data, syllabus, db_path)
    if result['report']:
        out = root / 'artifacts/eval/exam-coverage.md'
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(result['report'], encoding='utf-8')
        except OSError as exc:
            print(f'Exam map: report error: {exc}')
            return 1
        totals = result['totals']
        print(f"Exam map: {totals['papers']} papers, {totals['questions']} questions, "
              f"{totals['checked']} source-checked; report at {out.relative_to(root).as_posix()}")
    for message in result['warnings'] + result['errors']:
        print(f'Exam map: {message}')
    return 1 if result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
