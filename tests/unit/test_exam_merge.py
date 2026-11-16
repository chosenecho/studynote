"""Test that merging exam-map drafts stays a rebuildable, data-preserving step."""
import importlib.util
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def merge_module():
    spec = importlib.util.spec_from_file_location('exam_merge_maps', ROOT / 'tools/exam/merge_maps.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MergeCoursesTests(unittest.TestCase):
    def test_course_only_in_existing_map_is_preserved(self):
        merge = merge_module()
        kept = {'code': '13511', 'papers': [{'paper_id': 'FJ-13511-202304'}]}
        drafts = [{'code': '02318', 'papers': []}]
        result = merge.merge_courses({'13511': kept}, drafts)
        self.assertEqual([course['code'] for course in result], ['02318', '13511'])
        self.assertIs(result[1], kept)

    def test_draft_replaces_same_code_and_output_is_sorted(self):
        merge = merge_module()
        existing = {'02318': {'code': '02318', 'papers': [{'paper_id': 'old'}]}}
        draft = {'code': '02318', 'papers': [{'paper_id': 'new'}]}
        result = merge.merge_courses(existing, [draft])
        self.assertEqual(result[0]['papers'], [{'paper_id': 'new'}])

    def test_pending_question_can_be_rebuilt_without_inventing_a_chapter(self):
        merge = merge_module()
        question = dict(question_id='13511-pending', question_no=25,
                        review_status='mapping-pending', syllabus_level='未登记',
                        chapter_refs=[], section_refs=[])
        draft = dict(code='13511', name='Demo', papers=[dict(
            paper_id='demo', period='2023-04', questions=[question])])
        self.assertEqual(merge.check_draft(draft, {1}, {'未登记'}), [])
        question['review_status'] = 'source-checked'
        self.assertTrue(any('empty chapter_refs' in error
                            for error in merge.check_draft(draft, {1}, {'未登记'})))

    def test_all_courses_rebuild_and_merge_roundtrip_without_an_existing_map(self):
        merge = merge_module()
        spec = importlib.util.spec_from_file_location(
            'exam_combine_shards', ROOT / 'tools/exam/combine_shards.py')
        combine = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(combine)
        expected = json.loads((ROOT / 'config/exam-map.json').read_text(encoding='utf-8'))
        with TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            root = Path(tmp)
            maps = root / 'tools/exam/map'
            maps.mkdir(parents=True)
            (root / 'config').mkdir()
            (root / 'config/syllabus.json').write_bytes((ROOT / 'config/syllabus.json').read_bytes())
            for draft in (ROOT / 'tools/exam/map').glob('*.json'):
                (maps / draft.name).write_bytes(draft.read_bytes())
            # Exercise the new 13511 paper input rather than trusting its aggregate.
            folder = maps / '13511'
            folder.mkdir()
            for shard in (ROOT / 'tools/exam/map/13511').glob('*.json'):
                (folder / shard.name).write_bytes(shard.read_bytes())
            with patch.object(combine, 'ROOT', root), patch.object(combine, 'MAPS', maps):
                self.assertEqual(combine.main(['combine_shards.py', '13511']), 0)
            output = root / 'config/exam-map.json'
            with patch.object(merge, 'ROOT', root), patch.object(merge, 'MAP', output), \
                    patch.object(merge, 'DRAFTS', maps):
                merge.main()
                rebuilt = json.loads(output.read_text(encoding='utf-8'))
                self.assertEqual(rebuilt['courses'], expected['courses'])
                first = output.read_bytes()
                merge.main()
                self.assertEqual(output.read_bytes(), first)


if __name__ == '__main__':
    unittest.main()
