"""Owned file/metadata and arithmetic controls; separate from historical 39 tests."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from compare import SUMMARY_FILES, CSV_FILES, compare_directories


class WorkflowRegression(unittest.TestCase):
    def test_portable_public_runner(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'results'
            proc = subprocess.run([sys.executable, '-B', str(ROOT / 'run.py'),
                                   '--suite', 'tests', '--resource-backend', 'portable',
                                   '--out', str(output)], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            report = json.loads((output / 'run-summary.json').read_text())
            self.assertIsNone(report['main_process_peak_rss'])
            self.assertIsNone(report['completed_cli_child_cpu_seconds'])
            self.assertIsNone(report['accounted_cpu_seconds'])
            self.assertIsNone(report['resource_limits']['cpu_limit_seconds_per_process'])

    def test_optimized_closure_regression_exposes_wrong_peak(self):
        # Ordinary arithmetic mutation, not an input attack: a test double returns
        # peak 1 for an empty graph whose exact ideal maximum is zero.
        code = ("import importlib.util; "
                f"s=importlib.util.spec_from_file_location('closure_regression', {str(ROOT / 'tests/closure_regression.py')!r}); "
                "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                "Fake=type('Fake',(),{'maximum_closure':staticmethod(lambda w,e:([],[],1))}); "
                "m.checked_closure(Fake,(),[])")
        proc = subprocess.run([sys.executable, '-B', '-O', '-c', code],
                              capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0, 'wrong peak escaped optimized checks')
        self.assertIn('AssertionError', proc.stderr)

    def test_extra_case_is_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            left, right = (Path(temporary) / name for name in ('left', 'right'))
            left.mkdir(); right.mkdir()
            for root in (left, right):
                for name in SUMMARY_FILES:
                    (root / name).write_text('{}', encoding='utf-8')
                for name in CSV_FILES:
                    (root / name).write_text('case,value\na,1\n', encoding='utf-8')
            (right / 'case-extra.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(AssertionError, 'case file set'):
                compare_directories(left, right)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / 'owned.txt'
            marker.write_text('keep', encoding='utf-8')
            proc = subprocess.run([sys.executable, '-B', str(ROOT / 'run.py'),
                                   '--suite', 'tests', '--resource-backend', 'portable',
                                   '--out', temporary], capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(marker.read_text(), 'keep')
            self.assertEqual(list(Path(temporary).iterdir()), [marker])


if __name__ == '__main__':
    unittest.main(verbosity=2)
