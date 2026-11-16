"""Draft per-question exam records with keyword candidates from the syllabus scope.

Each question gets the chapter/section whose scope terms appear in its stem, plus
a candidate list with hit counts. Nothing here is a final mapping: statuses stay
'mapping-pending' and the reviewer confirms or overrides the candidates.
"""
from pathlib import Path
import argparse
import json
import re

ROOT = Path(__file__).resolve().parents[2]
MAP_TERM_MIN = 2


def normalize(text):
    text = text.replace('（', '(').replace('）', ')').replace('，', ',')
    text = re.sub(r'\s+', '', text)
    return text.lower()


def scope_terms(chapter):
    terms = set()
    for section in chapter.get('sections', []):
        for item in section.get('scope', []):
            for piece in re.split('、', item):
                piece = piece.strip()
                piece = re.sub(r'^[\d.]+\s*', '', piece)
                piece = piece.split(',')[0]
                if len(piece) >= 2:
                    terms.add(piece)
    return terms


def sketch(code, questions_path, syllabus_path, out):
    data = json.loads(questions_path.read_text(encoding='utf-8'))
    syllabus = json.loads(syllabus_path.read_text(encoding='utf-8'))
    chapters = {c['id']: c for c in syllabus['chapters']}
    per_chapter_terms = {cid: scope_terms(c) for cid, c in chapters.items() if cid.endswith('')}
    records = []
    for paper in data['papers']:
        if paper['code'] != code:
            continue
        period = f"{paper['year']}-{paper['month']:02d}"
        for question in paper['questions']:
            stem = normalize(' '.join([question['stem']] + question['body']))
            hits = []
            for cid, terms in per_chapter_terms.items():
                if not cid.split('-')[0].endswith(code_map_code(code)):
                    continue
                matched = sorted(t for t in terms if normalize(t) in stem)
                if len(matched) >= MAP_TERM_MIN:
                    hits.append((len(matched), cid, matched))
            hits.sort(reverse=True)
            candidates = [{'chapter_id': cid, 'terms': matched} for _, cid, matched in hits[:4]]
            records.append({
                'question_id': f"{code}-{period}-Q{question['question_no']:02d}",
                'paper_id': paper['paper_id'],
                'period': period,
                'question_no': question['question_no'],
                'type': question['type'],
                'points': question['points'],
                'stem': question['stem'],
                'candidates': candidates,
                'chapter_refs': [],
                'section_refs': [],
                'topic_tags': [],
                'syllabus_level': '未登记',
                'review_status': 'mapping-pending',
            })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'code': code, 'records': records}, ensure_ascii=False, indent=1) + '\n',
                   encoding='utf-8')
    print(f'Sketch: {code} {len(records)} questions -> {out}')


def code_map_code(code):
    return {'02141': 'cn', '02318': 'co', '02323': 'os', '13511': 'mm'}[code]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--code', required=True)
    ap.add_argument('--questions', default=str(ROOT / 'artifacts/eval/exam-questions.json'))
    ap.add_argument('--syllabus', default=str(ROOT / 'config/syllabus.json'))
    ap.add_argument('--out', default=None)
    args = ap.parse_args()
    out = Path(args.out or ROOT / f'artifacts/eval/map-sketch-{args.code}.json')
    sketch(args.code, Path(args.questions), Path(args.syllabus), out)


if __name__ == '__main__':
    main()
