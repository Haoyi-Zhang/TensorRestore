#!/usr/bin/env python3
"""Reproduce finite evidence with one experiment worker.

Usage: python run.py --suite all --out reproduced
       python run.py --suite kernels --out reproduced
Suites run serially in the main worker.  The robustness suite launches only
serial public-CLI subprocesses. Results contain no release/hash manifests.
"""
import argparse, copy, csv, json, os, platform, random, resource, sys, time, unittest
from itertools import product
from pathlib import Path
from refcert.checker import structure, verify
from refcert.producer import produce, single_rescuer_accepts
from refcert.interpreter import source_values, execute
from refcert.kernels import build, reference, compile_schedule, FAMILIES
from refcert.oracles import (provenance_oracle, memory_oracle, diagnostic_dead_stores,
                             restoration_set_cover_oracle, orders)
from refcert.examples import restoring_diamond, unsafe_diamond
from refcert.packets import (build_residual_fan, compile_restoring_fan, compile_quarantine_fan,
                             compile_forwarded_fan, compile_private_fan, compile_split_fan,
                             recolor_scratch_fan, edge_repair, unrestricted_middle_orders,
                             repaired_middle_orders)
from refcert.checker import Rejected
from refcert.robustness import robustness_audit

ROOT=Path(__file__).resolve().parent

def dump(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def completed_child_cpu_seconds():
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime+usage.ru_stime

def linearization(p,seed):
    rng=random.Random(seed); n=len(p['events']); succ=[set() for _ in range(n)];degree=[0]*n
    for u,v in p['edges']:
        if v not in succ[u]:succ[u].add(v);degree[v]+=1
    avail=[i for i,d in enumerate(degree) if d==0];out=[]
    while avail:
        i=0 if seed==-1 else (len(avail)-1 if seed==-2 else rng.randrange(len(avail)))
        u=avail.pop(i);out.append(u)
        for v in sorted(succ[u]):
            degree[v]-=1
            if degree[v]==0:avail.append(v)
    if len(out)!=n:raise ValueError('cycle')
    return out

def input_vectors(n):
    rng=random.Random(271828+n)
    return [[0]*n,[2**32-1]*n,list(range(n)),[2**32-1 if i%2 else 1 for i in range(n)],
            [rng.randrange(2**32) for _ in range(n)]]

def kernels(out):
    rows=[];executions=0;reuse=0;max_events=0
    dimensions=(2,3,4,5,6)
    source_reference_comparisons=0
    for family in FAMILIES:
        for n in dimensions:
            src=build(family,n);inputs=input_vectors(src['inputs'])
            expected=[reference(family,n,x) for x in inputs]
            for x,y in zip(inputs,expected):
                source_reference_comparisons+=1
                if source_values(src,x)!=y:raise AssertionError(('source/reference',family,n))
            for layout in ('materialized','tiled','folded'):
                nt=1 if layout=='materialized' else (len(src['outputs'])+1)//2
                for lanes in sorted({1,min(2,nt),nt}):
                    p=compile_schedule(src,layout,lanes);t=time.process_time();c,b=produce(p);producer_s=time.process_time()-t
                    t=time.process_time();verdict=verify(p,c,b);checker_s=time.process_time()-t
                    traces=[linearization(p,seed) for seed in (-1,-2,0,1,2,3,4,5)]
                    measured_peak=0
                    for tr in traces:
                        for x,y in zip(inputs,expected):
                            actual,peak=execute(p,x,tr);executions+=1;measured_peak=max(peak,measured_peak)
                            if actual!=y or peak>b:raise AssertionError(('target/reference',family,n,layout,lanes))
                    p2=copy.deepcopy(p);p2['edges'] += [[a,z] for a,z in zip(traces[-1],traces[-1][1:])]
                    verify(p2,{k:v for k,v in c.items() if k!='peak_ideal'},b);reuse+=1
                    sizes=[x['cells'] for x in p['buffers'][2:]]
                    formula=src['inputs']+len(src['outputs'])+sum(max(sizes[j::lanes],default=0) for j in range(lanes))
                    if b!=formula:raise AssertionError('lane capacity formula')
                    row={'family':family,'dimension':n,'layout':layout,'lanes':lanes,'tiles':nt,
                         'source_nodes':len(src['nodes']),'events':len(p['events']),'reads':verdict['read_obligations'],
                         'persistent_cells':src['inputs']+len(src['outputs']),'sum_scratch_cells':sum(sizes),
                         'certified_peak_cells':b,'sampled_peak_cells':measured_peak,
                         'single_rescuer_accepts':int(single_rescuer_accepts(p)),
                         'rescuers':sum(len(x) for x in c['rescue']),'flow_entries':len(c['flow']),
                         'certificate_bytes':len(json.dumps(c,separators=(',',':')).encode()),
                         'producer_cpu_seconds':producer_s,'checker_cpu_seconds':checker_s}
                    rows.append(row);max_events=max(max_events,len(p['events']))
                    if family=='separable' and n==5 and layout=='folded':
                        dump(out/f'case-separable-lanes-{lanes}.json',{'program':p,'certificate':c,'budget_cells':b,'input':inputs[-1]})
    with (out/'kernels.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    diamond=restoring_diamond();c,b=produce(diamond);ts=orders(structure(diamond)['pred']);verify(diamond,c,b)
    diamond_results=[{'order':list(tr),'output':execute(diamond,[42],tr)[0],'peak_cells':execute(diamond,[42],tr)[1]} for tr in ts]
    unsafe=unsafe_diamond();uts=orders(structure(unsafe)['pred'])
    unsafe_results=[{'order':list(tr),'output':execute(unsafe,[42],tr)[0]} for tr in uts]
    dump(out/'case-restoring-diamond.json',{'program':diamond,'certificate':c,'budget_cells':b,'input':[42],'replay':diamond_results})
    dump(out/'case-missing-order.json',{'program':unsafe,'input':[42],'replay':unsafe_results})
    summary={'source_instances':len(FAMILIES)*len(dimensions),'families':len(FAMILIES),
             'dimensions':list(dimensions),'schedule_configurations':len(rows),
             'source_reference_comparisons':source_reference_comparisons,
             'target_executions':executions,'mismatches':0,'core_certificate_reuses':reuse,
             'single_rescuer_accepted_configurations':sum(r['single_rescuer_accepts'] for r in rows),'max_events':max_events,
             'input_seed_rule':'271828 + input_count','order_seeds':[-1,-2,0,1,2,3,4,5],
             'diamond_linearizations':len(ts),'unsafe_diamond_linearizations':len(uts),
             'interpretation':'Hand-written bounded mathematical constructors; not production compiler integration or workload breadth.'}
    dump(out/'kernels-summary.json',summary);return summary

def packets(out):
    """Discriminating effect-coupled family, counter-baselines, and layout oracle."""
    rows=[];numeric_executions=0;exact_orders_checked=0;repaired_orders_checked=0
    split_order_sets_checked=0;split_order_replays=0;split_order_mismatches=0
    source_formula_checks=0;negative_controls=0;max_events=0
    layout_assignments_checked=0;layout_safe=0;layout_orders_replayed=0;layout_oracle_mismatches=0
    layout_single_acceptances={1:0,2:0}
    branch_counts=(2,3,4,5,6,7,8,12,16,24,32,48,64,96,128,192)
    for branches in branch_counts:
        source=build_residual_fan(branches)
        vectors=[]
        rng=random.Random(314159+branches)
        vectors.append([0]*(branches+1))
        vectors.append([2**32-1]+list(range(1,branches+1)))
        vectors.append([rng.randrange(2**32) for _ in range(branches+1)])
        expected=[]
        for values in vectors:
            direct=[(values[0]^values[i+1])&((1<<32)-1) for i in range(branches)]+[values[0]&((1<<32)-1)]
            got=source_values(source,values);source_formula_checks+=1
            if got!=direct:raise AssertionError(('packet source/reference',branches))
            expected.append(direct)

        shared=compile_restoring_fan(source)
        t=time.process_time();certificate,budget=produce(shared);producer_s=time.process_time()-t
        t=time.process_time();verdict=verify(shared,certificate,budget);checker_s=time.process_time()-t
        if single_rescuer_accepts(shared):raise AssertionError('single rescuer unexpectedly accepts packet fan')
        if max(map(len,certificate['rescue']))!=branches:raise AssertionError('packet rescue cardinality')
        if shared['buffers'][2]['cells']!=1:raise AssertionError('shared packet capacity')

        full_orders=unrestricted_middle_orders(branches)
        repaired_orders=repaired_middle_orders(branches)
        if branches<=5:
            traces=orders(structure(shared)['pred'])
            exact_orders_checked+=len(traces)
            if len(traces)!=full_orders:raise AssertionError('packet order formula')
        else:
            traces=[linearization(shared,seed) for seed in (-1,-2,0,1,2,3,4,5)]
        for trace in traces:
            actual,peak=execute(shared,vectors[-1],trace);numeric_executions+=1
            if actual!=expected[-1] or peak!=budget:raise AssertionError(('packet target/reference',branches))

        repaired=edge_repair(shared)
        repaired_certificate,repaired_budget=produce(repaired)
        verify(repaired,repaired_certificate,repaired_budget)
        if not single_rescuer_accepts(repaired) or repaired_budget!=budget:
            raise AssertionError('edge repair baseline')
        if branches<=5:
            repaired_traces=orders(structure(repaired)['pred'])
            repaired_orders_checked+=len(repaired_traces)
            if len(repaired_traces)!=repaired_orders:raise AssertionError('repaired order formula')
            for trace in (repaired_traces[0],repaired_traces[-1]):
                actual,peak=execute(repaired,vectors[-1],trace);numeric_executions+=1
                if actual!=expected[-1] or peak!=repaired_budget:
                    raise AssertionError('repaired execution')

        # Strong all-order alternatives.  Quarantine is optimal only in the explicit
        # fixed-final-read storage-recoloring class.  Forwarding is the counterexample
        # showing that atomicity alone does not imply a storage advantage.
        quarantine=compile_quarantine_fan(source)
        quarantine_certificate,quarantine_budget=produce(quarantine)
        verify(quarantine,quarantine_certificate,quarantine_budget)
        if not single_rescuer_accepts(quarantine):raise AssertionError('quarantine baseline')
        if quarantine['buffers'][2]['cells']!=2 or quarantine_budget-budget!=1:
            raise AssertionError('quarantine capacity delta')
        if quarantine['edges']!=shared['edges'] or quarantine['packets']!=shared['packets']:
            raise AssertionError('quarantine changed event/order interface')

        private=compile_private_fan(source)
        private_certificate,private_budget=produce(private)
        verify(private,private_certificate,private_budget)
        if not single_rescuer_accepts(private):raise AssertionError('injective private baseline')
        if private['buffers'][2]['cells']!=branches+1 or private_budget-budget!=branches:
            raise AssertionError('injective private capacity delta')
        if private['edges']!=shared['edges'] or private['packets']!=shared['packets']:
            raise AssertionError('injective private changed event/order interface')

        forwarded=compile_forwarded_fan(source)
        forwarded_certificate,forwarded_budget=produce(forwarded)
        verify(forwarded,forwarded_certificate,forwarded_budget)
        if not single_rescuer_accepts(forwarded) or forwarded_budget!=budget:
            raise AssertionError('forwarded-read baseline')
        if forwarded['edges']!=shared['edges'] or forwarded['packets']!=shared['packets']:
            raise AssertionError('forwarding changed atoms or orders')

        split=compile_split_fan(source)
        split_certificate,split_budget=produce(split)
        verify(split,split_certificate,split_budget)
        if not single_rescuer_accepts(split) or split_budget!=budget:
            raise AssertionError('split baseline')
        if (len(split['events'])!=len(shared['events']) or split['edges']!=shared['edges']
                or split['restores']!=shared['restores']):
            raise AssertionError('split changed event/order/restore interface')
        if structure(split)['pred']!=structure(shared)['pred']:
            raise AssertionError('split changed reachability relation')
        if any(split['events'][event_id].get('kind')=='packet'
               for event_id in split['former_packet_events']):
            raise AssertionError('split retained a packet atom')
        if branches in (2,3):
            split_traces=orders(structure(split)['pred'])
            split_order_sets_checked+=1;split_order_replays+=len(split_traces)
            if split_traces!=traces:
                split_order_mismatches+=1
                raise AssertionError('split order set differs from shared target')
            for trace in split_traces:
                actual,peak=execute(split,vectors[-1],trace);numeric_executions+=1
                if actual!=expected[-1] or peak!=split_budget:
                    raise AssertionError('split exact-order execution')

        # Exhaustive small storage-recoloring oracle: all assignments of packet
        # clobbers and restores to one or two cells, with the final read fixed at cell 0.
        # Safety is decided by replaying every legal order on a discriminating numeric
        # input, not by the certificate producer.  The checker/producer decision is then
        # compared with that independent finite oracle.  The theorem supplies the
        # unbounded one-cell lower bound; this oracle attacks its implementation at k=2,3.
        if branches in (2,3):
            layout_traces=traces
            probe=[0x13579BDF]+list(range(1,branches+1))
            probe_expected=source_values(source,probe)
            for cells in (1,2):
                for assignment in product(range(cells),repeat=2*branches):
                    layout_assignments_checked+=1
                    candidate=recolor_scratch_fan(shared,cells,assignment[:branches],assignment[branches:])
                    exact_safe=True
                    for trace in layout_traces:
                        actual,_=execute(candidate,probe,trace)
                        numeric_executions+=1;layout_orders_replayed+=1
                        if actual!=probe_expected:exact_safe=False
                    accepted=True
                    try:
                        candidate_certificate,candidate_budget=produce(candidate)
                    except Rejected:
                        accepted=False
                    if accepted:
                        verify(candidate,candidate_certificate,candidate_budget)
                    if accepted!=exact_safe:
                        layout_oracle_mismatches+=1
                        raise AssertionError(('fixed-read layout oracle disagreement',branches,cells,assignment,accepted,exact_safe))
                    if exact_safe:
                        layout_safe+=1
                        if single_rescuer_accepts(candidate):layout_single_acceptances[cells]+=1

        # Removing any restore-to-final obligation admits an explicit bad order in
        # the original shared/fixed-read target.  The input makes the affected branch
        # value differ numerically from the anchor, supplementing the tag proof.
        unsafe_example=None
        final=next(i for i,e in enumerate(shared['events']) if e.get('dst')==[1,branches])
        freed=next(i for i,e in enumerate(shared['events']) if e.get('kind')=='free')
        for affected in range(branches):
            unsafe=copy.deepcopy(shared)
            restore=unsafe['restores'][affected]
            unsafe['edges']=[edge for edge in unsafe['edges'] if edge!=[restore,final]]
            unsafe['edges'].append([restore,freed])
            try:
                produce(unsafe)
            except Rejected:
                pass
            else:
                raise AssertionError('unsafe packet fan accepted')
            bad_order=[0,1,2]
            for i in range(branches):
                if i!=affected:bad_order += [unsafe['packets'][i],unsafe['restores'][i]]
            bad_order += [unsafe['packets'][affected],final,restore,freed,len(unsafe['events'])-1]
            bad_values=[0]*(branches+1);bad_values[0]=0x12345678;bad_values[affected+1]=1
            bad_expected=source_values(source,bad_values)
            bad_output,_=execute(unsafe,bad_values,bad_order)
            numeric_executions+=1;negative_controls+=1
            if bad_output[-1]==bad_expected[-1]:
                raise AssertionError('negative packet control did not fail')
            if branches==4 and affected==0:
                unsafe_example=(unsafe,bad_values,bad_order,bad_output,bad_expected)

        # Whole-event DSE cannot delete any packet from the shared target: each is the
        # unique correct writer of a distinct required output.  Each shared-interface
        # restore is needed by the explicit bad order above.  Forwarding deliberately
        # demonstrates that this indispensability does not survive interface rewriting.
        st=structure(shared)
        unique_packet_outputs=0
        for i,packet in enumerate(shared['packets']):
            writers=[w for w,tag in st['writes'][(1,i)] if tag==source['outputs'][i]]
            if writers==[packet]:unique_packet_outputs+=1
        if unique_packet_outputs!=branches:raise AssertionError('packet output uniqueness')

        for program,values,answer,peak_bound in (
                (quarantine,vectors[0],expected[0],quarantine_budget),
                (private,vectors[0],expected[0],private_budget),
                (forwarded,vectors[1],expected[1],forwarded_budget),
                (split,vectors[1],expected[1],split_budget)):
            trace=structure(program)['order'];actual,peak=execute(program,values,trace);numeric_executions+=1
            if actual!=answer or peak!=peak_bound:raise AssertionError('packet baseline execution')

        row={'branches':branches,'source_nodes':len(source['nodes']),'events':len(shared['events']),
             'packet_events':verdict['packet_events'],'packet_effects':verdict['packet_effects'],
             'read_obligations':verdict['read_obligations'],'shared_scratch_cells':1,
             'quarantine_scratch_cells':2,'fixed_read_min_single_rescuer_cells':2,
             'injective_private_scratch_cells':branches+1,
             'scratch_cells_saved_vs_best_fixed_read_single_rescuer':1,
             'scratch_cells_saved_vs_injective_private':branches,
             'shared_peak_cells':budget,'quarantine_peak_cells':quarantine_budget,
             'injective_private_peak_cells':private_budget,'forwarded_peak_cells':forwarded_budget,
             'split_peak_cells':split_budget,'split_events':len(split['events']),
             'split_restores_retained':len(split['restores']),
             'split_order_relation_preserved':int(structure(split)['pred']==structure(shared)['pred']),
             'max_restorers_for_one_read':max(map(len,certificate['rescue'])),
             'single_rescuer_shared':int(single_rescuer_accepts(shared)),
             'single_rescuer_repaired':int(single_rescuer_accepts(repaired)),
             'single_rescuer_quarantine':int(single_rescuer_accepts(quarantine)),
             'single_rescuer_injective_private':int(single_rescuer_accepts(private)),
             'single_rescuer_forwarded':int(single_rescuer_accepts(forwarded)),
             'single_rescuer_split':int(single_rescuer_accepts(split)),
             'edge_repair_added_edges':branches-1,'unrestricted_orders':str(full_orders),
             'repaired_orders':str(repaired_orders),
             'repair_retained_fraction':repaired_orders/full_orders,
             'certificate_bytes':len(json.dumps(certificate,separators=(',',':')).encode()),
             'producer_cpu_seconds':producer_s,'checker_cpu_seconds':checker_s,
             'unique_essential_packet_outputs_shared_interface':unique_packet_outputs,
             'essential_restores_shared_interface':branches}
        rows.append(row);max_events=max(max_events,len(shared['events']))
        if branches==4:
            dump(out/'case-packet-fan-4.json',{'program':shared,'certificate':certificate,
                 'budget_cells':budget,'input':vectors[-1],'expected_output':expected[-1],
                 'comparison_class':{'name':'fixed-final-read atom-preserving storage recoloring',
                                     'preserves':['source','events','edges','packet grouping','effect operations and operands','result tags and values','all non-scratch destinations','final scratch read'],
                                     'permits':['scratch capacity and clobber/restore destination recoloring']},
                 'baselines':{'fixed_read_min_single_rescuer_cells':2,
                              'quarantine_budget_cells':quarantine_budget,
                              'injective_private_budget_cells':private_budget,
                              'forwarded_budget_cells':forwarded_budget,
                              'split_budget_cells':split_budget,
                              'edge_repair_orders':str(repaired_orders),
                              'unrestricted_orders':str(full_orders)}})
            unsafe,bad_values,bad_order,bad_output,bad_expected=unsafe_example
            dump(out/'case-packet-fan-unsafe.json',{'program':unsafe,'input':bad_values,
                 'bad_order':bad_order,'observed_output':bad_output,'expected_output':bad_expected,
                 'removed_restore_to_final_edge_for_branch':0,
                 'scope':'original shared target with fixed final scratch read'})
    if layout_single_acceptances[1]!=0 or layout_single_acceptances[2]==0:
        raise AssertionError('fixed-read layout oracle failed to separate one and two cells')
    with (out/'packets.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    summary={'branch_counts':list(branch_counts),'configurations':len(rows),
             'source_formula_checks':source_formula_checks,'numeric_target_executions':numeric_executions,
             'exact_unrestricted_orders_enumerated':exact_orders_checked,
             'exact_repaired_orders_enumerated':repaired_orders_checked,
             'unsafe_negative_controls':negative_controls,'mismatches':0,'max_events':max_events,
             'fixed_read_layout_assignments_checked':layout_assignments_checked,
             'fixed_read_safe_layouts_checked':layout_safe,
             'fixed_read_layout_orders_replayed':layout_orders_replayed,
             'fixed_read_layout_oracle_mismatches':layout_oracle_mismatches,
             'one_cell_single_rescuer_acceptances':layout_single_acceptances[1],
             'two_cell_single_rescuer_acceptances':layout_single_acceptances[2],
             'proved_fixed_read_min_single_rescuer_cells':2,
             'single_rescuer_shared_acceptances':sum(r['single_rescuer_shared'] for r in rows),
             'single_rescuer_repaired_acceptances':sum(r['single_rescuer_repaired'] for r in rows),
             'single_rescuer_quarantine_acceptances':sum(r['single_rescuer_quarantine'] for r in rows),
             'single_rescuer_injective_private_acceptances':sum(r['single_rescuer_injective_private'] for r in rows),
             'single_rescuer_forwarded_acceptances':sum(r['single_rescuer_forwarded'] for r in rows),
             'single_rescuer_split_acceptances':sum(r['single_rescuer_split'] for r in rows),
             'split_configurations_with_identical_event_order_relation':sum(r['split_order_relation_preserved'] for r in rows),
             'split_small_order_sets_checked':split_order_sets_checked,
             'split_exact_orders_replayed':split_order_replays,
             'split_order_mismatches':split_order_mismatches,
             'packet_events_indispensable_in_shared_interface':sum(r['unique_essential_packet_outputs_shared_interface'] for r in rows),
             'restore_events_indispensable_in_shared_interface':negative_controls,
             'interpretation':'The shared fixed-read target needs a set-valued cover. Within event/order/final-read-preserving storage recoloring, one cell cannot pass the single-restorer rule and a two-cell quarantine is optimal. Direct final-value forwarding matches one cell and all orders by changing the read interface. The split baseline removes only packet scratch subeffects while retaining every event identifier, restore, and edge, so it has the identical order relation but changes the atom contract.'}
    dump(out/'packets-summary.json',summary);return summary

def run_tests(out):
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    with (out/'tests.txt').open('w') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    summary={'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful()}
    dump(out/'tests.json',summary)
    if not result.wasSuccessful():raise AssertionError('tests failed')
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite',choices=('all','tests','provenance','memory','cover','stores','robustness','kernels','packets'),default='all')
    parser.add_argument('--out',type=Path,default=Path('reproduced'))
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    # POSIX per-process guards. Serial CLI subprocesses inherit these limits; RLIMIT_CPU
    # is not an aggregate process-tree budget.
    address_limit=3*1024**3
    if hasattr(resource,'RLIMIT_AS'):resource.setrlimit(resource.RLIMIT_AS,(address_limit,address_limit))
    resource.setrlimit(resource.RLIMIT_CPU,(240,240))
    affinity_applied=False
    if hasattr(os,'sched_getaffinity'):
        os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});affinity_applied=True
    start=time.perf_counter();worker_cpu=time.process_time();child_cpu=completed_child_cpu_seconds()
    suite_data={};timing={}
    tasks={'tests':run_tests,'provenance':lambda o:provenance_oracle(),'memory':lambda o:memory_oracle(),
           'cover':lambda o:restoration_set_cover_oracle(),
           'stores':lambda o:diagnostic_dead_stores(),
           'robustness':lambda o:robustness_audit(),'kernels':kernels,'packets':packets}
    for name,fn in tasks.items():
        if args.suite not in ('all',name):continue
        t=time.perf_counter();c=time.process_time();cc=completed_child_cpu_seconds()
        suite_data[name]=fn(out)
        timing[name]={'wall_seconds':time.perf_counter()-t,
                      'worker_cpu_seconds':time.process_time()-c,
                      'completed_cli_child_cpu_seconds':completed_child_cpu_seconds()-cc}
        dump(out/f'{name}-summary.json',suite_data[name]);print(name,'completed',flush=True)
    worker_used=time.process_time()-worker_cpu
    child_used=completed_child_cpu_seconds()-child_cpu
    system=platform.system()
    rss_unit='KiB' if system=='Linux' else ('bytes' if system=='Darwin' else 'platform-defined')
    report={
        'suite':args.suite,
        'execution_model':{
            'experiment_workers':1,
            'suite_scheduling':'serial in the main worker',
            'cli_subprocesses':'serial only (public-CLI robustness checks)',
        },
        'resource_limits':{
            'virtual_address_limit_bytes_per_process':address_limit if hasattr(resource,'RLIMIT_AS') else None,
            'cpu_limit_seconds_per_process':240,
            'single_cpu_affinity_applied':affinity_applied,
            'scope':('POSIX per-process limits on the worker, inherited by spawned CLI children; '
                     'the CPU limit is not an aggregate process-tree limit.'),
        },
        'wall_seconds':time.perf_counter()-start,
        'worker_cpu_seconds':worker_used,
        'completed_cli_child_cpu_seconds':child_used,
        'accounted_cpu_seconds':worker_used+child_used,
        'main_process_peak_rss':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        'main_process_peak_rss_unit':rss_unit,
        'measurement_scope':(
            'process_time and RUSAGE_SELF describe only the main experiment worker. '
            'Completed serial child CPU is added from RUSAGE_CHILDREN. Child RSS is '
            'not reported or summed; the main-process peak is not a process-tree peak.'),
        'reference_environment':{
            'os':system,
            'os_release':platform.release(),
            'python_implementation':sys.implementation.name,
            'python_version':platform.python_version(),
            'resource_module_assumption':'POSIX resource semantics; Windows requires adaptation.',
            'legacy_environment_for_preceding_frozen_runs':'unknown/not recoverable',
        },
        'timing':timing,
        'results':suite_data,
    }
    dump(out/'run-summary.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('results','timing')},indent=2))
if __name__=='__main__':main()
