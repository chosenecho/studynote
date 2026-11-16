"""Require an exam anchor for every claim about how often a topic is tested."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
CLAIMS = (
    '近年', '近五年', '没出过', '未考过', '从未考', '考过', '常考',
    '每年', '每次考', '多年', '反复考', '高频', '高频考点',
)
# "最高频率" and similar technical terms are not exam-frequency claims.
FALSE_FRIENDS = ('最高频率', '超高', '甚高频', '高频带')
ANCHOR = re.compile(r'<!--\s*(真题|真题范围|exam)\s*[:：]')
SKIP_PREFIX = ('|', '```', '    ', '#')
errors, warnings = [], []
checked = guarded = 0

for page in sorted((ROOT / 'docs/courses').glob('*/exam/*.md')):
    if page.name == 'index.md':
        continue
    rel = page.relative_to(ROOT).as_posix()
    lines = page.read_text(encoding='utf-8').splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith(SKIP_PREFIX):
            continue
        probe = line
        for friend in FALSE_FRIENDS:
            probe = probe.replace(friend, '')
        found = [word for word in CLAIMS if word in probe]
        if not found:
            continue
        checked += 1
        window = '\n'.join(lines[index:index + 4])
        if ANCHOR.search(window):
            guarded += 1
            continue
        snippet = line.strip()[:70]
        warnings.append(f'{rel}:{index + 1}: {"/".join(found)} → needs <!-- 真题: ID --> | {snippet}')

print(f'Exam claims: {checked} claim lines, {guarded} with a nearby anchor, '
      f'{len(warnings)} without')
for line in warnings:
    print('warn ' + line)
if errors:
    print('\n'.join(errors))
    sys.exit(1)
if '--strict' in sys.argv and warnings:
    sys.exit(1)
