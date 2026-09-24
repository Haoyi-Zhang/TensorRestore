"""Numeric oracles for scalar and atomic-packet schedules.

These routines execute operations rather than trusting certificate annotations.
They are separate implementations, not independent human review.
"""
MASK = (1 << 32) - 1


def source_values(source, inputs):
    if len(inputs) != source['inputs']:
        raise ValueError('wrong input length')
    values = []
    for node in source['nodes']:
        op = node['op']
        if op == 'input':
            value = inputs[node['index']]
        elif op == 'const':
            value = node['literal']
        else:
            a, b = (values[j] for j in node['args'])
            if op == 'add':
                value = a + b
            elif op == 'sub':
                value = a - b
            elif op == 'mul':
                value = a * b
            elif op == 'xor':
                value = a ^ b
            else:
                raise ValueError('unknown source operator')
        values.append(value & MASK)
    return [values[output] for output in source['outputs']]


def execute(program, inputs, order):
    n = len(program['events'])
    if sorted(order) != list(range(n)):
        raise ValueError('not a permutation')
    at = {event: index for index, event in enumerate(order)}
    if any(at[u] >= at[v] for u, v in program['edges']):
        raise ValueError('not a linear extension')
    if len(inputs) != program['source']['inputs']:
        raise ValueError('wrong input length')

    memory = {0: [x & MASK for x in inputs], 1: [None] * len(program['source']['outputs'])}
    cells = sum(len(buffer) for buffer in memory.values())
    peak = cells

    def load(loc):
        buffer_id, slot = loc
        if (buffer_id not in memory or not 0 <= slot < len(memory[buffer_id])
                or memory[buffer_id][slot] is None):
            raise ValueError('invalid or uninitialized target read')
        return memory[buffer_id][slot]

    def evaluate(effect):
        kind = effect['kind']
        if kind == 'copy':
            return load(effect['src'])
        args = [load(loc) for loc in effect['args']]
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
    for event_index in order:
        event = program['events'][event_index]
        kind = event['kind']
        if kind == 'entry':
            continue
        if kind == 'alloc':
            buffer_id = event['buffer']
            if buffer_id in memory:
                raise ValueError('double allocation')
            size = program['buffers'][buffer_id]['cells']
            memory[buffer_id] = [None] * size
            cells += size
            peak = max(peak, cells)
        elif kind == 'free':
            buffer_id = event['buffer']
            cells -= len(memory[buffer_id])
            del memory[buffer_id]
        elif kind in ('copy', 'eval'):
            value = evaluate(event)
            buffer_id, slot = event['dst']
            memory[buffer_id][slot] = value
        elif kind == 'packet':
            # Every effect reads the same pre-event store. Distinct destinations are
            # checked structurally, then the buffered values commit together.
            pending = [(effect['dst'], evaluate(effect)) for effect in event['effects']]
            for (buffer_id, slot), value in pending:
                memory[buffer_id][slot] = value
        elif kind == 'exit':
            result = [load([1, slot]) for slot in range(len(memory[1]))]
        else:
            raise ValueError('unknown target event')
    return result, peak
