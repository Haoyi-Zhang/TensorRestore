"""Same-program full-cost comparison on owned finite constructors.

The direct baseline shares schema/operation/lifetime/reachability parsing, but
uses no supplied restoration or flow witness. Its read test is separately written
and its exact peak optimizer constructs and solves its own residual network.
Neither path is native Halide/GPU validation or an independently authored verifier.
"""
import argparse
import copy
from collections import deque
import hashlib
import importlib.util
from itertools import product, combinations
import json
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from refcert.checker import structure, verify, Rejected
from refcert import producer
from refcert.interpreter import execute, source_values
from refcert.oracles import posets, orders
from refcert.kernels import build, compile_schedule
from refcert.packets import (build_residual_fan, compile_restoring_fan,
                            compile_quarantine_fan, compile_split_fan, edge_repair)


def direct_reads(state):
    pred = state['pred']
    for read, loc, want in state['reads']:
        writers = state['writes'].get(loc, [])
        good = [w for w, tag in writers if tag == want and (pred[read] >> w) & 1]
        if not good:
            raise Rejected('required source unavailable before read')
        # Unioning all correct predecessor downsets decides existence of a cover.
        # No heuristic/minimum-witness selection and no certificate input.
        covered = 0
        for good_writer in good:
            covered |= pred[good_writer]
        for writer, tag in writers:
            if writer != read and tag != want and not ((pred[writer] >> read) & 1):
                if not ((covered >> writer) & 1):
                    raise Rejected('possible wrong last writer')


def direct_peak(weights, edges):
    """Independent exact max-closure implementation, not producer/check_flow.

    BFS augmenting paths terminate at a residual cut; reversal handles rerouting.
    The fixed DAG has no antiparallel precedence arcs. Duplicate edges are sets.
    """
    n = len(weights)
    source, sink = n, n + 1
    positive = sum(max(0, w) for w in weights)
    residual = [dict() for _ in range(n + 2)]

    def arc(u, v, capacity):
        residual[u][v] = capacity
        residual[v].setdefault(u, 0)

    for v, w in enumerate(weights):
        if w > 0:
            arc(source, v, w)
        elif w < 0:
            arc(v, sink, -w)
    for u, v in sorted(set(map(tuple, edges))):
        arc(v, u, positive + 1)
    total_flow = 0
    while True:
        previous = {source: None}
        todo = deque([source])
        while todo and sink not in previous:
            u = todo.popleft()
            for v, capacity in residual[u].items():
                if capacity > 0 and v not in previous:
                    previous[v] = u
                    todo.append(v)
        if sink not in previous:
            return positive - total_flow
        amount = positive + 1
        v = sink
        while v != source:
            u = previous[v]
            amount = min(amount, residual[u][v])
            v = u
        v = sink
        while v != source:
            u = previous[v]
            residual[u][v] -= amount
            residual[v][u] += amount
            v = u
        total_flow += amount


def direct_verify(program, budget):
    state = structure(program)
    direct_reads(state)
    peak = state['persistent'] + direct_peak(state['weights'], program['edges'])
    if peak > budget:
        raise Rejected('memory budget not certified')
    return {'upper_cells': peak, 'exact_peak_cells': peak,
            'read_obligations': len(state['reads']), 'events': state['events'],
            'packet_events': state['packet_events'], 'packet_effects': state['packet_effects']}


def validate_direct():
    # Tiny complete universes test the new direct arithmetic independently of a
    # supplied witness. Exact trace/ideal replay is the reference, not producer.
    read_cases = weight_cases = 0
    for n in range(2, 5):
        for pred in posets(n):
            traces = orders(pred)
            edges = [[u, v] for v in range(n) for u in range(n) if pred[v] >> u & 1]
            ideals = [mask for mask in range(1 << n)
                      if all(not (mask >> v & 1) or not (pred[v] & ~mask) for v in range(n))]
            for weights in product((-2, 0, 3), repeat=n):
                exact = max(sum(weights[v] for v in range(n) if mask >> v & 1) for mask in ideals)
                if direct_peak(weights, edges) != exact:
                    raise AssertionError('direct peak differs from ideal enumeration')
                weight_cases += 1
            for read in range(n):
                others = [v for v in range(n) if v != read]
                for tags in product((-1, 0, 1), repeat=n - 1):
                    labels = dict(zip(others, tags))
                    for initial in (0, 1):
                        actual = True
                        for trace in traces:
                            current = initial
                            for v in trace:
                                if v == read:
                                    if current != 1:
                                        actual = False
                                    break
                                if labels[v] != -1:
                                    current = labels[v]
                            if not actual:
                                break
                        expanded = [0] + [1 | (p << 1) for p in pred]
                        writers = [(0, initial)] + [(v + 1, tag) for v, tag in labels.items() if tag != -1]
                        state = {'pred': expanded, 'reads': [(read + 1, (0, 0), 1)],
                                 'writes': {(0, 0): writers}}
                        try:
                            direct_reads(state)
                            got = True
                        except Rejected:
                            got = False
                        if got != actual:
                            raise AssertionError('direct read test differs from exact traces')
                        read_cases += 1
    return {'read_cases': read_cases, 'weight_cases': weight_cases, 'mismatches': 0}


def fixtures():
    for k in (2, 8, 32, 96, 192):
        source = build_residual_fan(k)
        shared = compile_restoring_fan(source)
        yield f'fan-{k}', shared
        yield f'quarantine-{k}', compile_quarantine_fan(source)
    for family in ('pointwise', 'separable', 'matmul'):
        for lanes in (1, 2):
            yield f'{family}-5-lanes-{lanes}', compile_schedule(build(family, 5), 'folded', lanes)


def measured(fn, repeats):
    samples = []
    answer = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        answer = fn()
        samples.append(time.perf_counter_ns() - start)
    return answer, samples


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--eager-producer', type=Path, required=True,
                    help='reviewed unmodified entry producer source, retained with results')
    ap.add_argument('--repeats', type=int, default=21)
    args = ap.parse_args()
    if not 3 <= args.repeats <= 101:
        ap.error('repeats must be 3..101')
    if args.out.exists() and any(args.out.iterdir()):
        ap.error('output directory must be new or empty')
    args.out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('refcert._eager_cost_baseline', args.eager_producer)
    eager = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eager)
    controls = validate_direct()
    records = []
    mismatches = negatives = 0
    for name, program in fixtures():
        cert, budget = producer.produce(program)
        old_cert, old_budget = eager.produce(program)
        expected = verify(program, cert, budget)
        if (cert, budget) != (old_cert, old_budget) or direct_verify(program, budget) != expected:
            raise AssertionError('full path or witness mismatch')
        inputs = [(i * 31 + 7) & ((1 << 32) - 1) for i in range(program['source']['inputs'])]
        output, peak = execute(program, inputs, structure(program)['order'])
        if output != source_values(program['source'], inputs) or peak > budget:
            raise AssertionError('numeric fixture mismatch')

        def pipeline(module):
            certificate, bound = module.produce(program)
            encoded = json.dumps(certificate, separators=(',', ':'))
            return verify(program, json.loads(encoded), bound)

        methods = {
            'eager_full': lambda: pipeline(eager),
            'lazy_full': lambda: pipeline(producer),
            'supplied_checker': lambda: verify(program, cert, budget),
            'direct_identifier': lambda: direct_verify(program, budget),
            'schema_and_reachability': lambda: structure(program),
        }
        # One untimed warm-up per method, then rotate method order each round.
        for fn in methods.values():
            fn()
        samples = {key: [] for key in methods}
        keys = list(methods)
        for round_id in range(args.repeats):
            for key in keys[round_id % len(keys):] + keys[:round_id % len(keys)]:
                _, elapsed = measured(methods[key], 1)
                samples[key].extend(elapsed)
        medians = {key: statistics.median(values) for key, values in samples.items()}
        row = {'name': name, 'origin': 'owned authored finite constructor',
               'program': program, 'certificate': cert, 'budget_cells': budget,
               'input': inputs, 'order': structure(program)['order'], 'output': output,
               'sampled_peak_cells': peak, 'checked': expected,
               'certificate_utf8_bytes': len(json.dumps(cert, separators=(',', ':')).encode()),
               'samples_ns': samples, 'median_ns': medians,
               'lazy_full_over_eager_full': medians['lazy_full'] / medians['eager_full'],
               'lazy_full_over_direct_identifier': medians['lazy_full'] / medians['direct_identifier'],
               'supplied_checker_over_direct_identifier': medians['supplied_checker'] / medians['direct_identifier']}
        records.append(row)
    # Ordinary missing-order controls on owned fans, not target vulnerability inputs.
    negative_records = []
    for k in (2, 8, 32):
        original = compile_restoring_fan(build_residual_fan(k))
        final = next(i for i, e in enumerate(original['events']) if e.get('dst') == [1, k])
        freed = next(i for i, e in enumerate(original['events']) if e.get('kind') == 'free')
        for restore in original['restores']:
            program = copy.deepcopy(original)
            program['edges'].remove([restore, final]); program['edges'].append([restore, freed])
            state = structure(program)
            cover = [[w for w, tag in state['writes'][loc] if tag == want and state['pred'][r] >> w & 1]
                     for r, loc, want in state['reads']]
            outcomes = []
            for fn in (lambda: verify(program, {'rescue': cover, 'flow': []}, state['persistent'] + 1),
                       lambda: direct_verify(program, state['persistent'] + 1)):
                try:
                    fn()
                    raise AssertionError('unsafe control accepted')
                except Rejected as error:
                    outcomes.append(str(error))
            if outcomes != ['possible wrong last writer'] * 2:
                raise AssertionError(outcomes)
            negative_records.append({'program': program, 'outcomes': outcomes})
            negatives += 1
    report = {'environment': {'os': platform.platform(), 'python': sys.version,
                             'optimization_level': sys.flags.optimize, 'timer': 'perf_counter_ns',
                             'timer_resolution_seconds': time.get_clock_info('perf_counter').resolution,
                             'rss': None, 'native_tensor_compiler': 'not executed', 'workers': 1},
              'source_bindings': {'eager_producer_sha256': digest(args.eager_producer),
                                  'lazy_producer_sha256': digest(ROOT / 'refcert/producer.py'),
                                  'checker_sha256': digest(ROOT / 'refcert/checker.py'),
                                  'experiment_sha256': digest(__file__)},
              'protocol': {'repeats': args.repeats, 'method_order': 'round-robin rotation',
                           'full_pipeline': 'produce including schema/closure; JSON serialization/parsing; verify including schema/closure',
                           'direct': 'same program/budget, shared schema/reachability; separately coded all-good coverage and exact peak optimizer; no supplied witness',
                           'trust': 'same guarantee on well-formed exact-tag finite DAGs; direct trusts its optimizer, checker trusts supplied feasible flow validation; shared front end not independent',
                           'origin': 'authored bounded test constructors, not observed production schedules'},
              'direct_exact_controls': controls, 'positive_configurations': len(records),
              'negative_controls': negatives, 'mismatches': mismatches,
              'records': records, 'negative_records': negative_records}
    (args.out / 'measurements.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'positive_configurations': len(records), 'negative_controls': negatives,
                      'direct_exact_controls': controls,
                      'ratios': [{k: r[k] for k in ('name', 'lazy_full_over_eager_full', 'lazy_full_over_direct_identifier', 'supplied_checker_over_direct_identifier')}
                                 for r in records]}, indent=2))


if __name__ == '__main__':
    main()
