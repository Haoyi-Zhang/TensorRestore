"""Trusted finite checker: structure, provenance, packet effects, and a flow bound.

The checker does not call the producer or a numeric execution oracle. Memory units
are 32-bit cells, including persistent input and output buffers. A packet event is
an atomic read-before-write group: every sub-operation reads the pre-event store,
then all distinct destinations are committed together.
"""
from collections import deque


class Rejected(ValueError):
    """The supplied finite program or certificate is not accepted."""


def require(ok, message):
    if not ok:
        raise Rejected(message)


def integer(x, low=0, high=1000000):
    require(type(x) is int and low <= x <= high, 'integer outside schema bounds')
    return x


def graph(n, edges):
    integer(n, 1, 2500)
    require(type(edges) is list and len(edges) <= 20000, 'edge list limit')
    succ = [set() for _ in range(n)]
    incoming = [set() for _ in range(n)]
    for edge in edges:
        require(type(edge) is list and len(edge) == 2, 'edge shape')
        u, v = (integer(x, 0, n - 1) for x in edge)
        require(u != v, 'self edge')
        succ[u].add(v)
        incoming[v].add(u)
    degree = [len(x) for x in incoming]
    queue = deque(i for i, d in enumerate(degree) if d == 0)
    order = []
    pred = [0] * n
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in sorted(succ[u]):
            pred[v] |= pred[u] | (1 << u)
            degree[v] -= 1
            if degree[v] == 0:
                queue.append(v)
    require(len(order) == n, 'cyclic schedule')
    return pred, order


def closure_network(weights, edges):
    """Standard maximum-weight downward-closure network; no novel solver claim."""
    n = len(weights)
    source = n
    sink = n + 1
    positive = sum(w for w in weights if w > 0)
    caps = {}
    for u, weight in enumerate(weights):
        if weight > 0:
            caps[(source, u)] = weight
        elif weight < 0:
            caps[(u, sink)] = -weight
    for u, v in edges:
        caps[(v, u)] = positive + 1
    return caps, source, sink, positive


def structure(program):
    require(type(program) is dict, 'program object')
    source = program.get('source')
    require(type(source) is dict, 'source object')
    nodes = source.get('nodes')
    outputs = source.get('outputs')
    inputs = source.get('inputs')
    require(type(nodes) is list and 1 <= len(nodes) <= 5000, 'source nodes')
    require(type(outputs) is list and 1 <= len(outputs) <= 256, 'source outputs')
    integer(inputs, 1, 10000)
    for i, node in enumerate(nodes):
        require(type(node) is dict, 'source node object')
        op = node.get('op')
        if i < inputs:
            require(op == 'input' and node.get('index') == i and type(node.get('index')) is int,
                    'input prefix')
        elif op == 'const':
            integer(node.get('literal'), 0, 2**32 - 1)
        else:
            require(op in ('add', 'sub', 'mul', 'xor'), 'source operation')
            args = node.get('args')
            require(type(args) is list and len(args) == 2, 'source arity')
            for arg in args:
                integer(arg, 0, i - 1)
    require(inputs <= len(nodes), 'input count')
    for output in outputs:
        integer(output, 0, len(nodes) - 1)

    buffers = program.get('buffers')
    events = program.get('events')
    edges = program.get('edges')
    require(type(buffers) is list and 2 <= len(buffers) <= 128, 'buffers')
    require(type(events) is list and 2 <= len(events) <= 2500, 'events')
    n = len(events)
    pred, order = graph(n, edges)
    require(events[0] == {'kind': 'entry'} and events[-1] == {'kind': 'exit'}, 'entry/exit')
    for i in range(1, n):
        require(pred[i] & 1, 'entry must precede all events')
    for i in range(n - 1):
        require(pred[-1] >> i & 1, 'all events must precede exit')

    for buffer in buffers:
        require(type(buffer) is dict and type(buffer.get('persistent')) is bool, 'buffer schema')
        integer(buffer.get('cells'), 1, 10000)
    require(buffers[0]['persistent'] and buffers[0]['cells'] == inputs, 'input storage')
    require(buffers[1]['persistent'] and buffers[1]['cells'] == len(outputs), 'output storage')
    require(all(not buffer['persistent'] for buffer in buffers[2:]), 'only input/output persistent')
    require(sum(buffer['cells'] for buffer in buffers) <= 100000, 'expanded storage limit')

    alloc = {}
    free = {}
    weights = [0] * n
    accesses = []
    reads = []
    writes = {}
    packet_events = 0
    packet_effects = 0

    def location(loc):
        require(type(loc) is list and len(loc) == 2, 'location shape')
        b = integer(loc[0], 0, len(buffers) - 1)
        slot = integer(loc[1], 0, buffers[b]['cells'] - 1)
        return b, slot

    def write(event_index, loc, tag):
        writes.setdefault(loc, []).append((event_index, tag))

    def read(event_index, loc, tag):
        normalized = location(loc)
        accesses.append((event_index, normalized[0]))
        reads.append((event_index, normalized, tag))

    for slot in range(inputs):
        write(0, (0, slot), slot)
    for slot in range(len(outputs)):
        write(0, (1, slot), None)

    def scalar_effect(event_index, effect, destinations):
        require(type(effect) is dict, 'effect object')
        kind = effect.get('kind')
        require(kind in ('eval', 'copy'), 'unsupported scalar effect')
        value = integer(effect.get('value'), 0, len(nodes) - 1)
        dst = location(effect.get('dst'))
        require(dst[0] != 0, 'write to immutable input')
        require(dst not in destinations, 'duplicate packet destination')
        destinations.add(dst)
        accesses.append((event_index, dst[0]))
        write(event_index, dst, value)
        if kind == 'copy':
            read(event_index, effect.get('src'), value)
            return
        node = nodes[value]
        require(value >= inputs, 'cannot evaluate an input')
        require(effect.get('op') == node['op'], 'operation differs from source')
        args = effect.get('args')
        require(type(args) is list, 'target args')
        if node['op'] == 'const':
            require(args == [] and type(effect.get('literal')) is int
                    and effect['literal'] == node['literal'], 'literal differs from source')
        else:
            require(len(args) == 2, 'target arity')
            for loc, want in zip(args, node['args']):
                read(event_index, loc, want)

    for event_index, event in enumerate(events[1:-1], 1):
        require(type(event) is dict, 'event object')
        kind = event.get('kind')
        if kind in ('alloc', 'free'):
            buffer_id = integer(event.get('buffer'), 2, len(buffers) - 1)
            endpoints = alloc if kind == 'alloc' else free
            require(buffer_id not in endpoints, 'duplicate lifetime endpoint')
            endpoints[buffer_id] = event_index
            weights[event_index] = buffers[buffer_id]['cells'] * (1 if kind == 'alloc' else -1)
            if kind == 'alloc':
                for slot in range(buffers[buffer_id]['cells']):
                    write(event_index, (buffer_id, slot), None)
        elif kind in ('eval', 'copy'):
            scalar_effect(event_index, event, set())
        elif kind == 'packet':
            effects = event.get('effects')
            require(type(effects) is list and 2 <= len(effects) <= 16, 'packet effect count')
            destinations = set()
            for effect in effects:
                scalar_effect(event_index, effect, destinations)
            packet_events += 1
            packet_effects += len(effects)
        else:
            raise Rejected('unsupported event')

    require(set(alloc) == set(range(2, len(buffers))) and set(free) == set(alloc),
            'incomplete lifetimes')
    for buffer_id in alloc:
        require(pred[free[buffer_id]] >> alloc[buffer_id] & 1, 'free before allocation')
    for event_index, buffer_id in accesses:
        if buffer_id >= 2:
            require(pred[event_index] >> alloc[buffer_id] & 1
                    and pred[free[buffer_id]] >> event_index & 1,
                    'access outside declared lifetime')
    for slot, value in enumerate(outputs):
        read(n - 1, [1, slot], value)

    return {
        'pred': pred,
        'order': order,
        'reads': reads,
        'writes': writes,
        'weights': weights,
        'persistent': inputs + len(outputs),
        'events': n,
        'packet_events': packet_events,
        'packet_effects': packet_effects,
    }



def check_read_cover(pred, writers, read_event, want, chosen):
    """Validate one restoration witness against a reachability relation.

    ``writers`` is an iterable of ``(event, tag)`` pairs for one physical cell.
    This is the production predicate exercised by the exhaustive semantic oracle.
    It raises ``Rejected`` on a malformed or insufficient witness.
    """
    require(type(chosen) is list and len(chosen) <= len(pred), 'rescue set shape')
    tagged = dict(writers)
    good_predecessors = [writer for writer, tag in tagged.items()
                         if tag == want and pred[read_event] >> writer & 1]
    require(bool(good_predecessors), 'required source unavailable before read')
    covered = 0
    seen = set()
    for writer in chosen:
        integer(writer, 0, len(pred) - 1)
        require(writer not in seen and writer in tagged and tagged[writer] == want
                and pred[read_event] >> writer & 1, 'invalid restoring writer')
        seen.add(writer)
        covered |= pred[writer]
    for writer, tag in tagged.items():
        if writer == read_event or tag == want or pred[writer] >> read_event & 1:
            continue
        require(covered >> writer & 1, 'possible wrong last writer')
    return len(good_predecessors), len(seen)

def check_flow(weights, edges, flow):
    caps, source, sink, positive = closure_network(weights, edges)
    require(type(flow) is list and len(flow) <= len(caps), 'flow shape')
    balance = [0] * (len(weights) + 2)
    seen = set()
    for row in flow:
        require(type(row) is list and len(row) == 3, 'flow row')
        u, v = (integer(x, 0, sink) for x in row[:2])
        amount = integer(row[2], 0, 10**12)
        require((u, v) in caps and (u, v) not in seen, 'unknown or duplicate flow arc')
        require(amount <= caps[u, v], 'capacity exceeded')
        seen.add((u, v))
        balance[u] -= amount
        balance[v] += amount
    require(all(x == 0 for x in balance[:source]), 'flow conservation')
    require(balance[source] <= 0 and balance[sink] == -balance[source], 'source/sink flow')
    return positive + balance[source]


def verify(program, certificate, budget):
    """Return a checked bound or raise Rejected. No empirical execution is used."""
    integer(budget, 0, 10**12)
    require(type(certificate) is dict, 'certificate object')
    st = structure(program)
    pred = st['pred']
    reads = st['reads']
    rescue = certificate.get('rescue')
    require(type(rescue) is list and len(rescue) == len(reads), 'one witness per read')
    for (read_event, loc, want), chosen in zip(reads, rescue):
        check_read_cover(pred, st['writes'].get(loc, []), read_event, want, chosen)

    scratch = check_flow(st['weights'], program['edges'], certificate.get('flow'))
    upper = st['persistent'] + scratch
    require(upper <= budget, 'memory budget not certified')
    exact = None
    if 'peak_ideal' in certificate:
        chosen = certificate['peak_ideal']
        require(type(chosen) is list and len(chosen) <= st['events'], 'ideal shape')
        mask = 0
        for event_index in chosen:
            integer(event_index, 0, st['events'] - 1)
            require(not (mask >> event_index & 1), 'duplicate ideal event')
            mask |= 1 << event_index
        for event_index in chosen:
            require(pred[event_index] & ~mask == 0, 'not a downward-closed ideal')
        lower = st['persistent'] + sum(st['weights'][event_index] for event_index in chosen)
        require(lower == upper, 'ideal and flow do not certify the same peak')
        exact = lower
    return {
        'upper_cells': upper,
        'exact_peak_cells': exact,
        'read_obligations': len(reads),
        'events': st['events'],
        'packet_events': st['packet_events'],
        'packet_effects': st['packet_effects'],
    }
