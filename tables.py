#!/usr/bin/env python3
"""Emit manuscript table bodies and plot data from recorded scientific results."""
import argparse,csv,json
from pathlib import Path

def load(root,name):return json.loads((root/name).read_text(encoding='utf-8'))
def number(v):return f'{int(v):,}'
def tabular(spec,headers,rows,total=None):
    lines=[r'\begin{tabular}{'+spec+'}',r'\toprule',' & '.join(headers)+r'\\',r'\midrule']
    for row in rows:lines.append(' & '.join(map(str,row))+r'\\')
    if total is not None:lines += [r'\midrule',' & '.join(map(str,total))+r'\\']
    return '\n'.join(lines+[r'\bottomrule',r'\end{tabular}'])+'\n'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--results',type=Path,default=Path('results'))
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();root=args.results;out=args.out;out.mkdir(parents=True,exist_ok=True)
    p=load(root,'provenance-summary.json');m=load(root,'memory-summary.json')
    if [r['events'] for r in p]!=[r['events'] for r in m]:raise ValueError('oracle dimensions differ')
    rows=[]
    for a,b in zip(p,m):
        if a['posets']!=b['posets'] or a['mismatches'] or b['mismatches']:raise ValueError('oracle disagreement')
        rows.append([a['events'],a['posets'],a['linear_extensions'],a['tagged_read_cases'],b['weight_cases']])
    totals=['Total']+[number(sum(r[j] for r in rows)) for j in range(1,5)]
    (out/'oracle-table.tex').write_text(tabular('rrrrr',['Events','Posets','Linear extensions','Read cases','Weight cases'],[[number(v) for v in r] for r in rows],totals))
    with (root/'kernels.csv').open(newline='') as f:ks=list(csv.DictReader(f))
    select=[('materialized',1),('tiled',13),('tiled',2),('tiled',1),('folded',13),('folded',2),('folded',1)]
    rows=[]
    for layout,lanes in select:
        candidates=[r for r in ks if r['family']=='separable' and int(r['dimension'])==5 and r['layout']==layout and int(r['lanes'])==lanes]
        if len(candidates)!=1:raise ValueError('capacity table selection not unique')
        r=candidates[0]
        rows.append([layout.capitalize(),number(lanes),number(r['events']),number(r['sum_scratch_cells']),number(r['certified_peak_cells'])])
    (out/'capacity-table.tex').write_text(tabular('lrrrr',['Layout','Lanes','Events','Sum scratch','Exact total peak'],rows))
    ds=load(root,'stores-summary.json')['exhaustive']
    keys=['events','mixed_cases','safe_cases','single_rejections','after_unobservable_store_removal']
    rows=[[r[k] for k in keys] for r in ds]
    totals=['Total']+[number(sum(r[j] for r in rows)) for j in range(1,5)]
    (out/'stores-table.tex').write_text(tabular('rrrrr',['Events','Mixed cases','Universally safe','Before','After'],[[number(v) for v in r] for r in rows],totals))
    with (root/'packets.csv').open(newline='') as f:ps=list(csv.DictReader(f))
    chosen={2,4,8,16,32,64,128,192}
    prows=[]
    for r in ps:
        k=int(r['branches'])
        if k not in chosen:continue
        prows.append([number(k),number(r['events']),number(r['max_restorers_for_one_read']),
                      number(r['shared_scratch_cells']),number(r['quarantine_scratch_cells']),
                      number(r['injective_private_scratch_cells']),
                      f"{100*float(r['repair_retained_fraction']):.1f}\\%"])
    (out/'packet-scaling-table.tex').write_text(tabular('rrrrrrr',
        ['Branches','Events','Restorers','Set-valued','Quarantine','Injective','Repair orders'],prows))
    summary=load(root,'packets-summary.json')
    erows=[
      ['Exact unrestricted orders',number(summary['exact_unrestricted_orders_enumerated'])],
      ['Exact repaired orders',number(summary['exact_repaired_orders_enumerated'])],
      ['Numeric target executions',number(summary['numeric_target_executions'])],
      ['Unsafe shared-interface controls',number(summary['unsafe_negative_controls'])],
      ['Necessary packets in shared target',number(summary['packet_events_indispensable_in_shared_interface'])],
      ['Necessary restores in shared target',number(summary['restore_events_indispensable_in_shared_interface'])],
      ['Small fixed-read recolorings',number(summary['fixed_read_layout_assignments_checked'])],
      ['Exact recoloring-order replays',number(summary['fixed_read_layout_orders_replayed'])],
      ['Recoloring oracle mismatches',number(summary['fixed_read_layout_oracle_mismatches'])],
      ['All observed mismatches',number(summary['mismatches'])],
    ]
    (out/'packet-evidence-table.tex').write_text(tabular('lr',['Check','Count'],erows))
    baseline_rows=[
      ['Set restoration','fixed','yes','$1$','all','no'],
      ['Quarantine','fixed','yes','$2$','all','yes'],
      ['Injective recolor','fixed','yes','$k+1$','all','yes'],
      ['Edge repair','fixed','yes','$1$','subset','yes'],
      ['Value forwarding','changed','yes','$1$','all','yes'],
      ['Split effects','fixed','no','$1$','all','yes'],
    ]
    (out/'baseline-table.tex').write_text(tabular('lccccc',
        ['Alternative','Final read','Atom','Scratch','Orders','1-rest.'],baseline_rows))
    with (out/'packet-orders.dat').open('w',encoding='utf-8') as f:
        f.write('branches retained_percent shared quarantine injective\n')
        for r in ps:
            f.write(f"{int(r['branches'])} {100*float(r['repair_retained_fraction']):.12g} "
                    f"{int(r['shared_scratch_cells'])} {int(r['quarantine_scratch_cells'])} "
                    f"{int(r['injective_private_scratch_cells'])}\n")
    print('WROTE: oracle, capacity, stores, baseline, packet tables, and packet-orders.dat from recorded results.')
if __name__=='__main__':main()
