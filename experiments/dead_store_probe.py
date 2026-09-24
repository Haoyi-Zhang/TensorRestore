import itertools, json, time, resource, os
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
resource.setrlimit(resource.RLIMIT_CPU,(90,90))
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
 n=len(p);full=(1<<n)-1
 def rec(m,tr):
  if m==full:yield tuple(tr);return
  for u in range(n):
   if not(m>>u&1) and not(p[u]&~m):yield from rec(m|1<<u,tr+[u])
 return list(rec(0,[]))
counts={};counter=[]
for n in (2,3,4,5):
 es=list(itertools.combinations(range(n),2));ps={closure(n,[e for j,e in enumerate(es) if m>>j&1]) for m in range(1<<len(es))}
 tested=valid=separating=after=0
 for p in sorted(ps):
  ts=orders(p)
  for lab in itertools.product((-1,0,1),repeat=n):
   reads=[r for r in range(n) if lab[r]==-1]
   if not reads or all(x==-1 for x in lab):continue
   tested+=1;seen={r:set() for r in reads}
   for tr in ts:
    w=-1
    for u in tr:
     if lab[u]==-1:seen[u].add(w)
     else:w=u
   tag=lambda w:0 if w==-1 else lab[w]
   if any(len({tag(w) for w in seen[r]})!=1 for r in reads):continue
   valid+=1;live=set().union(*seen.values());expected={r:tag(next(iter(seen[r]))) for r in reads}
   def single(r,live_only):
    v=expected[r]
    bs=[w for w in range(n) if lab[w]!=-1 and lab[w]!=v and (not live_only or w in live) and not(p[w]>>r&1)]
    if v!=0:bs.append(-1)
    gs=[g for g in range(n) if lab[g]==v and p[r]>>g&1 and (not live_only or g in live)]
    if v==0:gs.append(-1)
    return any(all((w==-1 and g!=-1) or (w!=-1 and g!=-1 and p[g]>>w&1) for w in bs) for g in gs)
   if not all(single(r,False) for r in reads):separating+=1
   if not all(single(r,True) for r in reads):
    after+=1
    counter.append({'n':n,'pred':p,'labels':lab,'expected':expected,'observable':sorted(live),'orders':len(ts),'read_last_writers':{str(r):sorted(s) for r,s in seen.items()}})
    break
  if counter:break
 counts[str(n)]={'posets':len(ps),'mixed_event_cases':tested,'universally_value_safe_cases':valid,'single_rescuer_rejections_before_dead_stores':separating,'single_rescuer_rejections_after_dead_stores':after}
 if counter:break
res={'counts':counts,'counterexample':counter,'cpu_seconds':time.process_time()-c0,'wall_seconds':time.perf_counter()-t0,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'interpretation':'Exact oracle dead-store removal is a diagnostic, not an efficient baseline or a general theorem.'}
Path(__file__).with_name('dead_store_result.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps(res,indent=2))
