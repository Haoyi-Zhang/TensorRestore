"""Compiler-derived atomic-packet fan used to test effect-coupled restoration.

The source computes k independent tensor elements y_i = anchor XOR x_i and returns
both y and the residual anchor. Each scheduled packet writes y_i to its output and,
as an indivisible second effect, clobbers one scratch cell. A branch-local restore
rewrites the anchor before the final residual read.

The module deliberately includes strong counter-baselines.  A two-cell quarantine
layout preserves packets, events, the final scratch read, and every original order,
but routes all clobbers to a non-anchor cell.  A one-cell forwarding layout preserves
packets and orders but changes the final read to the immutable input.  Consequently,
the one-versus-two-cell result is stated only for fixed-final-read storage recoloring;
atomicity alone is not enough.  The injective layout remains as a simple, nonoptimal
reference, and the split layout changes the packet contract.
"""
import copy
import math


def build_residual_fan(branches):
    if type(branches) is not int or not 2 <= branches <= 255:
        raise ValueError('branch count')
    nodes = [{'op': 'input', 'index': i} for i in range(branches + 1)]
    values = []
    for i in range(branches):
        nodes.append({'op': 'xor', 'args': [0, i + 1]})
        values.append(len(nodes) - 1)
    return {
        'inputs': branches + 1,
        'nodes': nodes,
        'outputs': values + [0],
        'family': 'residual-packet-fan',
        'branches': branches,
    }


def _packet(value, input_slot, clobber_dst, output_slot):
    effect = {
        'kind': 'eval',
        'value': value,
        'op': 'xor',
        'args': [[0, 0], [0, input_slot]],
    }
    clobber = dict(effect)
    clobber['args'] = [list(x) for x in effect['args']]
    clobber['dst'] = list(clobber_dst)
    output = dict(effect)
    output['args'] = [list(x) for x in effect['args']]
    output['dst'] = [1, output_slot]
    return {'kind': 'packet', 'effects': [clobber, output]}


def compile_restoring_fan(source):
    branches = source['branches']
    buffers = [
        {'persistent': True, 'cells': source['inputs']},
        {'persistent': True, 'cells': len(source['outputs'])},
        {'persistent': False, 'cells': 1},
    ]
    events = [{'kind': 'entry'}]
    edges = []

    def emit(event):
        events.append(event)
        return len(events) - 1

    allocation = emit({'kind': 'alloc', 'buffer': 2})
    initialize = emit({'kind': 'copy', 'value': 0, 'src': [0, 0], 'dst': [2, 0]})
    edges.extend([[0, allocation], [allocation, initialize]])
    packets = []
    restores = []
    for i, value in enumerate(source['outputs'][:-1]):
        packet = emit(_packet(value, i + 1, [2, 0], i))
        restore = emit({'kind': 'copy', 'value': 0, 'src': [0, 0], 'dst': [2, 0]})
        packets.append(packet)
        restores.append(restore)
        edges.extend([[initialize, packet], [packet, restore]])
    final = emit({'kind': 'copy', 'value': 0, 'src': [2, 0], 'dst': [1, branches]})
    freed = emit({'kind': 'free', 'buffer': 2})
    exit_event = emit({'kind': 'exit'})
    for restore in restores:
        edges.append([restore, final])
    edges.extend([[final, freed], [freed, exit_event]])
    return {
        'source': source,
        'buffers': buffers,
        'events': events,
        'edges': edges,
        'schedule': 'restoring-packet-fan',
        'packets': packets,
        'restores': restores,
        'anchor_location': [2, 0],
    }


def recolor_scratch_fan(program, cells, clobber_cells, restore_cells):
    """Return a fixed-read, atom-preserving scratch recoloring.

    The event set, precedence relation, packet grouping, source tags, non-scratch
    effects, and final read from scratch cell zero are unchanged.  Only packet
    clobber and restore destinations may be recolored.  This helper makes the
    comparison class executable instead of leaving it implicit in the paper.
    """
    branches = program['source']['branches']
    if type(cells) is not int or cells < 1:
        raise ValueError('scratch cell count')
    if len(clobber_cells) != branches or len(restore_cells) != branches:
        raise ValueError('recoloring arity')
    destinations = list(clobber_cells) + list(restore_cells)
    if any(type(cell) is not int or not 0 <= cell < cells for cell in destinations):
        raise ValueError('scratch cell index')
    recolored = copy.deepcopy(program)
    recolored['buffers'][2]['cells'] = cells
    for event_id, cell in zip(recolored['packets'], clobber_cells):
        recolored['events'][event_id]['effects'][0]['dst'] = [2, cell]
    for event_id, cell in zip(recolored['restores'], restore_cells):
        recolored['events'][event_id]['dst'] = [2, cell]
    recolored['schedule'] = 'fixed-read-recolored-packet-fan'
    recolored['scratch_recoloring'] = {
        'cells': cells,
        'anchor_cell': 0,
        'clobber_cells': list(clobber_cells),
        'restore_cells': list(restore_cells),
    }
    return recolored


def compile_quarantine_fan(source):
    """Optimal fixed-read one-restorer layout: anchor plus one quarantine cell."""
    shared = compile_restoring_fan(source)
    branches = source['branches']
    quarantined = recolor_scratch_fan(
        shared,
        cells=2,
        clobber_cells=[1] * branches,
        restore_cells=[1] * branches,
    )
    quarantined['schedule'] = 'quarantined-packet-fan'
    return quarantined


def compile_forwarded_fan(source):
    """One-cell/full-order baseline that changes the final dataflow interface.

    Packets and restores are untouched, but the final output is copied directly
    from the immutable input rather than from the distinguished scratch anchor.
    This is intentionally outside the fixed-final-read comparison class.
    """
    forwarded = compile_restoring_fan(source)
    branches = source['branches']
    final = next(
        i for i, event in enumerate(forwarded['events'])
        if event.get('kind') == 'copy' and event.get('dst') == [1, branches]
    )
    forwarded['events'][final]['src'] = [0, 0]
    forwarded['schedule'] = 'forwarded-residual-packet-fan'
    forwarded['final_read_interface'] = 'immutable-input'
    return forwarded


def compile_private_fan(source):
    """Nonoptimal injective recoloring: anchor plus one cell per branch.

    Unlike a dead-restore cleanup, this construction preserves the complete event
    set and order relation: packet i and restore i are both redirected to cell i+1.
    It is useful as a transparent baseline, but quarantine proves it is not storage
    optimal within the same fixed-read recoloring class.
    """
    shared = compile_restoring_fan(source)
    branches = source['branches']
    private = recolor_scratch_fan(
        shared,
        cells=branches + 1,
        clobber_cells=list(range(1, branches + 1)),
        restore_cells=list(range(1, branches + 1)),
    )
    private['schedule'] = 'injective-private-packet-fan'
    return private


def compile_split_fan(source):
    """Out-of-contract baseline that removes only each packet scratch subeffect.

    The constructor starts from the shared target and keeps every event identifier,
    restore event, and precedence edge.  At each former packet site it retains the
    unique output effect as a scalar event and removes only the scratch-clobber
    subeffect.  Consequently the event DAG and its linear extensions are literally
    identical to the shared target; the comparison changes only the packet/effect
    contract, not the order space.  The redundant restores are intentionally kept so
    that ``all orders`` is not a projection claim.
    """
    split = compile_restoring_fan(source)
    former_packets = list(split['packets'])
    for event_id in former_packets:
        packet = split['events'][event_id]
        output_effects = [effect for effect in packet['effects']
                          if effect.get('dst', [None])[0] == 1]
        if len(output_effects) != 1:
            raise ValueError('expected one packet output effect')
        split['events'][event_id] = copy.deepcopy(output_effects[0])
    split['schedule'] = 'split-scratch-subeffects-fan'
    split['former_packet_events'] = former_packets
    split['split_removed_scratch_effects'] = len(former_packets)
    split['split_preserves_event_ids_edges_and_restores'] = True
    return split


def edge_repair(program, chosen_branch=0):
    repaired = copy.deepcopy(program)
    packets = repaired['packets']
    restores = repaired['restores']
    if not 0 <= chosen_branch < len(packets):
        raise ValueError('chosen branch')
    chosen_restore = restores[chosen_branch]
    existing = {tuple(edge) for edge in repaired['edges']}
    for packet in packets:
        edge = (packet, chosen_restore)
        if edge not in existing:
            repaired['edges'].append(list(edge))
            existing.add(edge)
    repaired['schedule'] = 'single-restorer-edge-repair'
    repaired['repair_branch'] = chosen_branch
    return repaired


def unrestricted_middle_orders(branches):
    """Linear extensions of k independent packet<restore pairs."""
    return math.factorial(2 * branches) // (2 ** branches)


def repaired_middle_orders(branches):
    """Extensions after one restore is constrained after every packet.

    Choose m of the other restores before the designated restore. Before it are all
    k packets and those m restores, with m pair constraints; the remaining restores
    can follow in any order.
    """
    if type(branches) is not int or branches < 1:
        raise ValueError('branch count')
    return math.factorial(branches - 1) * sum(
        math.factorial(branches + m) // (2 ** m * math.factorial(m))
        for m in range(branches)
    )
