"""Compare deterministic scientific outputs, intentionally excluding timings."""
import csv
import json
import sys
from pathlib import Path

SUMMARY_FILES = (
    'tests-summary.json',
    'provenance-summary.json',
    'memory-summary.json',
    'cover-summary.json',
    'stores-summary.json',
    'robustness-summary.json',
    'kernels-summary.json',
    'packets-summary.json',
)
CSV_FILES = ('kernels.csv', 'packets.csv')


def load(path):
    if not path.is_file():
        raise AssertionError(f'missing {path.name}')
    return json.loads(path.read_text(encoding='utf-8'))


def normalized_csv(path):
    if not path.is_file():
        raise AssertionError(f'missing {path.name}')
    with path.open(newline='', encoding='utf-8') as stream:
        return [
            {key: value for key, value in row.items() if not key.endswith('_seconds')}
            for row in csv.DictReader(stream)
        ]


def compare_directories(left, right):
    left, right = Path(left), Path(right)
    for name in SUMMARY_FILES:
        if load(left / name) != load(right / name):
            raise AssertionError(name)
    for path in sorted(left.glob('case-*.json')):
        peer = right / path.name
        if not peer.exists() or load(path) != load(peer):
            raise AssertionError(path.name)
    for name in CSV_FILES:
        if normalized_csv(left / name) != normalized_csv(right / name):
            raise AssertionError(f'{name} deterministic columns')


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: python compare.py EXPECTED REPRODUCED')
    compare_directories(Path(sys.argv[1]), Path(sys.argv[2]))
    print('MATCH: eight deterministic scientific summaries, all supplied cases, '
          'and all CSV result columns except timing.')


if __name__ == '__main__':
    main()
