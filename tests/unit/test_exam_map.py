"""Exam-map gate regression tests; all file/DB writes use temporary directories."""
from contextlib import closing, redirect_stdout
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'tools/checks/exam_map.py'


def load_module():
    spec = importlib.util.spec_from_file_location('exam_map_gate', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


exam_map = load_module()


def syllabus_fixture():
    return {'chapters': [
        {'id': f'{prefix}-{chapter}', 'title': f'Chapter {chapter}', 'sections': [
            {'number': section, 'levels': ['识记', '领会', '简单应用', '综合应用']}
            for section in (1, 2)]}
        for prefix, chapter in [('os', 1), ('os', 2), ('mm', 1), ('mm', 8)]
    ]}


def map_fixture(code='02323', period='2020-08'):
    return {'version': 1, 'courses': [{'code': code, 'name': 'Course', 'papers': [{
        'paper_id': 'paper-1', 'period': period, 'questions': [{
            'question_id': 'paper-1-Q01', 'question_no': 1,
            'type': 'single_choice', 'points': 1,
            'chapter_refs': [1], 'section_refs': ['1.1'],
            'topic_tags': ['topic'], 'syllabus_level': '识记',
            'review_status': 'source-checked',
        }],
    }]}]}


def question(data):
    return data['courses'][0]['papers'][0]['questions'][0]


def paper(data):
    return data['courses'][0]['papers'][0]


class ExamMapValidationTests(unittest.TestCase):
    def audit(self, data=None, db_path=None):
        return exam_map.audit(map_fixture() if data is None else data,
                              syllabus_fixture(), db_path)

    def assert_invalid(self, data, diagnostic):
        result = self.audit(data)
        self.assertTrue(result['errors'])
        self.assertIn(diagnostic, '\n'.join(result['errors']))
        self.assertEqual('', result['report'])

    def test_import_has_no_io_or_exit_side_effects(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('read on import')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('mkdir on import')), \
                patch.object(sqlite3, 'connect', side_effect=AssertionError('DB on import')), \
                patch('builtins.print') as output:
            module = load_module()
        self.assertTrue(callable(module.audit))
        self.assertTrue(callable(module.main))
        output.assert_not_called()

    def test_valid_map_only_and_fixed_statistics(self):
        data = map_fixture()
        old = deepcopy(paper(data))
        old.update(paper_id='paper-old', period='2020-07')
        old['questions'][0]['question_id'] = 'paper-old-Q01'
        data['courses'][0]['papers'].append(old)
        result = self.audit(data)
        self.assertEqual([], result['errors'])
        self.assertEqual({'papers': 2, 'questions': 2, 'recent': 1, 'checked': 2,
                          'pending': 0, 'blocked': 0}, result['totals'])
        self.assertIn('EXAM_DB 未指定', result['warnings'][0])
        self.assertIn('固定统计窗口自 2020-08 起', result['report'])
        self.assertNotIn('近五年', result['report'])
        self.assertIn('第 2 章', result['report'])

    def test_malformed_container_shapes(self):
        for data, message in [([], 'map must be an object'), ({}, 'version'),
                              ({'version': True, 'courses': []}, 'version'),
                              ({'version': 1, 'courses': {}}, 'courses'),
                              ({'version': 1, 'courses': []}, 'courses'),
                              ({'version': 1, 'courses': [None]}, 'course must')]:
            with self.subTest(data=data):
                self.assert_invalid(data, message)
        for target, field, value, message in [
                ('course', 'code', [], 'code'), ('course', 'code', '99999', 'registry'),
                ('course', 'name', None, 'name'), ('course', 'papers', {}, 'papers'),
                ('course', 'papers', [], 'papers'), ('course', 'papers', [None], 'paper must'),
                ('paper', 'paper_id', {}, 'paper_id'), ('paper', 'questions', {}, 'questions'),
                ('paper', 'questions', [], 'questions'),
                ('paper', 'questions', [None], 'question must'),
                ('question', 'question_id', [], 'question_id'),
                ('question', 'chapter_refs', None, 'chapter_refs'),
                ('question', 'section_refs', {}, 'section_refs'),
                ('question', 'topic_tags', 'bad', 'topic_tags'),
                ('question', 'topic_tags', [None], 'topic_tags')]:
            with self.subTest(target=target, field=field, value=value):
                data = map_fixture()
                node = {'course': data['courses'][0], 'paper': paper(data),
                        'question': question(data)}[target]
                node[field] = value
                self.assert_invalid(data, message)

    def test_question_positive_integer_excludes_bool(self):
        for value in (None, True, False, 0, -1, 1.5, '1', [], {}):
            with self.subTest(value=value):
                data = map_fixture()
                question(data)['question_no'] = value
                self.assert_invalid(data, 'positive integer (not bool)')

    def test_invalid_periods(self):
        for value in (None, True, [], '2020-00', '2020-13', '0000-01',
                      '2020-8', '2020-08suffix', '2020-08-01'):
            with self.subTest(value=value):
                data = map_fixture()
                paper(data)['period'] = value
                self.assert_invalid(data, 'period must be valid YYYY-MM')

    def test_duplicate_identifiers_and_question_numbers(self):
        for kind in ('code', 'paper_id', 'question_id', 'question_no'):
            with self.subTest(kind=kind):
                data = map_fixture()
                if kind == 'code':
                    data['courses'].append(deepcopy(data['courses'][0]))
                elif kind == 'paper_id':
                    data['courses'][0]['papers'].append(deepcopy(paper(data)))
                else:
                    extra = deepcopy(question(data))
                    if kind == 'question_id':
                        extra['question_no'] = 2
                    else:
                        extra['question_id'] = 'different-id'
                    paper(data)['questions'].append(extra)
                self.assert_invalid(data, f'duplicate {kind}')

    def test_question_ids_are_unique_across_papers(self):
        data = map_fixture()
        extra = deepcopy(paper(data))
        extra['paper_id'] = 'paper-2'
        data['courses'][0]['papers'].append(extra)
        self.assert_invalid(data, 'duplicate question_id')

    def test_registered_chapters_and_sections(self):
        for refs in ([True], [0], [-1], ['1'], [99], [1, 1]):
            with self.subTest(chapters=refs):
                data = map_fixture()
                question(data)['chapter_refs'] = refs
                self.assert_invalid(data, 'chapter_refs')
        for ref in ('1.99', '2.1', '1.1.1', '1.0', '1.-1', '01.1',
                    '1.foo', '1', True, 1, {}, None):
            with self.subTest(section=ref):
                data = map_fixture()
                question(data)['section_refs'] = [ref]
                self.assert_invalid(data, 'section_refs')
        data = map_fixture()
        question(data)['section_refs'] = ['1.1', '1.1']
        self.assert_invalid(data, 'duplicate section_refs')

    def test_status_levels_types_and_points(self):
        for field, values in [
                ('review_status', ['done', None, []]),
                ('syllabus_level', ['expert', None, []]),
                ('type', ['unknown', None, []]),
                ('points', [-1, True, None, '1', float('nan'), float('inf')])]:
            for value in values:
                with self.subTest(field=field, value=value):
                    data = map_fixture()
                    question(data)[field] = value
                    self.assert_invalid(data, field)
        for value in (0, 0.5, 10 ** 400):
            data = map_fixture()
            question(data)['points'] = value
            self.assertEqual([], self.audit(data)['errors'])
        data = map_fixture()
        question(data)['syllabus_level'] = '未登记'
        self.assertEqual([], self.audit(data)['errors'])

    def test_pending_empty_chapters_explicitly_allowed(self):
        for status in ('mapping-pending', 'blocked-pending-source'):
            with self.subTest(status=status):
                data = map_fixture()
                question(data).update(review_status=status, chapter_refs=[], section_refs=[])
                self.assertEqual([], self.audit(data)['errors'])
        data = map_fixture()
        question(data).update(chapter_refs=[], section_refs=[])
        self.assert_invalid(data, 'source-checked requires nonempty chapter_refs')

    def test_13511_textbook_namespace_not_syllabus_group_numbers(self):
        data = map_fixture('13511')
        question(data).update(chapter_refs=[1, 8], section_refs=['1.1.1', '8.14'])
        result = self.audit(data)
        self.assertEqual([], result['errors'])
        self.assertIn('与 syllabus.json 的分组小节编号不对应', result['report'])
        for refs in (['2.1.1'], ['1.0.1'], ['8.14x']):
            with self.subTest(refs=refs):
                bad = deepcopy(data)
                question(bad)['section_refs'] = refs
                self.assert_invalid(bad, 'section_refs')
        bad = deepcopy(data)
        question(bad).update(chapter_refs=[9], section_refs=['9.1'])
        self.assert_invalid(bad, 'outside registered course')

    def test_missing_or_invalid_syllabus_registry(self):
        for syllabus in ({}, [], {'chapters': [None]}, {'chapters': []}):
            with self.subTest(syllabus=syllabus):
                self.assertTrue(exam_map.audit(map_fixture(), syllabus)['errors'])

    def test_real_map_is_valid_without_bank_or_source_changes(self):
        source = ROOT / 'config/exam-map.json'
        before = source.read_bytes()
        data = json.loads(before)
        syllabus = json.loads((ROOT / 'config/syllabus.json').read_text(encoding='utf-8'))
        result = exam_map.audit(data, syllabus)
        self.assertEqual([], result['errors'])
        self.assertEqual(49, result['totals']['papers'])
        self.assertEqual(1798, result['totals']['questions'])
        self.assertEqual(1181, result['totals']['recent'])
        self.assertEqual(before, source.read_bytes())


class ExamMapFileAndBankTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.data = map_fixture()
        self.write_inputs()

    def write_inputs(self):
        (self.root / 'config/exam-map.json').write_text(
            json.dumps(self.data), encoding='utf-8')
        (self.root / 'config/syllabus.json').write_text(
            json.dumps(syllabus_fixture()), encoding='utf-8')

    def run_main(self, env=None):
        output = io.StringIO()
        with redirect_stdout(output):
            status = exam_map.main(self.root, {} if env is None else env)
        return status, output.getvalue()

    def create_bank(self, rows=None):
        path = self.root / 'bank # 题库.sqlite'
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('create table papers (id text, code text, year integer, month integer, question_numbers text)')
            db.executemany('insert into papers values (?, ?, ?, ?, ?)', rows if rows is not None else [
                ('paper-1', '02323', 2020, 8, '1, 2, 3')])
        return path

    def audit(self, path):
        return exam_map.audit(self.data, syllabus_fixture(), path)

    def test_missing_map_fails_instead_of_skipping(self):
        (self.root / 'config/exam-map.json').unlink()
        status, output = self.run_main()
        self.assertEqual(1, status)
        self.assertIn('input error', output)
        self.assertFalse((self.root / 'artifacts').exists())

    def test_invalid_json_or_missing_syllabus_fails_cleanly(self):
        (self.root / 'config/exam-map.json').write_text('{broken', encoding='utf-8')
        self.assertEqual(1, self.run_main()[0])
        self.write_inputs()
        (self.root / 'config/syllabus.json').unlink()
        self.assertEqual(1, self.run_main()[0])

    def test_no_db_runs_map_only_and_publishes_report(self):
        with patch.object(sqlite3, 'connect', side_effect=AssertionError('unexpected bank')):
            status, output = self.run_main()
        self.assertEqual(0, status, output)
        self.assertIn('EXAM_DB 未指定', output)
        report = (self.root / 'artifacts/eval/exam-coverage.md').read_text(encoding='utf-8')
        self.assertIn('2020-08 起', report)

    def test_no_db_still_fails_structural_gate(self):
        question(self.data)['question_no'] = True
        self.write_inputs()
        status, output = self.run_main()
        self.assertEqual(1, status)
        self.assertIn('positive integer', output)

    def test_explicit_bad_path_directory_empty_or_corrupt_bank_fails(self):
        corrupt = self.root / 'corrupt.sqlite'
        corrupt.write_text('not a sqlite database', encoding='utf-8')
        empty = self.root / 'no-schema.sqlite'
        with closing(sqlite3.connect(empty)):
            pass
        missing = self.root / 'missing.sqlite'
        for path in (str(missing), str(self.root), '', str(corrupt), str(empty)):
            with self.subTest(path=path):
                status, output = self.run_main({'EXAM_DB': path})
                self.assertEqual(1, status, output)
                self.assertIn('EXAM_DB', output)
        self.assertFalse(missing.exists(), 'invalid DB path must not create a database')

    def test_temp_sqlite_uses_readonly_uri_and_closes_connection(self):
        path = self.create_bank()
        before = path.read_bytes()
        connect = sqlite3.connect
        opened = []

        def readonly_connect(database_uri, **kwargs):
            self.assertEqual(path.resolve().as_uri() + '?mode=ro', database_uri)
            self.assertTrue(kwargs.get('uri'))
            db = connect(database_uri, **kwargs)
            opened.append(db)
            with self.assertRaisesRegex(sqlite3.OperationalError, 'readonly'):
                db.execute('create table forbidden_write (id integer)')
            return db

        with patch.object(sqlite3, 'connect', side_effect=readonly_connect):
            result = self.audit(path)
        self.assertEqual([], result['errors'])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(1, len(opened))
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute('select 1')

    def test_sqlite_connection_also_closes_when_schema_query_fails(self):
        path = self.root / 'missing-schema.sqlite'
        with closing(sqlite3.connect(path)):
            pass
        connect = sqlite3.connect
        opened = []

        def tracking_connect(*args, **kwargs):
            db = connect(*args, **kwargs)
            opened.append(db)
            return db

        with patch.object(sqlite3, 'connect', side_effect=tracking_connect):
            result = self.audit(path)
        self.assertIn('no such table', '\n'.join(result['errors']))
        self.assertEqual(1, len(opened))
        with self.assertRaises(sqlite3.ProgrammingError):
            opened[0].execute('select 1')

    def test_bank_code_period_question_and_missing_paper_mismatches(self):
        for row, message in [
                (('paper-1', '13511', 2020, 8, '1'), 'paper code'),
                (('paper-1', '02323', 2021, 8, '1'), 'paper period'),
                (('paper-1', '02323', 'bad', 8, '1'), 'paper period'),
                (('paper-1', '02323', 2020, 8, '2, 3'), 'question 1'),
                (('paper-1', '02323', 2020, 8, None), 'question 1'),
                (('different-paper', '02323', 2020, 8, '1'), 'absent from EXAM_DB')]:
            with self.subTest(row=row):
                path = self.root / 'case.sqlite'
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute('drop table if exists papers')
                    db.execute('create table papers (id, code, year, month, question_numbers)')
                    db.execute('insert into papers values (?, ?, ?, ?, ?)', row)
                result = self.audit(path)
                self.assertIn(message, '\n'.join(result['errors']))

    def test_bank_without_13511_reports_degradation(self):
        path = self.create_bank()
        self.data = map_fixture('13511')
        paper(self.data)['paper_id'] = 'FJ-13511-202304'
        result = self.audit(path)
        self.assertEqual([], result['errors'])
        self.assertTrue(any('13511' in w and '降级' in w for w in result['warnings']))
        self.assertIn('13511：该课程无本地题库', result['report'])

    def test_cli_bank_mismatch_returns_failure(self):
        path = self.create_bank([('paper-1', '02323', 2020, 8, '9')])
        status, output = self.run_main({'EXAM_DB': str(path)})
        self.assertEqual(1, status)
        self.assertIn('question 1', output)


if __name__ == '__main__':
    unittest.main()
