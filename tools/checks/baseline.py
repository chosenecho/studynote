"""Seal an evaluation baseline: source snapshot, check outputs and content fingerprints."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DATE = '2026-11-16'
LIB = Path(os.environ['EXAM_LIBRARY']) if os.environ.get('EXAM_LIBRARY') else None
if LIB is None:
    print('缺少资料库目录：设置 EXAM_LIBRARY 指向成书与题库所在目录。', file=sys.stderr)
    raise SystemExit(2)
SNAPSHOT = ROOT / 'local/sources' / DATE
OUT = ROOT / 'artifacts/eval' / f'baseline-{DATE}.json'
SOURCES = [
    ('成书/操作系统概论/操作系统概论（2017年版）.md', 'os'),
    ('成书/计算机组成原理/book.md', 'co'),
    ('成书/计算机网络技术/计算机网络技术.md', 'cn'),
    ('成书/多媒体技术及应用/多媒体技术及应用（第三版）.md', 'mm'),
    ('多媒体技术与应用_13511_真题资料/江苏官方_13511多媒体技术与应用_考试大纲.pdf', 'mm-syllabus'),
    ('成书/计算机网络技术/分章/03 大纲·Ⅲ 课程内容与考核要求.md', 'cn-syllabus'),
    ('成书/计算机网络技术/分章/02 大纲·Ⅱ 考核目标.md', 'cn-syllabus'),
    ('成书/计算机网络技术/分章/05 大纲·Ⅴ 题型举例.md', 'cn-syllabus'),
]
CHECKS = (
    'tools/checks/structure.py', 'tools/checks/notes.py', 'tools/checks/revisions.py',
    'tools/checks/syllabus.py', 'tools/checks/counts.py', 'tools/checks/arithmetic.py',
    'tools/checks/exam_claims.py',
)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest().upper()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True,
                          encoding='utf-8').stdout.strip()


SNAPSHOT.mkdir(parents=True, exist_ok=True)
manifest = []
for relative, course in SOURCES:
    source = LIB / relative
    if not source.is_file():
        manifest.append({'source': relative, 'course': course, 'status': 'missing'})
        continue
    target = SNAPSHOT / course / source.name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    manifest.append({
        'source': relative,
        'course': course,
        'snapshot': target.relative_to(ROOT).as_posix(),
        'bytes': source.stat().st_size,
        'sha256': sha256(source),
        'status': 'copied',
    })
(SNAPSHOT / 'snapshot-manifest.json').write_text(
    json.dumps({'date': DATE, 'library': str(LIB), 'files': manifest},
               ensure_ascii=False, indent=1), encoding='utf-8')

content = []
for path in sorted((ROOT / 'docs/courses').glob('**/*.md')):
    if path.name.startswith('chapter-') or (path.parent.name == 'exam' and path.name != 'index.md'):
        content.append({'path': path.relative_to(ROOT).as_posix(),
                        'bytes': path.stat().st_size,
                        'sha256': sha256(path)})

checks = []
for script in CHECKS:
    run = subprocess.run([sys.executable, '-X', 'utf8', script], cwd=ROOT,
                         capture_output=True, text=True, encoding='utf-8')
    checks.append({
        'script': script,
        'exit': run.returncode,
        'stdout': run.stdout.strip().splitlines()[-1:] or [''] ,
        'errors': (run.stderr or '').strip().splitlines()[-2:],
    })

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps({
    'date': DATE,
    'head': git('rev-parse', 'HEAD'),
    'branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
    'status': git('status', '--porcelain'),
    'checks': checks,
    'snapshot_manifest': (SNAPSHOT / 'snapshot-manifest.json').relative_to(ROOT).as_posix(),
    'content_files': content,
}, ensure_ascii=False, indent=1), encoding='utf-8')

print(f'Baseline sealed: {len([m for m in manifest if m["status"] == "copied"])} sources, '
      f'{len(content)} content files, {len(checks)} checks → {OUT.relative_to(ROOT).as_posix()}')
for check in checks:
    print(f'  {check["script"]:34} exit={check["exit"]} {check["stdout"][0][:90]}')
