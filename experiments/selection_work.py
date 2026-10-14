"""Exact candidate-intersection counts on owned fans; no time inference."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from refcert import producer
from refcert.checker import structure
from refcert.packets import build_residual_fan, compile_restoring_fan

class Mask(int):
    calls = 0
    def __and__(self, value):
        type(self).calls += 1
        return int(self) & value

def count(module, program):
    state = structure(program)
    state['pred'] = [Mask(p) for p in state['pred']]
    Mask.calls = 0
    with patch.object(module, 'structure', return_value=state):
        answer = module.produce(program)
    return answer, Mask.calls

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--eager-producer', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        ap.error('output already exists')
    spec = importlib.util.spec_from_file_location('refcert._eager_selection', args.eager_producer)
    eager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eager)
    rows = []
    for k in (2, 8, 32, 96, 192):
        program = compile_restoring_fan(build_residual_fan(k))
        old, old_calls = count(eager, program)
        current, current_calls = count(producer, program)
        if old != current or current_calls != 5*k+3:
            raise AssertionError(('selection work/equivalence', k, old_calls, current_calls))
        rows.append({'branches': k, 'eager_intersections': old_calls,
                     'lazy_intersections': current_calls, 'certificates_and_bounds_identical': True})
    report = {'origin': 'owned authored residual-fan constructors',
              'optimization_level': sys.flags.optimize,
              'count_scope': 'pred[good] & remaining_bad in all producer read obligations; excludes schema/heap/closure/checker/JSON',
              'rows': rows}
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
