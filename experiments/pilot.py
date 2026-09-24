"""Small exact oracle for a candidate all-order provenance criterion.
No tensor code or third-party code is executed. One bounded worker.
"""
import itertools,json,os,resource,time
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
resource.setrlimit(resource.RLIMIT_CPU,(100,100))
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
t0=time.perf_counter();c0=time.process_time()
def closure(n,edges):
    p=[0]*n
    for u,v in edges:p[v]|=1<<u
    for k in range(n):
        for v in range(n):
            if p[v]>>k&1:p[v]|=p[k]
    return tuple(p)
def orders(p):
    n=len(p);allm=(1<<n)-1
    def rec(m,s):
        if m==allm:yield tuple(s);return
        for u in range(n):
            if not (m>>u&1) and not(p[u]&~m):yield from rec(m|1<<u,s+[u])
    return list(rec(0,[]))
def criterion(p,r,labels):
    # Entry contains the desired value. -1 means no write; 0 bad; 1 good.
    good=[g for g,x in enumerate(labels) if x==1 and g!=r and p[r]>>g&1]
    for w,x in enumerate(labels):
        if w==r or x!=0:continue
        if p[w]>>r&1:continue
        if not any(p[g]>>w&1 for g in good):return False
    return True
counts={};bad=[]
for n in (2,3,4,5):
    edges=list(itertools.combinations(range(n),2));posets={}
    for m in range(1<<len(edges)):
        p=closure(n,[e for i,e in enumerate(edges) if m>>i&1]);posets[p]=None
    tested=0;oracle_orders=0
    for p in posets:
        ts=orders(p);oracle_orders+=len(ts)
        for r in range(n):
            ws=[u for u in range(n) if u!=r]
            for ls in itertools.product((-1,0,1),repeat=n-1):
                lab=[-1]*n
                for u,l in zip(ws,ls):lab[u]=l
                predicted=criterion(p,r,lab)
                actual=True
                for tr in ts:
                    value=1
                    for u in tr:
                        if u==r:
                            if value!=1:actual=False
                            break
                        if lab[u]!=-1:value=lab[u]
                    if not actual:break
                tested+=1
                if actual!=predicted:
                    bad.append({'n':n,'p':p,'r':r,'labels':lab,'predicted':predicted,'actual':actual})
                    break
            if bad:break
        if bad:break
    counts[str(n)]={'distinct_naturally_labeled_posets':len(posets),'tagged_read_cases':tested,'topological_orders_enumerated':oracle_orders}
    if bad:break
# Two independent overwrite/restore branches: no single good writer covers both bads.
p=closure(5,[(0,1),(1,4),(2,3),(3,4)])
lab=[0,1,0,1,-1];r=4
single=any(all(p[w]>>r&1 or p[g]>>w&1 for w,x in enumerate(lab) if x==0) for g,x in enumerate(lab) if x==1 and p[r]>>g&1)
res={'candidate':'universal_last_writer_rescue','counts':counts,'mismatches':bad,'diamond':{'accepted':criterion(p,r,lab),'single_rescuer_accepted':single,'linearizations':len(orders(p))},'wall_seconds':time.perf_counter()-t0,'cpu_seconds':time.process_time()-c0,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'workers':1,'arithmetic':'exact integer event identifiers; two provenance tags plus no-write','seed':None,'status':'PASS' if not bad and not single else 'FAIL'}
Path(__file__).with_name('result.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(res,indent=2))
