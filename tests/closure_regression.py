"""File-free focused regressions, run separately from the retained campaign suite.

The reference enumerates ideals directly from precedence edges. It neither builds
a flow network nor imports a historical producer. No timing or external jobs.
"""
import copy
from itertools import combinations, permutations, product
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from refcert import checker, producer
from refcert.examples import restoring_diamond, packet_cross_read_program
from refcert.kernels import FAMILIES, build, compile_schedule
from refcert.packets import (build_residual_fan, compile_restoring_fan,
                            compile_quarantine_fan, compile_private_fan,
                            compile_forwarded_fan, compile_split_fan, edge_repair)


def ideal_peak(weights, edges):
    ideals = [tuple(v for v in range(len(weights)) if mask >> v & 1)
              for mask in range(1 << len(weights))
              if all(not (mask >> v & 1) or mask >> u & 1 for u, v in edges)]
    return max(sum(weights[v] for v in ideal) for ideal in ideals), ideals


def forward_graphs(n):
    pairs = tuple(combinations(range(n), 2))
    for mask in range(1 << len(pairs)):
        yield [list(edge) for i, edge in enumerate(pairs) if mask >> i & 1]


def tiny_posets(n):
    """Deduplicate reachability using per-vertex graph walks, not checker bitsets."""
    relations = set()
    for edges in forward_graphs(n):
        successors = {v: [] for v in range(n)}
        for u, v in edges:
            successors[u].append(v)
        relation = set()
        for u in range(n):
            todo = list(successors[u])
            seen = set()
            while todo:
                v = todo.pop()
                if v not in seen:
                    seen.add(v)
                    todo.extend(successors[v])
            relation.update((u, v) for v in seen)
        relations.add(tuple(sorted(relation)))
    return sorted(relations)


def residual_fixtures():
    return (
        ((), []), ((0,), []), ((3,), []), ((-2,), []),
        ((-2, 3), [[0, 1]]), ((3, -2), [[0, 1]]),
        ((-2, 0, 3), [[0, 1], [1, 2]]),
        ((-2, 3, 3), [[0, 1], [0, 2]]),
        ((-1, -1, 1, 1), [[0, 2], [1, 2], [0, 3]]),
        ((-2, 3, -2, 3), [[0, 1], [2, 3]]),
        ((-2, 3, 0), [[0, 1], [0, 1], [1, 2]]),
        ((-10**11, 10**11, 0), [[0, 1], [1, 2]]),
    )


def program_fixtures():
    yield restoring_diamond()
    yield packet_cross_read_program(initialized=True)
    for family in FAMILIES:
        for layout in ('tiled', 'folded'):
            yield compile_schedule(build(family, 2), layout, 1)
    for branches in (2, 3, 4):
        source = build_residual_fan(branches)
        shared = compile_restoring_fan(source)
        yield shared
        yield edge_repair(shared)
        for compile_fan in (compile_quarantine_fan, compile_private_fan,
                            compile_forwarded_fan, compile_split_fan):
            yield compile_fan(source)


def checked_closure(module, weights, edges):
    flow, ideal, peak = module.maximum_closure(weights, edges)
    exact, ideals = ideal_peak(weights, edges)
    assert peak == exact and tuple(ideal) in ideals
    assert checker.check_flow(weights, edges, flow) == exact
    return flow, ideal, peak


class ClosureRegression(unittest.TestCase):
    def test_all_forward_graphs_and_signed_weights_through_four(self):
        count = 0
        for n in range(1, 5):
            for edges in forward_graphs(n):
                for weights in product((-2, 0, 3), repeat=n):
                    checked_closure(producer, weights, edges)
                    count += 1
        self.assertEqual(count, 5421)

    def test_relabeling_and_duplicate_edges(self):
        count = 0
        for labels in permutations(range(4)):
            for edges in forward_graphs(4):
                renamed = [[labels[u], labels[v]] for u, v in edges]
                weights = (-2, 3, 0, -2)
                plain = checked_closure(producer, weights, renamed)
                self.assertEqual(plain, checked_closure(producer, weights, renamed + renamed))
                count += 1
        self.assertEqual(count, 1536)

    def test_residual_reverse_arc_and_finite_boundaries(self):
        for weights, edges in residual_fixtures():
            original = copy.deepcopy((weights, edges))
            checked_closure(producer, weights, edges)
            self.assertEqual((weights, edges), original)
        flow, ideal, peak = producer.maximum_closure((-1, -1, 1, 1), [[0, 2], [1, 2], [0, 3]])
        self.assertEqual(flow, [[0, 5, 1], [1, 5, 1], [2, 1, 1],
                                [3, 0, 1], [4, 2, 1], [4, 3, 1]])
        self.assertEqual((ideal, peak), ([], 0))

    def test_consumer_certificates_and_stats(self):
        count = 0
        for program in program_fixtures():
            certificate, budget = producer.produce(program)
            result = checker.verify(program, certificate, budget)
            self.assertEqual(result['upper_cells'], budget)
            self.assertEqual(result['exact_peak_cells'], budget)
            with self.assertRaises(checker.Rejected):
                checker.verify(program, certificate, budget - 1)
            count += 1
        self.assertEqual(count, 36)

    def test_independent_flow_checks_still_reject_forgery(self):
        weights, edges = (-2, 3), [[0, 1]]
        flow, _, _ = producer.maximum_closure(weights, edges)
        bad = copy.deepcopy(flow)
        bad[0][2] += 1
        for forged in (bad, flow + flow[:1], flow[:-1], [[0, 1, 1]]):
            with self.assertRaises(checker.Rejected):
                checker.check_flow(weights, edges, forged)
        with self.assertRaises(checker.Rejected):
            checker.graph(2, [[0, 1], [1, 0]])

    def test_schema_caps_and_optional_tightness_are_preserved(self):
        program = restoring_diamond()
        certificate, budget = producer.produce(program)
        for mutation in ('cells', 'events', 'edges', 'bool_budget', 'ideal'):
            p, c, b = copy.deepcopy(program), copy.deepcopy(certificate), budget
            if mutation == 'cells': p['buffers'][2]['cells'] = 10001
            elif mutation == 'events': p['events'] += [{'kind': 'entry'}] * 2500
            elif mutation == 'edges': p['edges'] += [[0, 1]] * 20001
            elif mutation == 'bool_budget': b = True
            else: c['peak_ideal'] = []
            with self.assertRaises(checker.Rejected):
                checker.verify(p, c, b)


if __name__ == '__main__':
    unittest.main(verbosity=2)
