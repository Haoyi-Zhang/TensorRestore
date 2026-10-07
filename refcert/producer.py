"""Untrusted witness producer. A separate checker validates its output; structural routines are shared."""
from collections import deque
from .checker import structure, closure_network, Rejected

def maximum_closure(weights, edges):
    """Exact integer augmenting paths; return feasible flow and a tight ideal."""
    caps,s,t,positive=closure_network(weights,edges)
    residual={}; adjacent=[set() for _ in range(t+1)]
    for (u,v),cap in caps.items():
        residual[u,v]=cap; residual[v,u]=0
        adjacent[u].add(v); adjacent[v].add(u)
    adjacent=tuple(tuple(sorted(neighbors)) for neighbors in adjacent)
    while True:
        parent={s:None}; queue=deque([s])
        while queue and t not in parent:
            u=queue.popleft()
            for v in adjacent[u]:
                if v not in parent and residual[u,v]>0:
                    parent[v]=u; queue.append(v)
        if t not in parent: break
        x=t; amount=positive+1
        while x!=s:
            u=parent[x]; amount=min(amount,residual[u,x]); x=u
        x=t
        while x!=s:
            u=parent[x]; residual[u,x]-=amount; residual[x,u]+=amount; x=u
    flow=[[u,v,cap-residual[u,v]] for (u,v),cap in sorted(caps.items()) if cap!=residual[u,v]]
    ideal=sorted(u for u in parent if u<s)
    peak=sum(weights[u] for u in ideal)
    return flow,ideal,peak

def produce(program):
    st=structure(program); pred=st['pred']; rescue=[]
    for r,loc,want in st['reads']:
        writers=st['writes'].get(loc,[])
        bad=sum(1<<w for w,tag in writers if w!=r and tag!=want and not(pred[w]>>r&1))
        good=[g for g,tag in writers if tag==want and pred[r]>>g&1]
        if not good: raise Rejected('required source unavailable before read')
        chosen=[]
        while bad:
            g=max(good,key=lambda x:((pred[x]&bad).bit_count(),-x),default=None)
            if g is None or not(pred[g]&bad): raise Rejected('no restoring-writer cover')
            chosen.append(g); bad &= ~pred[g]; good.remove(g)
        rescue.append(chosen)
    flow,ideal,peak=maximum_closure(st['weights'],program['edges'])
    return {'rescue':rescue,'flow':flow,'peak_ideal':ideal},st['persistent']+peak

def single_rescuer_accepts(program):
    st=structure(program); pred=st['pred']
    for r,loc,want in st['reads']:
        ws=st['writes'].get(loc,[])
        good=[g for g,tag in ws if tag==want and pred[r]>>g&1]
        if not good: return False
        bad=[w for w,tag in ws if w!=r and tag!=want and not(pred[w]>>r&1)]
        if not bad: continue
        if not any(all(pred[g]>>w&1 for w in bad) for g in good):
            return False
    return True
