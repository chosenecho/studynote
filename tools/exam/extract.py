"""Split local exam papers into per-question records for the mapping ledger.

Reads the OCR markdown of each paper in the external question bank, cuts the
text by the declared section headers, and writes one record per question with
its number, section type, points and the question stem. Stems stay local: the
output goes under artifacts/, which is outside the published site and outside
the mapping file.
"""
from pathlib import Path
import argparse
import json
import os
import re
import sqlite3
import sys

CN_NUM = '一二三四五六七八九十'
SECTION_RE = re.compile(rf'^[#\s]*([{CN_NUM}]+)\s*[、.]\s*(.*)$')
DECLARED_RE = re.compile(r'本大题共\s*(\d+)\s*(小题|空)')
POINTS_PER_RE = re.compile(r'每(?:小题|空)\s*(\d+)\s*分')
POINTS_LIST_RE = re.compile(r'第\s*(\d+)\s*小题\s*(\d+)\s*分')
QUESTION_RE = re.compile(r'^(?:#+\s*)?(\d{1,2})\s*(?:\\)?\s*[.、．]\s*(.*)$')
PAGE_RE = re.compile(r'^##\s*卷面页')

TYPE_BY_KEYWORD = (
    ('单项选择', 'single_choice'),
    ('多项选择', 'multiple_choice'),
    ('填空', 'fill_blank'),
    ('名词解释', 'term_explain'),
    ('简答', 'short_answer'),
    ('计算', 'calculation'),
    ('综合应用', 'integration'),
    ('综合', 'integration'),
    ('应用', 'application'),
    ('论述', 'essay'),
    ('判断', 'judgement'),
    ('设计', 'design'),
)


def section_type(title):
    for key, value in TYPE_BY_KEYWORD:
        if key in title:
            return value
    return 'unknown'


def parse_paper(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    sections = []
    current = None
    for line in lines:
        stripped = line.strip()
        if PAGE_RE.match(stripped):
            continue
        match = SECTION_RE.match(stripped)
        if match and len(match.group(1)) <= 6:
            current = {'title': match.group(2).strip(), 'lines': [], 'line': None}
            sections.append(current)
            continue
        if current is not None:
            current['lines'].append(stripped)
    for section in sections:
        declared = DECLARED_RE.search(section['title'])
        section['declared'] = int(declared.group(1)) if declared else 0
        per = POINTS_PER_RE.search(section['title'])
        section['points_per'] = int(per.group(1)) if per else 0
        section['points_list'] = {int(a): int(b) for a, b in POINTS_LIST_RE.findall(section['title'])}
        section['type'] = section_type(section['title'])
    return sections


def split_questions(section):
    items = []
    buffer = None
    for line in section['lines']:
        match = QUESTION_RE.match(line)
        if match:
            if buffer is not None:
                items.append(buffer)
            buffer = {'question_no': int(match.group(1)), 'stem': match.group(2).strip(), 'body': []}
            continue
        if buffer is not None:
            buffer['body'].append(line)
    if buffer is not None:
        items.append(buffer)
    return items


def build(bank, out):
    db_path = bank / '题库.sqlite3'
    if not db_path.is_file():
        print(f'Extract: {db_path} not found', file=sys.stderr)
        sys.exit(1)
    db = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    rows = db.execute(
        'select id, code, course, year, month, ocr_path, question_numbers from papers'
        ' order by code, year, month').fetchall()
    papers = []
    problems = []
    for paper_id, code, course, year, month, ocr_path, numbers in rows:
        ocr = bank / ocr_path
        if not ocr.is_file():
            problems.append({'paper_id': paper_id, 'kind': 'missing-ocr', 'detail': ocr_path})
            continue
        known = [int(n) for n in json.loads(numbers or '[]')]
        sections = parse_paper(ocr)
        questions = []
        cursor = 0
        for section in sections:
            items = split_questions(section)
            if not items:
                continue
            restarts = items[0]['question_no'] == 1
            for item in items:
                number = cursor + item['question_no'] if restarts else item['question_no']
                points = section['points_list'].get(number, section['points_per'])
                questions.append({
                    'question_no': number,
                    'section_no': item['question_no'],
                    'type': section['type'],
                    'points': points,
                    'stem': item['stem'],
                    'body': [b for b in item['body'] if b],
                    'section_title': section['title'],
                })
            cursor = max(q['question_no'] for q in questions)
        seen = [q['question_no'] for q in questions]
        if seen != known:
            missing = [n for n in known if n not in seen]
            extra = [n for n in seen if n not in known]
            problems.append({
                'paper_id': paper_id, 'kind': 'number-mismatch',
                'missing': missing, 'extra': extra,
                'found': len(seen), 'expected': len(known),
            })
        papers.append({
            'paper_id': paper_id, 'code': code, 'course': course,
            'year': int(year), 'month': int(month), 'ocr_path': ocr_path,
            'sections': [{'title': s['title'], 'type': s['type'], 'declared': s['declared'],
                          'points_per': s['points_per']} for s in sections],
            'questions': questions,
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'papers': papers, 'problems': problems},
                              ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    total = sum(len(p['questions']) for p in papers)
    print(f'Extract: {len(papers)} papers, {total} questions, {len(problems)} problems; '
          f'report at {out}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bank', default=os.environ.get('EXAM_BANK', ''),
                    help='外部题库目录；也可用 EXAM_BANK 环境变量指定')
    ap.add_argument('--out', default='artifacts/eval/exam-questions.json')
    args = ap.parse_args()
    if not args.bank:
        print('缺少题库目录：传 --bank 或设置 EXAM_BANK。', file=sys.stderr)
        return 2
    build(Path(args.bank), Path(args.out))
    return 0


if __name__ == '__main__':
    main()
