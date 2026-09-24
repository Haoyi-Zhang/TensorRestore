"""Black-box, metamorphic, mutation-sensitivity, and held-out audits."""
import copy
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from .checker import structure, verify, Rejected
from .producer import produce
from .packets import build_residual_fan, compile_restoring_fan
from .oracles import closure, orders, production_prediction


def _rename_program_and_certificate(program, certificate):
    n = len(program['events'])
    internal = list(range(1, n - 1))[::-1]
    old_to_new = {0: 0, n - 1: n - 1}
    old_to_new.update({old: new for new, old in enumerate(internal, 1)})
    events = [None] * n
    for old, event in enumerate(program['events']):
        events[old_to_new[old]] = copy.deepcopy(event)
    renamed = copy.deepcopy(program)
    renamed['events'] = events
    renamed['edges'] = [[old_to_new[u], old_to_new[v]]
                        for u, v in program['edges']]
    for key in ('packets', 'restores'):
        if key in renamed:
            renamed[key] = [old_to_new[i] for i in program[key]]
    cert = copy.deepcopy(certificate)
    cert['rescue'] = [[old_to_new[i] for i in row]
                      for row in certificate['rescue']]
    cert['peak_ideal'] = [old_to_new[i]
                          for i in certificate.get('peak_ideal', [])]
    cert['flow'] = [[old_to_new.get(u, u), old_to_new.get(v, v), amount]
                    for u, v, amount in certificate['flow']]
    return renamed, cert


def _metamorphic_audit():
    program = compile_restoring_fan(build_residual_fan(3))
    certificate, budget = produce(program)
    baseline = verify(program, certificate, budget)
    checks = 0

    shuffled = copy.deepcopy(program)
    rng = random.Random(404)
    rng.shuffle(shuffled['edges'])
    shuffled_certificate = copy.deepcopy(certificate)
    for row in shuffled_certificate['rescue']:
        row.reverse()
    shuffled_certificate['flow'].reverse()
    if verify(shuffled, shuffled_certificate, budget) != baseline:
        raise AssertionError('edge/certificate order changed verdict')
    checks += 1

    redundant = copy.deepcopy(program)
    pred = structure(program)['pred']
    existing = {tuple(edge) for edge in program['edges']}
    extra = next([u, v] for v in range(len(pred)) for u in range(len(pred))
                 if pred[v] >> u & 1 and (u, v) not in existing)
    redundant['edges'].append(extra)
    if verify(redundant, certificate, budget) != baseline:
        raise AssertionError('transitive edge changed verdict')
    checks += 1

    renamed, _ = _rename_program_and_certificate(program, certificate)
    renamed_certificate, renamed_budget = produce(renamed)
    renamed_verdict = verify(renamed, renamed_certificate, renamed_budget)
    stable_keys = ('upper_cells', 'exact_peak_cells', 'read_obligations',
                   'events', 'packet_events', 'packet_effects')
    if renamed_budget != budget or any(renamed_verdict[k] != baseline[k]
                                       for k in stable_keys):
        raise AssertionError('alpha-renaming changed verdict')
    checks += 1

    round_trip = json.loads(json.dumps(program, sort_keys=True))
    round_cert = json.loads(json.dumps(certificate, sort_keys=True))
    if verify(round_trip, round_cert, budget) != baseline:
        raise AssertionError('JSON key order changed verdict')
    checks += 1
    return {'checks': checks, 'mismatches': 0}


def _black_box_audit():
    root = Path(__file__).resolve().parents[1]
    cases = []
    with tempfile.TemporaryDirectory() as temporary:
        temporary = Path(temporary)
        bad_json = temporary / 'bad.json'
        bad_json.write_text('{not-json', encoding='utf-8')
        cases.append(bad_json)

        program = compile_restoring_fan(build_residual_fan(2))
        certificate, budget = produce(program)
        cyclic = copy.deepcopy(program)
        cyclic['edges'].append([len(cyclic['events']) - 1, 0])
        cycle_case = temporary / 'cycle.json'
        cycle_case.write_text(json.dumps({'program': cyclic,
                                          'certificate': certificate,
                                          'budget_cells': budget}),
                              encoding='utf-8')
        cases.append(cycle_case)

        malformed = temporary / 'malformed.json'
        malformed.write_text(json.dumps({'program': program,
                                          'certificate': {'rescue': []},
                                          'budget_cells': budget}),
                             encoding='utf-8')
        cases.append(malformed)

        accepted = temporary / 'accepted.json'
        accepted.write_text(json.dumps({'program': program,
                                         'certificate': certificate,
                                         'budget_cells': budget}),
                            encoding='utf-8')

        rejected = 0
        for case in cases:
            proc = subprocess.run(
                [sys.executable, '-m', 'refcert', 'check', str(case)],
                cwd=root, text=True, capture_output=True, timeout=15)
            if (proc.returncode == 0 or 'Traceback' in proc.stderr or
                    'Traceback' in proc.stdout):
                raise AssertionError(('black-box rejection failure',
                                      case.name, proc.returncode,
                                      proc.stdout, proc.stderr))
            payload = json.loads(proc.stdout)
            if payload.get('accepted') is not False:
                raise AssertionError(('malformed public response',
                                      case.name, payload))
            rejected += 1
        proc = subprocess.run(
            [sys.executable, '-m', 'refcert', 'check', str(accepted)],
            cwd=root, text=True, capture_output=True, timeout=15)
        if (proc.returncode != 0 or
                json.loads(proc.stdout).get('accepted') is not True):
            raise AssertionError(('black-box acceptance failure',
                                  proc.stdout, proc.stderr))
    return {'accepted_cases': 1, 'cleanly_rejected_cases': rejected,
            'tracebacks': 0}


def _mutation_sensitivity():
    import refcert.checker as checker
    from .examples import restoring_diamond, unsafe_diamond

    safe = restoring_diamond()
    certificate, budget = produce(safe)
    unsafe = unsafe_diamond()
    try:
        verify(unsafe, certificate, budget)
    except Rejected:
        original_rejected = True
    else:
        original_rejected = False
    if not original_rejected:
        raise AssertionError('negative control not rejected by original predicate')

    original = checker.check_read_cover
    try:
        def mutant(pred, writers, read_event, want, chosen):
            if not any(tag == want and pred[read_event] >> writer & 1
                       for writer, tag in writers):
                raise Rejected('required source unavailable before read')
            return 1, len(chosen)
        checker.check_read_cover = mutant
        verify(unsafe, certificate, budget)
        mutant_accepts_unsafe = True
    except Rejected:
        mutant_accepts_unsafe = False
    finally:
        checker.check_read_cover = original
    if not mutant_accepts_unsafe:
        raise AssertionError('mutation was not exposed by negative control')
    return {'mutants': 1, 'detected_by_negative_control': 1}


def _heldout_provenance():
    rng = random.Random(8675309)
    cases = mismatches = order_replays = 0
    graph_count = 0
    while graph_count < 96:
        n = 6
        probability = 0.18 + 0.44 * rng.random()
        edges = [(u, v) for u in range(n) for v in range(u + 1, n)
                 if rng.random() < probability]
        p = closure(n, edges)
        traces = orders(p)
        if len(traces) > 720:
            continue
        graph_count += 1
        for _ in range(12):
            read = rng.randrange(n)
            labels = [rng.choice((-1, 0, 1)) for _ in range(n)]
            labels[read] = -1
            initial = rng.randrange(2)
            actual = True
            for trace in traces:
                value = initial
                for event in trace:
                    if event == read:
                        if value != 1:
                            actual = False
                        break
                    if labels[event] != -1:
                        value = labels[event]
                order_replays += 1
                if not actual:
                    break
            predicted = production_prediction(p, read, labels, initial)
            cases += 1
            if actual != predicted:
                mismatches += 1
                raise AssertionError(('held-out provenance mismatch', p, read,
                                      labels, initial))
    return {'seed': 8675309, 'event_count': 6, 'graphs': graph_count,
            'cases': cases, 'linear_extension_replays': order_replays,
            'mismatches': mismatches,
            'role': ('frozen post-formulation implementation holdout; '
                     'not workload breadth')}


def robustness_audit():
    return {'metamorphic': _metamorphic_audit(),
            'black_box_cli': _black_box_audit(),
            'mutation_sensitivity': _mutation_sensitivity(),
            'heldout_provenance': _heldout_provenance()}
