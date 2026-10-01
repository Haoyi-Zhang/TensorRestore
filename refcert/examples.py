"""Neutral, self-contained controls used by both the paper and the tests."""


def restoring_diamond():
    source={'inputs':1,'nodes':[{'op':'input','index':0},{'op':'const','literal':13}],'outputs':[0]}
    bs=[{'persistent':True,'cells':1},{'persistent':True,'cells':1},{'persistent':False,'cells':1}]
    ev=[{'kind':'entry'},{'kind':'alloc','buffer':2},{'kind':'copy','value':0,'src':[0,0],'dst':[2,0]},
        {'kind':'eval','value':1,'op':'const','args':[],'literal':13,'dst':[2,0]},
        {'kind':'copy','value':0,'src':[0,0],'dst':[2,0]},
        {'kind':'eval','value':1,'op':'const','args':[],'literal':13,'dst':[2,0]},
        {'kind':'copy','value':0,'src':[0,0],'dst':[2,0]},
        {'kind':'copy','value':0,'src':[2,0],'dst':[1,0]},{'kind':'free','buffer':2},{'kind':'exit'}]
    edges=[[0,1],[1,2],[2,3],[3,4],[2,5],[5,6],[4,7],[6,7],[7,8],[8,9]]
    return {'source':source,'buffers':bs,'events':ev,'edges':edges}


def unsafe_diamond():
    p=restoring_diamond()
    # The first branch's restore may now occur after the output is copied.
    p['edges']=[e for e in p['edges'] if e!=[4,7]]+[[4,8]]
    return p


def packet_cross_read_program(initialized=True):
    """Minimal packet that distinguishes snapshot from sequential effect commit.

    With ``initialized=True``, scratch ``h`` first receives input ``a``.  One packet
    then writes ``h <- x`` and copies the *old* ``h`` to the output.  Under the
    declared packet semantics both effects read the pre-event store, so the output is
    ``a`` regardless of effect-list order.  A sequential-commit mutant instead emits
    ``x`` when the clobber is listed first.

    With ``initialized=False``, the source requires ``x`` and the packet attempts to
    obtain it by first writing ``h <- x`` and then reading ``h`` in the same packet.
    Snapshot semantics make that read uninitialized; the checker must reject because
    a same-event write is not a predecessor source.
    """
    if type(initialized) is not bool:
        raise ValueError('initialized flag')
    source={
        'inputs':2,
        'nodes':[{'op':'input','index':0},{'op':'input','index':1}],
        'outputs':[0 if initialized else 1],
        'family':'packet-cross-read',
    }
    buffers=[
        {'persistent':True,'cells':2},
        {'persistent':True,'cells':1},
        {'persistent':False,'cells':1},
    ]
    events=[{'kind':'entry'},{'kind':'alloc','buffer':2}]
    edges=[[0,1]]
    if initialized:
        events.append({'kind':'copy','value':0,'src':[0,0],'dst':[2,0]})
        packet_predecessor=2
        edges.append([1,2])
    else:
        packet_predecessor=1
    packet=len(events)
    required=0 if initialized else 1
    events.append({
        'kind':'packet',
        'effects':[
            {'kind':'copy','value':1,'src':[0,1],'dst':[2,0]},
            {'kind':'copy','value':required,'src':[2,0],'dst':[1,0]},
        ],
    })
    freed=len(events)
    events.append({'kind':'free','buffer':2})
    exit_event=len(events)
    events.append({'kind':'exit'})
    edges.extend([[packet_predecessor,packet],[packet,freed],[freed,exit_event]])
    return {
        'source':source,
        'buffers':buffers,
        'events':events,
        'edges':edges,
        'packet_event':packet,
        'scratch_initialized':initialized,
    }
