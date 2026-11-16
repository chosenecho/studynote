"""Validate course manifests, authored links and canonical source paths."""
from pathlib import Path
import json
import re
import sys
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[2]
courses = json.loads((ROOT / 'config/courses.json').read_text(encoding='utf-8'))
config = yaml.safe_load((ROOT / 'mkdocs.yml').read_text(encoding='utf-8'))
errors = []
for field in ('id', 'slug', 'title'):
    values = [c[field] for c in courses]
    if len(values) != len(set(values)):
        errors.append(f'Duplicate course {field}')
for course in courses:
    folder = ROOT / 'docs/courses' / course['slug']
    expected = {f'chapter-{n:02}.md' for n in range(1, course['chapters'] + 1)}
    actual = {p.name for p in folder.glob('chapter-*.md')}
    if actual != expected:
        errors.append(f'{folder.name}: chapter files differ: {actual ^ expected}')
    if not (folder / 'index.md').is_file():
        errors.append(f'{folder.name}: missing course index')
    exam = folder / 'exam'
    if not (exam / 'index.md').is_file():
        errors.append(f'{folder.name}: missing exam index')
    if not (folder / 'learn' / 'index.md').is_file():
        errors.append(f'{folder.name}: missing learn index')
    expected_exam = {f'{n:02}.md' for n in range(1, course['chapters'] + 1)}
    actual_exam = {p.name for p in exam.glob('*.md')} - {'index.md'} if exam.is_dir() else set()
    if actual_exam != expected_exam:
        errors.append(f'{folder.name}: exam pages differ: {actual_exam ^ expected_exam}')
    if any(p.name.startswith('chapter-') for p in exam.glob('*.md')):
        errors.append(f'{folder.name}: exam pages must not use the chapter- file prefix')
# Navigation labels must read like the page they open; landing-role labels are exempt.
ROLE_LABELS = {'课程导航', '学习概览', '考点总览', '首页', '复习首页', '速查首页', '练习入口'}
VIRTUAL_PAGES = {'licensing.md', 'third-party-notices.md'}
TAB_COUNT = len(courses) + 3


def nav_pairs(items, out):
    for item in items:
        if isinstance(item, dict):
            for label, value in item.items():
                if isinstance(value, str):
                    out.append((label, value))
                else:
                    out.append((label, None))
                    nav_pairs(value, out)
    return out


def title_of(path):
    for line in path.read_text(encoding='utf-8').splitlines():
        if line.startswith('# '):
            return line[2:].strip()
    return ''


def compact(value):
    return re.sub(r'[·・:：\s]', '', value)


for label, target in nav_pairs(config['nav'], []):
    if target is None:
        continue
    path = ROOT / 'docs' / target
    if not path.is_file():
        if target not in VIRTUAL_PAGES:
            errors.append(f'导航指向不存在的源文件：{label} -> {target}')
        continue
    title = title_of(path)
    if compact(label) == compact(title) or compact(label) in compact(title):
        continue
    if label in ROLE_LABELS:
        continue
    errors.append(f'导航标签与页面标题不一致：{label} != {title}（{target}）')
if len(config['nav']) != TAB_COUNT:
    errors.append(
        f'顶层导航数量应为 {TAB_COUNT}（课程 {len(courses)} 门 + 3 个固定分区：首页、复习、关于），实际 {len(config["nav"])}')

# Heading depth stays at four levels or fewer so the rendered TOC covers every block.
for path in (ROOT / 'docs/courses').rglob('*.md'):
    for match in re.finditer(r'^(#{5,6})\s', path.read_text(encoding='utf-8'), re.M):
        errors.append(f'{path.relative_to(ROOT).as_posix()}: 标题层级过深 {match.group(1)}')

sources = list((ROOT / 'docs').rglob('*.md')) + list((ROOT / 'handbook').rglob('*.md'))
sources += [ROOT / name for name in ('README.md', 'LICENSING.md', 'THIRD_PARTY_NOTICES.md')]
for p in sources:
    text = p.read_text(encoding='utf-8')
    for href in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)', text):
        parts = urlsplit(href)
        if parts.scheme or parts.netloc or not parts.path:
            continue
        target = (p.parent / unquote(parts.path)).resolve()
        virtual = {
            ROOT / 'docs/licensing.md': ROOT / 'LICENSING.md',
            ROOT / 'docs/third-party-notices.md': ROOT / 'THIRD_PARTY_NOTICES.md',
        }
        target = virtual.get(target, target)
        if not target.is_relative_to(ROOT) or not target.exists():
            errors.append(f'{p.relative_to(ROOT)}: missing link {href}')
for name in ('content', 'website', 'scripts', 'esa'):
    if (ROOT / name).exists():
        errors.append(f'Retired root path exists: {name}')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'Structure passed: {len(courses)} courses, source links, canonical paths')
