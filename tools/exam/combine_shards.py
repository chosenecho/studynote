"""Combine per-paper mapping shards into one course draft.

Shards live at tools/exam/map/<code>/<anything>.json and each holds either one
paper object ({"paper_id": ..., "period": ..., "questions": [...]}) or a list of
paper objects. Usage:

    python -X utf8 tools/exam/combine_shards.py 02141

The result is written to tools/exam/map/<code>.json, which
tools/exam/merge_maps.py then validates and merges into config/exam-map.json.
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAPS = ROOT / 'tools' / 'exam' / 'map'
NAMES = {
    '02141': '计算机网络技术',
    '02318': '计算机组成原理',
    '02323': '操作系统概论',
    '13511': '多媒体技术及应用（第三版）',
}


def papers_of(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and 'papers' in payload and 'paper_id' not in payload:
        return payload['papers']
    return [payload]


def main(argv):
    if len(argv) != 2 or argv[1] not in NAMES:
        print('usage: combine_shards.py <' + '|'.join(sorted(NAMES)) + '>')
        return 2
    code = argv[1]
    folder = MAPS / code
    if not folder.is_dir():
        print(f'combine_shards: no shards at {folder.relative_to(ROOT).as_posix()}')
        return 1

    papers, order, seen = [], [], set()
    for path in sorted(folder.glob('*.json')):
        payload = json.loads(path.read_text(encoding='utf-8'))
        for paper in papers_of(payload):
            pid = paper.get('paper_id')
            if not pid:
                print(f'combine_shards: {path.name} holds a paper without paper_id')
                return 1
            if pid in seen:
                print(f'combine_shards: duplicate paper {pid} ({path.name})')
                return 1
            seen.add(pid)
            order.append(paper.get('period', ''))
            papers.append(paper)

    papers.sort(key=lambda p: p.get('period', ''))
    questions = sum(len(p.get('questions', [])) for p in papers)
    draft = {'code': code, 'name': NAMES[code], 'papers': papers}
    out = MAPS / f'{code}.json'
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'combine_shards: {code} {len(papers)} papers, {questions} questions '
          f'-> {out.relative_to(ROOT).as_posix()}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
