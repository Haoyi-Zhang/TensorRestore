import csv
import json
import tempfile
import unittest
from pathlib import Path

from compare import CSV_FILES, SUMMARY_FILES, compare_directories


class DeterministicComparison(unittest.TestCase):
    def fixture(self):
        temporary=tempfile.TemporaryDirectory()
        root=Path(temporary.name);left=root/'left';right=root/'right'
        left.mkdir();right.mkdir()
        for name in SUMMARY_FILES:
            payload={'summary':name,'nested':{'count':3,'ok':True}}
            (left/name).write_text(json.dumps(payload),encoding='utf-8')
            (right/name).write_text(json.dumps(payload),encoding='utf-8')
        case={'program':{'events':[0,1]},'accepted':True}
        for directory in (left,right):
            (directory/'case-example.json').write_text(json.dumps(case),encoding='utf-8')
        for name in CSV_FILES:
            with (left/name).open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=['case','value','worker_cpu_seconds'])
                writer.writeheader();writer.writerow({'case':'a','value':'9','worker_cpu_seconds':'1.0'})
            with (right/name).open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=['case','value','worker_cpu_seconds'])
                writer.writeheader();writer.writerow({'case':'a','value':'9','worker_cpu_seconds':'2.0'})
        return temporary,left,right

    def test_matching_fixture_compares_eight_summaries_cases_and_csv(self):
        temporary,left,right=self.fixture()
        try:compare_directories(left,right)
        finally:temporary.cleanup()

    def test_missing_cover_summary_fails(self):
        temporary,left,right=self.fixture()
        try:
            (right/'cover-summary.json').unlink()
            with self.assertRaisesRegex(AssertionError,'missing cover-summary.json'):
                compare_directories(left,right)
        finally:temporary.cleanup()

    def test_tampered_robustness_field_fails(self):
        temporary,left,right=self.fixture()
        try:
            payload=json.loads((right/'robustness-summary.json').read_text())
            payload['nested']['count']=4
            (right/'robustness-summary.json').write_text(json.dumps(payload),encoding='utf-8')
            with self.assertRaisesRegex(AssertionError,'robustness-summary.json'):
                compare_directories(left,right)
        finally:temporary.cleanup()

    def test_case_and_non_timing_csv_changes_fail(self):
        temporary,left,right=self.fixture()
        try:
            case=json.loads((right/'case-example.json').read_text());case['accepted']=False
            (right/'case-example.json').write_text(json.dumps(case),encoding='utf-8')
            with self.assertRaisesRegex(AssertionError,'case-example.json'):
                compare_directories(left,right)
            (right/'case-example.json').write_text((left/'case-example.json').read_text(),encoding='utf-8')
            rows=list(csv.DictReader((right/'kernels.csv').open(newline='',encoding='utf-8')))
            rows[0]['value']='10'
            with (right/'kernels.csv').open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(AssertionError,'kernels.csv deterministic columns'):
                compare_directories(left,right)
        finally:temporary.cleanup()


if __name__=='__main__':unittest.main()
