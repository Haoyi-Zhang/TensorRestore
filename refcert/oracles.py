"""Exhaustive finite oracles. Counts describe generated models, not workloads.

The semantic enumerators do not call the certificate producer. The provenance
campaign compares exact last-writer execution with both the theorem formula and
the production read-cover predicate. The maximum-closure campaign compares
exact ideal enumeration with the producer/checker flow pair.
"""
import itertools
from .producer import maximum_closure
from .checker import check_flow, check_read_cover, Rejected


def closure(n, edges):
    p = [0] * n
    for u, v in edges:
        p[v] |= 1 << u
    for k in range(n):
        for v in range(n):
            if p[v] >> k & 1:
                p[v] |= p[k]
    return tuple(p)


def posets(n):
    edges = list(itertools.combinations(range(n), 2))
    return sorted({closure(n, [e for i, e in enumerate(edges) if m >> i & 1])
                   for m in range(1 << len(edges))})


def orders(p):
    n = len(p)
    full = (1 << n) - 1

    def rec(mask, seq):
        if mask == full:
            yield tuple(seq)
            return
        for u in range(n):
            if not (mask >> u & 1) and not (p[u] & ~mask):
                yield from rec(mask | 1 << u, seq + [u])

    return list(rec(0, []))


def rescue_rule(p, r, labels, initial):
    """Independent direct transcription of the exact read condition."""
    good = [g for g, x in enumerate(labels)
            if x == 1 and g != r and p[r] >> g & 1]
    if initial == 1:
        good.append(-1)
    if not good:
        return False
    for w, x in enumerate(labels):
        if x != 0 or w == r:
            continue
        if p[w] >> r & 1:
            continue
        if not any(g != -1 and p[g] >> w & 1 for g in good):
            return False
    if initial != 1 and not any(g != -1 for g in good):
        return False
    return True


def production_prediction(p, r, labels, initial):
    """Invoke the shipped read-cover predicate with an explicit init event."""
    n = len(p)
    pred = [0] * (n + 1)
    for v in range(n):
        pred[v + 1] = 1 | sum(1 << (u + 1) for u in range(n)
                              if p[v] >> u & 1)
    writers = [(0, initial)] + [(w + 1, tag)
                                for w, tag in enumerate(labels)
                                if w != r and tag != -1]
    read = r + 1
    chosen = [w for w, tag in writers if tag == 1 and pred[read] >> w & 1]
    try:
        check_read_cover(tuple(pred), writers, read, 1, chosen)
        return True
    except Rejected:
        return False


def provenance_oracle():
    result = []
    for n in range(2, 6):
        ps = posets(n)
        count = extensions = production_calls = unsafe_cases = 0
        for p in ps:
            ts = orders(p)
            extensions += len(ts)
            for r in range(n):
                ws = [w for w in range(n) if w != r]
                for ls in itertools.product((-1, 0, 1), repeat=n - 1):
                    labels = [-1] * n
                    for w, label in zip(ws, ls):
                        labels[w] = label
                    for initial in (0, 1):
                        actual = True
                        found_bad_trace = False
                        for trace in ts:
                            value = initial
                            for u in trace:
                                if u == r:
                                    if value != 1:
                                        actual = False
                                        found_bad_trace = True
                                    break
                                if labels[u] != -1:
                                    value = labels[u]
                            if found_bad_trace:
                                break
                        formula = rescue_rule(p, r, labels, initial)
                        production = production_prediction(p, r, labels, initial)
                        count += 1
                        production_calls += 1
                        if not actual:
                            unsafe_cases += 1
                            if not found_bad_trace:
                                raise AssertionError('unsafe case lacks countertrace')
                        if actual != formula or actual != production:
                            raise AssertionError(('provenance mismatch', p, r, labels,
                                                  initial, actual, formula, production))
        result.append({'events': n, 'posets': len(ps), 'tagged_read_cases': count,
                       'linear_extensions': extensions,
                       'production_predicate_calls': production_calls,
                       'unsafe_cases_with_replayed_countertrace': unsafe_cases,
                       'mismatches': 0})
    return result


def memory_oracle():
    result = []
    for n in range(2, 6):
        ps = posets(n)
        cases = ideal_count = 0
        for p in ps:
            ideals = [m for m in range(1 << n)
                      if all(not (m >> i & 1) or not (p[i] & ~m)
                             for i in range(n))]
            ideal_count += len(ideals)
            edges = [[u, v] for v in range(n) for u in range(n)
                     if p[v] >> u & 1]
            for weights in itertools.product((-2, 0, 3), repeat=n):
                exact = max(sum(weights[i] for i in range(n) if mask >> i & 1)
                            for mask in ideals)
                flow, ideal, got = maximum_closure(weights, edges)
                checked = check_flow(weights, edges, flow)
                mask = sum(1 << i for i in ideal)
                if checked != exact or got != exact or mask not in ideals:
                    raise AssertionError(('memory mismatch', p, weights,
                                          exact, got, checked))
                cases += 1
        result.append({'events': n, 'posets': len(ps), 'weight_cases': cases,
                       'ideals': ideal_count, 'mismatches': 0})
    return result


def _minimum_cover(universe, family):
    for size in range(len(family) + 1):
        for chosen in itertools.combinations(range(len(family)), size):
            covered = set().union(*(family[i] for i in chosen)) if chosen else set()
            if covered >= universe:
                return size, chosen
    return None, None


def _minimum_restoration_via_production(universe, family):
    elements = sorted(universe)
    bad_count = len(elements)
    good_count = len(family)
    # Explicit good initialization matches the written reduction. It precedes
    # every event, cannot cover a bad writer, and cannot improve a minimum set.
    read = 1 + bad_count + good_count
    pred = [0] * (read + 1)
    index = {u: i + 1 for i, u in enumerate(elements)}
    for bad in range(1, 1 + bad_count):
        pred[bad] = 1
    for j, subset in enumerate(family):
        good = 1 + bad_count + j
        pred[good] = 1 | sum(1 << index[u] for u in subset)
    pred[read] = (1 << read) - 1
    writers = ([(0, 1)] + [(i + 1, 0) for i in range(bad_count)] +
               [(1 + bad_count + j, 1) for j in range(good_count)])
    for size in range(good_count + 1):
        for chosen_j in itertools.combinations(range(good_count), size):
            chosen = [1 + bad_count + j for j in chosen_j]
            try:
                check_read_cover(tuple(pred), writers, read, 1, chosen)
                return size, chosen_j
            except Rejected:
                pass
    return None, None


def restoration_set_cover_oracle():
    """Exact small-instance check of the Set-Cover/restoration reduction."""
    rows = []
    total = mismatches = 0
    for n in range(1, 5):
        universe = frozenset(range(n))
        subsets = [frozenset(i for i in range(n) if mask >> i & 1)
                   for mask in range(1, 1 << n)]
        systems = 0
        for width in range(1, min(5, len(subsets)) + 1):
            for family_tuple in itertools.combinations(subsets, width):
                if set().union(*family_tuple) != set(universe):
                    continue
                family = list(family_tuple)
                exact, exact_choice = _minimum_cover(set(universe), family)
                encoded, encoded_choice = _minimum_restoration_via_production(
                    set(universe), family)
                total += 1
                systems += 1
                if exact != encoded:
                    mismatches += 1
                    raise AssertionError(('set-cover reduction mismatch', universe,
                                          family, exact, encoded,
                                          exact_choice, encoded_choice))
        rows.append({'universe_size': n, 'set_systems': systems,
                     'mismatches': 0})

    universe = set(range(6))
    family = [set((0, 1, 2, 3)), set((0, 1, 4)),
              set((2, 3, 5)), set((4,)), set((5,))]
    optimum, optimum_choice = _minimum_cover(universe, family)
    remaining = set(universe)
    greedy = []
    available = list(range(len(family)))
    while remaining:
        j = max(available, key=lambda i: (len(family[i] & remaining), -i))
        if not family[j] & remaining:
            raise AssertionError('uncoverable fixed greedy instance')
        greedy.append(j)
        remaining -= family[j]
        available.remove(j)
    if not (optimum == 2 and len(greedy) == 3):
        raise AssertionError(('expected nonminimal greedy witness', optimum, greedy))
    return {'systems_checked': total, 'by_universe_size': rows,
            'mismatches': mismatches,
            'nonminimal_greedy_witness': {
                'universe_size': 6, 'sets': [sorted(s) for s in family],
                'optimum_size': optimum,
                'optimum_choice': list(optimum_choice),
                'greedy_size': len(greedy), 'greedy_choice': greedy}}


def diagnostic_dead_stores():
    rows = []
    for n in range(2, 6):
        ps = posets(n)
        tested = valid = before = after = 0
        for p in ps:
            ts = orders(p)
            for labels in itertools.product((-1, 0, 1), repeat=n):
                reads = [r for r, label in enumerate(labels) if label == -1]
                if not reads or len(reads) == n:
                    continue
                tested += 1
                seen = {r: set() for r in reads}
                for trace in ts:
                    writer = -1
                    for u in trace:
                        if labels[u] == -1:
                            seen[u].add(writer)
                        else:
                            writer = u
                tag = lambda writer: 0 if writer == -1 else labels[writer]
                if any(len({tag(writer) for writer in seen[r]}) != 1
                       for r in reads):
                    continue
                valid += 1
                live = set().union(*seen.values())
                want = {r: tag(next(iter(seen[r]))) for r in reads}

                def single(r, keep_live):
                    value = want[r]
                    bad = [w for w in range(n)
                           if labels[w] != -1 and labels[w] != value
                           and (not keep_live or w in live)
                           and not (p[w] >> r & 1)]
                    if value != 0:
                        bad.append(-1)
                    good = [g for g in range(n)
                            if labels[g] == value and p[r] >> g & 1
                            and (not keep_live or g in live)]
                    if value == 0:
                        good.append(-1)
                    return any(all((w == -1 and g != -1) or
                                   (w != -1 and g != -1 and p[g] >> w & 1)
                                   for w in bad) for g in good)

                before += not all(single(r, False) for r in reads)
                after += not all(single(r, True) for r in reads)
        rows.append({'events': n, 'posets': len(ps), 'mixed_cases': tested,
                     'safe_cases': valid, 'single_rejections': before,
                     'after_unobservable_store_removal': after})

    p = closure(3, [(0, 2), (1, 2)])
    ts = orders(p)

    def values(keep):
        observed = set()
        for trace in ts:
            value = 0
            for event in trace:
                if event == 2:
                    observed.add(value)
                elif event in keep:
                    value = 1
        return sorted(observed)

    joint_counterexample = {
        'events': ['write-1-a', 'write-1-b', 'read-1'],
        'linear_extensions': len(ts),
        'observation_interface': ['read-1'],
        'initialization': {'value': 0, 'deletable_in_proposition': False},
        'original_observed_values': values({0, 1}),
        'delete_first_observed_values': values({1}),
        'delete_second_observed_values': values({0}),
        'delete_both_observed_values': values(set()),
        'interpretation': ('Relative to the full declared observation interface, '
                           'including read-1, each noninitial write is individually '
                           'erasable but the pair is not jointly erasable; deleting '
                           'both changes the protected read from 1 to 0.')}
    if (joint_counterexample['original_observed_values'] != [1] or
            joint_counterexample['delete_first_observed_values'] != [1] or
            joint_counterexample['delete_second_observed_values'] != [1] or
            joint_counterexample['delete_both_observed_values'] != [0]):
        raise AssertionError('joint-erasure counterexample failed')

    p6 = closure(6, [(0, 3), (1, 4), (2, 3), (2, 4), (3, 5), (4, 5)])
    labels = [0, 0, -1, 1, 1, -1]
    seen = {2: set(), 5: set()}
    for trace in orders(p6):
        last = -1
        for event in trace:
            if labels[event] == -1:
                seen[event].add(last)
            else:
                last = event
    assert seen[2] == {-1, 0, 1} and seen[5] == {3, 4}
    return {'exhaustive': rows,
            'joint_erasure_counterexample': joint_counterexample,
            'six_event_caution': {
                'labels': labels, 'pred': list(p6),
                'linear_extensions': len(orders(p6)),
                'read_last_writers': {str(r): sorted(s)
                                      for r, s in seen.items()},
                'all_writes_potentially_observable': True,
                'single_rescuer_accepts_final_read': False,
                'interpretation': ('Two writes repeat the initial tag. Removing '
                                   'both preserves both reads; mere potential '
                                   'observability is not enough to exclude '
                                   'redundant stores.')}}
