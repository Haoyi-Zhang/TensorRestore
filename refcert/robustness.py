"""Black-box, metamorphic, mutation-sensitivity, and held-out audits."""
import copy
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from .checker import structure, verify, Rejected
from .producer import produce, maximum_closure
from .interpreter import execute, MASK
from .examples import packet_cross_read_program
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


def _sequential_packet_commit_mutant(program, inputs):
    """Test-only local mutant: commit packet effects one by one."""
    order = structure(program)['order']
    memory = {0: [value & MASK for value in inputs],
              1: [None] * len(program['source']['outputs'])}

    def load(location):
        buffer_id, slot = location
        if (buffer_id not in memory or not 0 <= slot < len(memory[buffer_id])
                or memory[buffer_id][slot] is None):
            raise ValueError('invalid or uninitialized target read')
        return memory[buffer_id][slot]

    def evaluate(effect):
        if effect['kind'] == 'copy':
            return load(effect['src'])
        args = [load(location) for location in effect['args']]
        op = effect['op']
        if op == 'const':
            value = effect['literal']
        elif op == 'add':
            value = args[0] + args[1]
        elif op == 'sub':
            value = args[0] - args[1]
        elif op == 'mul':
            value = args[0] * args[1]
        elif op == 'xor':
            value = args[0] ^ args[1]
        else:
            raise ValueError('unknown target operator')
        return value & MASK

    result = None
    for event_id in order:
        event = program['events'][event_id]
        kind = event['kind']
        if kind == 'entry':
            continue
        if kind == 'alloc':
            memory[event['buffer']] = [None] * program['buffers'][event['buffer']]['cells']
        elif kind == 'free':
            del memory[event['buffer']]
        elif kind in ('copy', 'eval'):
            buffer_id, slot = event['dst']
            memory[buffer_id][slot] = evaluate(event)
        elif kind == 'packet':
            for effect in event['effects']:
                buffer_id, slot = effect['dst']
                memory[buffer_id][slot] = evaluate(effect)
        elif kind == 'exit':
            result = [load([1, slot]) for slot in range(len(memory[1]))]
        else:
            raise ValueError('unknown target event')
    return result


def _packet_snapshot_semantics():
    inputs = [7, 19]
    expected = [7]
    variants = []
    for reverse_effects in (False, True):
        program = packet_cross_read_program(initialized=True)
        if reverse_effects:
            program['events'][program['packet_event']]['effects'].reverse()
        certificate, budget = produce(program)
        verify(program, certificate, budget)
        output, _ = execute(program, inputs, structure(program)['order'])
        if output != expected:
            raise AssertionError(('packet snapshot output', reverse_effects, output))
        variants.append(output)
    if variants[0] != variants[1]:
        raise AssertionError('packet effect permutation changed snapshot result')

    initialized = packet_cross_read_program(initialized=True)
    sequential_output = _sequential_packet_commit_mutant(initialized, inputs)
    if sequential_output != [19] or sequential_output == expected:
        raise AssertionError(('sequential packet mutant was not exposed', sequential_output))

    uninitialized = packet_cross_read_program(initialized=False)
    try:
        produce(uninitialized)
    except Rejected as error:
        producer_rejection = str(error)
    else:
        raise AssertionError('same-packet source incorrectly accepted')
    if producer_rejection != 'required source unavailable before read':
        raise AssertionError(('unexpected uninitialized rejection', producer_rejection))
    try:
        execute(uninitialized, inputs, structure(uninitialized)['order'])
    except ValueError as error:
        numeric_rejection = str(error)
    else:
        raise AssertionError('snapshot interpreter read uninitialized packet source')
    if numeric_rejection != 'invalid or uninitialized target read':
        raise AssertionError(('unexpected numeric rejection', numeric_rejection))
    if _sequential_packet_commit_mutant(uninitialized, inputs) != [19]:
        raise AssertionError('sequential mutant did not consume same-packet write')

    return {
        'initialized_effect_orders_checked': 2,
        'snapshot_outputs': variants,
        'effect_order_mismatches': 0,
        'sequential_commit_mutants_exposed': 1,
        'sequential_mutant_output': sequential_output,
        'uninitialized_same_packet_source_rejected_by_producer': True,
        'uninitialized_same_packet_source_rejected_by_snapshot_interpreter': True,
    }


def _mutation_sensitivity():
    import refcert.checker as checker
    from .examples import restoring_diamond, unsafe_diamond

    safe = restoring_diamond()
    safe_certificate, _ = produce(safe)
    unsafe = unsafe_diamond()
    state = structure(unsafe)
    rescue = copy.deepcopy(safe_certificate['rescue'])
    final_read_row = next(
        index for index, (read_event, location, want) in enumerate(state['reads'])
        if read_event == 7 and location == (2, 0) and want == 0
    )
    # Writer 6 is a valid good predecessor of the read but does not follow bad
    # writer 3.  Every supplied restorer is therefore legal; only coverage fails.
    rescue[final_read_row] = [6]
    flow, ideal, scratch_peak = maximum_closure(state['weights'], unsafe['edges'])
    certificate = {'rescue': rescue, 'flow': flow, 'peak_ideal': ideal}
    budget = state['persistent'] + scratch_peak
    try:
        verify(unsafe, certificate, budget)
    except Rejected as error:
        original_rejection = str(error)
    else:
        raise AssertionError('focused missing-coverage certificate was accepted')
    if original_rejection != 'possible wrong last writer':
        raise AssertionError(('negative control failed for the wrong reason',
                              original_rejection))

    original = checker.check_read_cover
    try:
        def missing_coverage_mutant(pred, writers, read_event, want, chosen):
            checker.require(type(chosen) is list and len(chosen) <= len(pred),
                            'rescue set shape')
            tagged = dict(writers)
            good = [writer for writer, tag in tagged.items()
                    if tag == want and pred[read_event] >> writer & 1]
            checker.require(bool(good), 'required source unavailable before read')
            seen = set()
            for writer in chosen:
                checker.integer(writer, 0, len(pred) - 1)
                checker.require(writer not in seen and writer in tagged
                                and tagged[writer] == want
                                and pred[read_event] >> writer & 1,
                                'invalid restoring writer')
                seen.add(writer)
            # Deliberate mutation: omit only the bad-writer coverage loop.
            return len(good), len(seen)

        checker.check_read_cover = missing_coverage_mutant
        verify(unsafe, certificate, budget)
        mutant_accepts = True
    except Rejected:
        mutant_accepts = False
    finally:
        checker.check_read_cover = original
    if not mutant_accepts:
        raise AssertionError('focused missing-coverage mutant was not exposed')
    return {
        'focused_missing_coverage_mutants': 1,
        'all_supplied_restorers_legal': True,
        'original_rejection': original_rejection,
        'mutant_acceptances': 1,
    }


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
            'packet_snapshot_semantics': _packet_snapshot_semantics(),
            'mutation_sensitivity': _mutation_sensitivity(),
            'heldout_provenance': _heldout_provenance()}
