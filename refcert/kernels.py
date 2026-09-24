"""Eight original mathematical test constructors, not imported workloads.
All dimensions are fixed at generation; reductions retain source order.
"""
MASK=(1<<32)-1
FAMILIES=('pointwise','stencil','separable','matvec','matmul','prefix','jacobi','convolution')

def build(family, n):
    if family not in FAMILIES or type(n) is not int or not 2<=n<=6:
        raise ValueError('family or bounded dimension')
    count={'pointwise':n,'stencil':n+2,'separable':(n+2)**2,'matvec':n*n+n,
           'matmul':2*n*n,'prefix':n,'jacobi':(n+2)**2,'convolution':n+4}[family]
    nodes=[{'op':'input','index':i} for i in range(count)]
    def op(kind,a,b):
        nodes.append({'op':kind,'args':[a,b]}); return len(nodes)-1
    def const(x):
        nodes.append({'op':'const','literal':x&MASK}); return len(nodes)-1
    zero=const(0)
    def summation(xs):
        r=zero
        for x in xs:r=op('add',r,x)
        return r
    if family=='pointwise':
        three=const(3); out=[op('add',op('mul',i,i),three) for i in range(n)]
    elif family=='stencil': out=[summation(range(i,i+3)) for i in range(n)]
    elif family=='separable':
        width=n+2
        h=[[summation([i*width+j+k for k in range(3)]) for j in range(n)] for i in range(width)]
        out=[summation([h[i+k][j] for k in range(3)]) for i in range(n) for j in range(n)]
    elif family=='matvec':out=[summation([op('mul',i*n+k,n*n+k) for k in range(n)]) for i in range(n)]
    elif family=='matmul':out=[summation([op('mul',i*n+k,n*n+k*n+j) for k in range(n)]) for i in range(n) for j in range(n)]
    elif family=='prefix':
        out=[];r=zero
        for i in range(n):r=op('add',r,i);out.append(r)
    elif family=='jacobi':
        width=n+2
        first=[[summation([(i+1)*width+j,(i+1)*width+j+2,i*width+j+1,(i+2)*width+j+1]) for j in range(n)] for i in range(n)]
        def second_get(i,j):return first[i][j] if 0<=i<n and 0<=j<n else zero
        out=[summation([second_get(i-1,j),second_get(i+1,j),second_get(i,j-1),second_get(i,j+1)]) for i in range(n) for j in range(n)]
    else:
        # Input holds n+2 signal samples, followed by two kernel coefficients.
        out=[summation([op('mul',i,n+2),op('mul',i+1,n+3)]) for i in range(n)]
    return {'inputs':count,'nodes':nodes,'outputs':out,'family':family,'dimension':n}

def reference(family,n,x):
    """Direct mathematical specification; does not traverse the source DAG."""
    x=[v&MASK for v in x]
    if family=='pointwise': y=[v*v+3 for v in x[:n]]
    elif family=='stencil': y=[sum(x[i:i+3]) for i in range(n)]
    elif family=='separable':
        w=n+2; y=[sum(x[(i+a)*w+j+b] for a in range(3) for b in range(3)) for i in range(n) for j in range(n)]
    elif family=='matvec': y=[sum(x[i*n+k]*x[n*n+k] for k in range(n)) for i in range(n)]
    elif family=='matmul': y=[sum(x[i*n+k]*x[n*n+k*n+j] for k in range(n)) for i in range(n) for j in range(n)]
    elif family=='prefix': y=[sum(x[:i+1]) for i in range(n)]
    elif family=='jacobi':
        w=n+2
        first=[[sum(x[(i+1)*w+j+d] for d in (0,2))+x[i*w+j+1]+x[(i+2)*w+j+1] for j in range(n)] for i in range(n)]
        def get(i,j):return first[i][j] if 0<=i<n and 0<=j<n else 0
        y=[get(i-1,j)+get(i+1,j)+get(i,j-1)+get(i,j+1) for i in range(n) for j in range(n)]
    elif family=='convolution': y=[x[i]*x[n+2]+x[i+1]*x[n+3] for i in range(n)]
    else: raise ValueError('unknown family')
    return [v&MASK for v in y]

def compile_schedule(source, layout='folded', lanes=None, tile_size=2):
    """Untrusted explicit scalarizer and tile scheduler.

    Each tile is a chain. Lane refinement orders a tile's free before the next
    allocation in that lane; different lanes denote all serial interleavings.
    """
    if layout not in ('materialized','tiled','folded'): raise ValueError('layout')
    if type(tile_size) is not int or not 1<=tile_size<=256: raise ValueError('tile size')
    nodes=source['nodes']; outs=source['outputs']; ni=source['inputs']
    groups=[list(range(len(outs)))] if layout=='materialized' else [list(range(i,min(i+tile_size,len(outs)))) for i in range(0,len(outs),tile_size)]
    if lanes is None: lanes=len(groups)
    if type(lanes) is not int or not 1<=lanes<=128:raise ValueError('lanes')
    events=[{'kind':'entry'}]; buffers=[{'persistent':True,'cells':ni},{'persistent':True,'cells':len(outs)}]; edges=[]; endpoints=[]
    def emit(event):events.append(event);return len(events)-1
    for group in groups:
        needed=set(); todo=[outs[i] for i in group]
        while todo:
            v=todo.pop()
            if v in needed or v<ni:continue
            needed.add(v);todo.extend(nodes[v].get('args',[]))
        uses={v:0 for v in needed}
        for v in needed:
            for a in nodes[v].get('args',[]):
                if a in uses: uses[a]+=1
        for i in group:
            if outs[i] in uses:uses[outs[i]]+=1
        b=len(buffers); buffers.append({'persistent':False,'cells':1})
        allocation=emit({'kind':'alloc','buffer':b}); chain=[allocation]; loc={i:[0,i] for i in range(ni)};available=[];capacity=0
        def consume(v):
            if v in uses:
                uses[v]-=1
                if uses[v]==0 and layout=='folded':available.append(loc[v][1])
        for v in sorted(needed):
            node=nodes[v]; args=[list(loc[a]) for a in node.get('args',[])]
            for a in node.get('args',[]):consume(a)
            if available:slot=available.pop()
            else:slot=capacity;capacity+=1
            loc[v]=[b,slot]
            e={'kind':'eval','value':v,'op':node['op'],'args':args,'dst':[b,slot]}
            if node['op']=='const':e['literal']=node['literal']
            chain.append(emit(e))
        for i in group:
            v=outs[i];chain.append(emit({'kind':'copy','value':v,'src':list(loc[v]),'dst':[1,i]}));consume(v)
        freed=emit({'kind':'free','buffer':b});chain.append(freed)
        buffers[b]['cells']=max(1,capacity);endpoints.append((allocation,freed))
        edges.append([0,allocation]);edges.extend([a,c] for a,c in zip(chain,chain[1:]))
    exit_event=emit({'kind':'exit'})
    for a,f in endpoints:edges.append([f,exit_event])
    for i in range(lanes,len(endpoints)):edges.append([endpoints[i-lanes][1],endpoints[i][0]])
    return {'source':source,'buffers':buffers,'events':events,'edges':edges,'layout':layout,'lanes':lanes,'tile_size':tile_size}
