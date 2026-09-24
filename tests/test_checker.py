import copy, unittest
from itertools import product
from refcert.checker import verify, Rejected, structure
from refcert.producer import produce, single_rescuer_accepts
from refcert.kernels import build, compile_schedule
from refcert.packets import (build_residual_fan, compile_restoring_fan, compile_quarantine_fan,
                             compile_forwarded_fan, compile_private_fan, compile_split_fan,
                             recolor_scratch_fan, edge_repair, unrestricted_middle_orders,
                             repaired_middle_orders)
from refcert.examples import restoring_diamond, unsafe_diamond
from refcert.interpreter import execute, source_values
from refcert.oracles import orders

class Certificates(unittest.TestCase):
    def setUp(self):
        self.p=compile_schedule(build('pointwise',3),'folded',1)
        self.c,self.b=produce(self.p)
    def reject(self, change):
        p,c=copy.deepcopy(self.p),copy.deepcopy(self.c)
        change(p,c)
        with self.assertRaises(Rejected):verify(p,c,self.b)
    def test_valid(self):self.assertEqual(verify(self.p,self.c,self.b)['exact_peak_cells'],self.b)
    def test_wrong_operation(self):
        def mutate(p,c):
            e=next(e for e in p['events'] if e.get('op')=='mul');e['op']='add'
        self.reject(mutate)
    def test_wrong_operand(self):
        def mutate(p,c):
            e=next(e for e in p['events'] if e.get('op')=='mul');e['args'][0]=[0,1]
        self.reject(mutate)
    def test_wrong_arity(self):
        self.reject(lambda p,c:next(e for e in p['events'] if e.get('op')=='mul')['args'].pop())
    def test_input_is_readonly(self):
        self.reject(lambda p,c:next(e for e in p['events'] if e.get('kind')=='eval').update(dst=[0,0]))
    def test_bad_location(self):
        self.reject(lambda p,c:next(e for e in p['events'] if e.get('kind')=='eval').update(dst=[2,10000]))
    def test_missing_lifetime(self):
        self.reject(lambda p,c:next(e for e in p['events'] if e.get('kind')=='free').update(kind='entry'))
    def test_cycle(self):self.reject(lambda p,c:p['edges'].append([len(p['events'])-1,0]))
    def test_omitted_rescue(self):
        def mutate(p,c):
            i=next(i for i,r in enumerate(c['rescue']) if r);c['rescue'][i]=[]
        self.reject(mutate)
    def test_capacity_violation(self):
        def mutate(p,c):c['flow'][0][2]=10**12
        self.reject(mutate)
    def test_conservation_violation(self):
        def mutate(p,c):c['flow'].pop()
        self.reject(mutate)
    def test_false_peak_ideal(self):self.reject(lambda p,c:c.update(peak_ideal=[]))
    def test_budget_below_exact(self):
        with self.assertRaises(Rejected):verify(self.p,self.c,self.b-1)
    def test_forged_copy_tag(self):
        self.reject(lambda p,c:next(e for e in p['events'] if e.get('kind')=='copy').update(value=0))
    def test_bool_budget_rejected(self):
        with self.assertRaises(Rejected):verify(self.p,self.c,True)
    def test_duplicate_flow_arc(self):
        self.reject(lambda p,c:c['flow'].append(c['flow'][0]))
    def test_required_source_unavailable(self):
        p=copy.deepcopy(self.p)
        out0=next(e for e in p['events'] if e.get('kind')=='copy' and e.get('dst')==[1,0])
        out0['dst']=[1,1]
        with self.assertRaisesRegex(Rejected,'required source unavailable before read'):
            produce(p)
    def test_unknown_restoring_writer_rejected(self):
        p,c=copy.deepcopy(self.p),copy.deepcopy(self.c)
        i=next(i for i,row in enumerate(c['rescue']) if row)
        c['rescue'][i]=[len(p['events'])-1]
        with self.assertRaises(Rejected):
            verify(p,c,self.b)
    def test_diamond_all_orders(self):
        p=restoring_diamond();c,b=produce(p);verify(p,c,b)
        self.assertFalse(single_rescuer_accepts(p))
        ts=orders(structure(p)['pred']);self.assertEqual(len(ts),6)
        for tr in ts:self.assertEqual(execute(p,[42],tr),([42],3))
    def test_unsafe_diamond(self):
        p=unsafe_diamond()
        with self.assertRaises(Rejected):produce(p)
        safe_c,safe_b=produce(restoring_diamond())
        with self.assertRaisesRegex(Rejected,'invalid restoring writer'):
            verify(p,safe_c,safe_b)
        outcomes=[execute(p,[42],tr)[0][0] for tr in orders(structure(p)['pred'])]
        self.assertIn(13,outcomes);self.assertIn(42,outcomes)
    def test_order_strengthening_reuses_core(self):
        p=copy.deepcopy(self.p);tr=structure(p)['order']
        p['edges'] += [[a,b] for a,b in zip(tr,tr[1:])]
        core={k:v for k,v in self.c.items() if k!='peak_ideal'}
        verify(p,core,self.b)
        # Edge refinement retains an upper witness, not its optional tight ideal.
        wide=compile_schedule(build('separable',5),'folded',13)
        cert,budget=produce(wide)
        narrow=copy.deepcopy(wide)
        alloc={e['buffer']:i for i,e in enumerate(narrow['events']) if e['kind']=='alloc'}
        free={e['buffer']:i for i,e in enumerate(narrow['events']) if e['kind']=='free'}
        bs=sorted(alloc)
        narrow['edges'] += [[free[a],alloc[b]] for a,b in zip(bs,bs[1:])]
        verify(narrow,{k:v for k,v in cert.items() if k!='peak_ideal'},budget)
        with self.assertRaisesRegex(Rejected,'not a downward-closed ideal'):
            verify(narrow,cert,budget)
        newcert,newbudget=produce(narrow)
        self.assertEqual((budget,newbudget),(162,81))
        verify(narrow,newcert,newbudget)
    def test_in_place_read_before_write(self):
        p=compile_schedule(build('prefix',3),'folded',1)
        self.assertTrue(any(e.get('kind')=='eval' and e['dst'] in e['args'] for e in p['events']))
        c,b=produce(p);verify(p,c,b)
        self.assertEqual(execute(p,[2**32-1,2,3],structure(p)['order'])[0],source_values(p['source'],[2**32-1,2,3]))

    def test_atomic_packet_fan_all_orders(self):
        source=build_residual_fan(3);p=compile_restoring_fan(source);c,b=produce(p)
        verdict=verify(p,c,b)
        self.assertEqual((verdict['packet_events'],verdict['packet_effects']),(3,6))
        self.assertFalse(single_rescuer_accepts(p))
        self.assertEqual(max(map(len,c['rescue'])),3)
        ts=orders(structure(p)['pred'])
        self.assertEqual(len(ts),unrestricted_middle_orders(3))
        x=[7,11,13,17];expected=source_values(source,x)
        for tr in ts:self.assertEqual(execute(p,x,tr),(expected,b))

    def test_packet_destinations_must_be_distinct(self):
        p=compile_restoring_fan(build_residual_fan(2));c,b=produce(p)
        packet=next(e for e in p['events'] if e.get('kind')=='packet')
        packet['effects'][1]['dst']=list(packet['effects'][0]['dst'])
        with self.assertRaisesRegex(Rejected,'duplicate packet destination'):
            verify(p,c,b)

    def test_packet_reads_use_pre_event_store(self):
        # Both packet effects read the old anchor even though the first effect writes it.
        p=compile_restoring_fan(build_residual_fan(2));c,b=produce(p)
        x=[5,9,12];tr=structure(p)['order']
        self.assertEqual(execute(p,x,tr)[0],source_values(p['source'],x))
        verify(p,c,b)

    def test_packet_baselines_and_edge_repair(self):
        source=build_residual_fan(4);shared=compile_restoring_fan(source)
        cert,budget=produce(shared)
        self.assertEqual(shared['buffers'][2]['cells'],1)
        self.assertFalse(single_rescuer_accepts(shared))
        repaired=edge_repair(shared);rc,rb=produce(repaired)
        self.assertTrue(single_rescuer_accepts(repaired));self.assertEqual(rb,budget)
        self.assertEqual(len(orders(structure(repaired)['pred'])),repaired_middle_orders(4))
        quarantine=compile_quarantine_fan(source);qc,qb=produce(quarantine)
        self.assertTrue(single_rescuer_accepts(quarantine))
        self.assertEqual(quarantine['buffers'][2]['cells'],2);self.assertEqual(qb-budget,1)
        private=compile_private_fan(source);pc,pb=produce(private)
        self.assertTrue(single_rescuer_accepts(private));self.assertEqual(private['buffers'][2]['cells'],5)
        self.assertEqual(pb-budget,4)
        forwarded=compile_forwarded_fan(source);fc,fb=produce(forwarded)
        self.assertTrue(single_rescuer_accepts(forwarded));self.assertEqual(fb,budget)
        split=compile_split_fan(source);sc,sb=produce(split)
        self.assertTrue(single_rescuer_accepts(split));self.assertEqual(sb,budget)
        for program,certificate,peak in ((shared,cert,budget),(repaired,rc,rb),(quarantine,qc,qb),
                                         (private,pc,pb),(forwarded,fc,fb),(split,sc,sb)):
            verify(program,certificate,peak)

    def test_fixed_read_recoloring_one_cell_lower_bound(self):
        # Exhaust every clobber/restore destination assignment for k=2 and k=3.
        # With one cell the only assignment is the shared target and no safe target
        # passes the one-restorer rule.  With two cells a safe accepting assignment
        # exists; the all-to-cell-1 quarantine construction is one such witness.
        for branches in (2,3):
            source=build_residual_fan(branches);shared=compile_restoring_fan(source)
            accepted={1:[],2:[]}
            traces=orders(structure(shared)['pred'])
            values=[0x13579BDF]+list(range(1,branches+1))
            expected=source_values(source,values)
            for cells in (1,2):
                for assignment in product(range(cells),repeat=2*branches):
                    q=recolor_scratch_fan(shared,cells,assignment[:branches],assignment[branches:])
                    exact_safe=all(execute(q,values,trace)[0]==expected for trace in traces)
                    checker_accepts=True
                    try:
                        certificate,peak=produce(q)
                    except Rejected:
                        checker_accepts=False
                    if checker_accepts:verify(q,certificate,peak)
                    self.assertEqual(checker_accepts,exact_safe)
                    if exact_safe and single_rescuer_accepts(q):accepted[cells].append(assignment)
            self.assertEqual(accepted[1],[])
            self.assertIn((1,)*(2*branches),accepted[2])

    def test_forwarding_preserves_atoms_and_orders_but_changes_final_read(self):
        source=build_residual_fan(2);shared=compile_restoring_fan(source)
        forwarded=compile_forwarded_fan(source)
        self.assertEqual(shared['edges'],forwarded['edges'])
        self.assertEqual(shared['packets'],forwarded['packets'])
        for packet in shared['packets']:
            self.assertEqual(shared['events'][packet],forwarded['events'][packet])
        final=next(i for i,e in enumerate(shared['events']) if e.get('dst')==[1,2])
        self.assertEqual(shared['events'][final]['src'],[2,0])
        self.assertEqual(forwarded['events'][final]['src'],[0,0])
        certificate,peak=produce(forwarded);verify(forwarded,certificate,peak)
        self.assertTrue(single_rescuer_accepts(forwarded))
        x=[19,2,5];expected=source_values(source,x)
        for trace in orders(structure(forwarded)['pred']):
            self.assertEqual(execute(forwarded,x,trace)[0],expected)

    def test_each_packet_and_restore_is_indispensable_in_shared_interface(self):
        source=build_residual_fan(3);p=compile_restoring_fan(source)
        # In the fixed shared target, dropping a whole packet leaves its unique output unwritten.
        for packet in p['packets']:
            q=copy.deepcopy(p);event=q['events'][packet];clobber=event['effects'][0]
            q['events'][packet]=clobber
            with self.assertRaises(Rejected):produce(q)
        # Replacing any restore by the branch value admits an order with a wrong residual.
        for i,restore in enumerate(p['restores']):
            q=copy.deepcopy(p);value=source['outputs'][i]
            q['events'][restore]={'kind':'copy','value':value,'src':[1,i],'dst':[2,0]}
            with self.assertRaises(Rejected):produce(q)
            other=[j for j in range(3) if j!=i]
            order=[0,1,2]
            for j in other:order += [q['packets'][j],q['restores'][j]]
            order += [q['packets'][i],q['restores'][i],2+2*3+1,2+2*3+2,2+2*3+3]
            got,_=execute(q,[19,2,3,5],order)
            self.assertNotEqual(got[-1],19)

if __name__=='__main__':unittest.main()
