"""Owned greedy-equivalence and work controls; not production workload evidence."""
from itertools import combinations
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from refcert import producer
from refcert.checker import structure, Rejected
from refcert.packets import build_residual_fan, compile_restoring_fan


def eager_cover(pred, bad, good):
    good = list(good)
    chosen = []
    while bad:
        g = max(good, key=lambda x: ((pred[x] & bad).bit_count(), -x), default=None)
        if g is None or not (pred[g] & bad):
            raise Rejected('no restoring-writer cover')
        chosen.append(g)
        bad &= ~pred[g]
        good.remove(g)
    return chosen


class CountingMask(int):
    intersections = 0

    def __and__(self, other):
        type(self).intersections += 1
        return int(self) & other


class RestorationRegression(unittest.TestCase):
    def test_fan_does_not_rescan_every_candidate_at_every_selection(self):
        program = compile_restoring_fan(build_residual_fan(192))
        state = structure(program)
        state['pred'] = [CountingMask(value) for value in state['pred']]
        CountingMask.intersections = 0
        with patch.object(producer, 'structure', return_value=state):
            certificate, _ = producer.produce(program)
        self.assertEqual(max(map(len, certificate['rescue'])), 192)
        # Final read: k+1 initial scores and 2k heap rescoring calls.
        # Each of k+1 output reads has one candidate: two calls per read.
        # Total = (3k+1) + (2k+2), with no calls for already-clean input reads.
        self.assertEqual(CountingMask.intersections, 5 * 192 + 3)

    def test_every_small_cover_retains_eager_selection_and_ties(self):
        # Complete covering families on 1..4 abstract elements with <=5 distinct
        # nonempty sets. This isolates greedy selection, not JSON admission.
        count = 0
        for n in range(1, 5):
            full = (1 << n) - 1
            for width in range(1, min(5, full) + 1):
                for sets in combinations(range(1, full + 1), width):
                    union = 0
                    for mask in sets:
                        union |= mask
                    if union != full:
                        continue
                    pred = [0] * n + list(sets)
                    good = list(range(n, len(pred)))
                    self.assertEqual(producer.greedy_cover(pred, full, good),
                                     eager_cover(pred, full, good))
                    count += 1
        self.assertEqual(count, 4612)

    def test_nonminimal_greedy_result_is_retained(self):
        sets = (15, 19, 44, 16, 32)
        pred = [0] * 6 + list(sets)
        self.assertEqual(producer.greedy_cover(pred, 63, list(range(6, 11))), [6, 7, 8])

    def test_empty_and_uncoverable_obligations(self):
        self.assertEqual(producer.greedy_cover([0], 0, []), [])
        with self.assertRaisesRegex(Rejected, 'no restoring-writer cover'):
            producer.greedy_cover([0, 1], 3, [1])


if __name__ == '__main__':
    unittest.main(verbosity=2)
