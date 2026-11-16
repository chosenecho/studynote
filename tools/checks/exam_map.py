"""Check the exam-to-notes mapping and report per-chapter coverage of recent papers."""
from pathlib import Path
import json
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / 'config/exam-map.json'
OUT = ROOT / 'artifacts/eval/exam-coverage.md'
STATUSES = {'source-checked', 'mapping-pending', 'blocked-pending-source'}
RECENT_FROM = (2020, 8)

if not MAP.is_file():
    print('Exam map: config/exam-map.json not present yet, coverage stats skipped')
    sys.exit(0)

data = json.loads(MAP.read_text(encoding='utf-8'))
errors = []
exams_db = os.environ.get('EXAM_DB')
db = None
if exams_db and Path(exams_db).is_file():
    import sqlite3
    db = sqlite3.connect(f'file:{exams_db}?mode=ro', uri=True)
else:
    print('Exam map: EXAM_DB unset or missing, paper-level checks reduced to the map')

papers = {}
if db is not None:
    for pid, code, year, month, qn in db.execute(
            'select id, code, year, month, question_numbers from papers'):
        papers[pid] = (code, int(year), int(month), qn or '')
bank_codes = set(entry[0] for entry in papers.values())

lines = ['# 真题覆盖统计（自动生成）', '',
         f'数据源：`config/exam-map.json`；近五年自 {RECENT_FROM[0]}-{RECENT_FROM[1]:02d} 起。', '']
lines.append('| 课程代码 | 试卷 | 题号 | 近五年题号 | source-checked | mapping-pending | blocked |')
lines.append('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')

totals = {'papers': 0, 'questions': 0, 'recent': 0, 'checked': 0, 'pending': 0, 'blocked': 0}
chapter_hits = {}
bankless = []
for course in data.get('courses', []):
    code = course.get('code', '')
    in_bank = db is not None and code in bank_codes
    per = {'papers': 0, 'questions': 0, 'recent': 0, 'checked': 0, 'pending': 0, 'blocked': 0}
    for paper in course.get('papers', []):
        per['papers'] += 1
        pid = paper.get('paper_id', '')
        period = paper.get('period', '')
        if in_bank and pid not in papers:
            errors.append(f'{code}: paper {pid} is absent from EXAM_DB')
        if in_bank and pid in papers:
            known = set(int(n) for n in re.findall(r'\d+', papers[pid][3]))
            for question in paper.get('questions', []):
                if int(question.get('question_no', 0)) not in known:
                    errors.append(f"{code}: {pid} question {question.get('question_no')} is not in papers.question_numbers")
        recent = False
        match = re.match(r'(\d{4})-(\d{2})', period)
        if match and (int(match[1]), int(match[2])) >= RECENT_FROM:
            recent = True
        for question in paper.get('questions', []):
            per['questions'] += 1
            if recent:
                per['recent'] += 1
            status = question.get('review_status')
            if status not in STATUSES:
                errors.append(f"{code}: {pid} Q{question.get('question_no')} has status {status}")
            per['checked' if status == 'source-checked' else
                'pending' if status == 'mapping-pending' else 'blocked'] += 1
            for chapter in question.get('chapter_refs', []):
                key = (code, int(chapter))
                chapter_hits[key] = chapter_hits.get(key, 0) + 1
    for key in totals:
        totals[key] += per[key]
    lines.append(f"| {code} | {per['papers']} | {per['questions']} | {per['recent']} | "
                 f"{per['checked']} | {per['pending']} | {per['blocked']} |")
    if db is not None and not in_bank:
        bankless.append(f'- {code}：该课程无本地题库，按映射文件统计。')

if bankless:
    lines += ['', '## 无本地题库的课程', ''] + bankless

lines += ['', f"合计：{totals['papers']} 套，{totals['questions']} 题，其中近五年 "
              f"{totals['recent']} 题；已核 {totals['checked']}，待映射 {totals['pending']}，"
              f"阻断 {totals['blocked']}。", '',
          '## 章节命中（近五年与旧卷合计，按题号计数）', '',
          '| 课程代码 | 章 | 命中题号数 |', '| --- | ---: | ---: |']
for (code, chapter), hits in sorted(chapter_hits.items()):
    lines.append(f'| {code} | {chapter} | {hits} |')

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print(f"Exam map: {totals['papers']} papers, {totals['questions']} questions, "
      f"{totals['checked']} source-checked; report at {OUT.relative_to(ROOT).as_posix()}")
for line in bankless:
    print(f'Exam map: {line.lstrip("- ")}')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
