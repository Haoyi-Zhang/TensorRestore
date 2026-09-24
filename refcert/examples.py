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
