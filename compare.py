"""Compare deterministic scientific outputs, intentionally excluding timings."""
import csv
import json
import sys
from pathlib import Path

SUMMARY_FILES = (
    'tests-summary.json',
    'provenance-summary.json',
    'memory-summary.json',
    'stores-summary.json',
    'kernels-summary.json',
    'packets-summary.json',
)
CSV_FILES = ('kernels.csv', 'packets.csv')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def normalized_csv(path):
    with path.open(newline='', encoding='utf-8') as stream:
        return [
            {key: value for key, value in row.items() if not key.endswith('_seconds')}
            for row in csv.DictReader(stream)
        ]


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: python compare.py EXPECTED REPRODUCED')
    left, right = map(Path, sys.argv[1:])
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
    print('MATCH: deterministic summaries, all supplied cases, and all CSV result columns except timing.')


if __name__ == '__main__':
    main()
