"""Emit a small paper table from retained same-information measurements."""
import argparse
import json
from pathlib import Path

SELECTED = (('fan-2','Fan, 2'), ('fan-32','Fan, 32'), ('fan-192','Fan, 192'),
            ('separable-5-lanes-1','Separable, 1 lane'))

def table(report):
    if report['mismatches'] or report['positive_configurations'] != 16:
        raise ValueError('incomplete or disagreeing measurement report')
    records = {r['name']:r for r in report['records']}
    if len(records) != len(report['records']):
        raise ValueError('duplicate fixture')
    lines = [r'\begin{tabular}{lrrrr}', r'\toprule',
             r'Instance & Eager full & Lazy full & Supplied check & Direct\\', r'\midrule']
    for key, label in SELECTED:
        r = records[key]
        values = [r['median_ns'][method] / 1e6
                  for method in ('eager_full','lazy_full','supplied_checker','direct_identifier')]
        lines.append(label + ' & ' + ' & '.join(f'{v:.3f}' for v in values) + r'\\')
    return '\n'.join(lines + [r'\bottomrule',r'\end{tabular}']) + '\n'

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--measurements', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        ap.error('table output already exists')
    args.out.write_text(table(json.loads(args.measurements.read_text(encoding='utf-8'))), encoding='utf-8')

if __name__ == '__main__':
    main()
