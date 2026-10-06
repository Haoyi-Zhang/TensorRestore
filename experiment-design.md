# Frozen experiment design

## Questions

1. Does the exact last-writer semantics agree with the theorem formula?
2. Does the shipped production read-cover predicate agree with exact semantics?
3. Does the maximum-closure producer/checker agree with exact ideal enumeration?
4. Is minimum witness selection exactly Set Cover on the reduction instances?
5. Does the scalar motivation survive a correct **joint** cleanup test?
6. Do bounded tensor targets preserve direct mathematical results and certified peaks?
7. Does the effect-coupled family realize the proved transformation boundary?
8. Are results robust to held-out structures, representation metamorphisms, malformed inputs, and a targeted mutant?

## Exact provenance universe

For naturally labeled posets with 2–5 events, enumerate every poset, read position, writer/no-writer assignment over two tags, and initial tag. For every case:

- enumerate legal extensions until a bad trace is found or all pass;
- evaluate the independent theorem formula;
- invoke the production `check_read_cover` predicate using an explicit initialization event;
- require all three decisions to agree.

Frozen result: 298,212 cases, 235,699 unsafe cases with replayed countertraces, zero mismatch.

## Exact memory universe

For naturally labeled posets with 2–5 events and weights in `{-2,0,3}`, enumerate every downward-closed ideal and compare the exact maximum with the producer’s flow, the checker’s independently validated bound, and the producer’s tight ideal.

Frozen result: 90,198 weight cases, zero mismatch.

## Minimum-witness reduction

Enumerate every covering family of unique nonempty subsets for universes of size 1–4, with at most five sets. Compare brute-force minimum Set Cover size with the minimum accepted restoration witness under the reduction, including its explicit good initialization before every event. Initialization covers no bad writer and is omitted from minimum candidates because selecting it is redundant. The reduction preserves optimum and decision existence, not a bijection of redundantly padded witnesses. Retain a fixed system where the producer-style maximum-new-coverage heuristic uses three writers although the optimum uses two.

Frozen result: 4,612 systems, zero optimum mismatch.

## Scalar cleanup diagnostic

Enumerate mixed read/write assignments for posets through five events. The declared observation interface contains every protected output/internal read, including the distinguished read; initialization is fixed input/lifetime state and is not deletable. Retain universally safe cases and remove the **joint family** of noninitial write effects that are never last before any observation in that full interface. Report the six bounded set-valued separations before cleanup and zero after cleanup. Separately replay:

- a three-event example with fixed zero initialization, two unordered writes of one, and protected read `r`: either write is individually erasable relative to `{r}`, but deleting both changes `r` from one to zero; and
- a six-event caution where potential observability does not imply indispensability.

This is bounded negative evidence, not a universal scalar theorem.

## Frozen holdout and robustness

After the production predicate was fixed, freeze seed `8675309` and generate 96 six-event DAGs. Evaluate 12 assignments per DAG by exact extension replay and the production predicate. Do not tune the checker or seed after examining outcomes.

Also check:

- edge/certificate ordering, redundant transitive edges, internal event alpha-renaming, and JSON key-order metamorphisms;
- three malformed public-CLI cases, requiring structured rejection without traceback;
- one accepted public-CLI case; and
- a focused certificate whose supplied restorer is legal but fails to cover one possible wrong last writer: the unchanged checker must reject with `possible wrong last writer`, while a mutant deleting only that coverage test accepts; and
- a packet cross-read/write case with `a != x`, both effect orders, a local sequential-commit mutant, and an uninitialized same-packet-source rejection.

Frozen result: 1,152 holdout cases, 11,542 extension replays, four metamorphic checks, four CLI checks, one focused missing-coverage mutant exposed, two initialized packet effect orders invariant under snapshot commit, one sequential-commit mutant exposed, and both producer and snapshot interpreter rejecting the uninitialized same-packet source. The latter negative case does not directly invoke the certificate checker.

## Bounded tensor suite

Use eight hand-written mathematical families: pointwise, stencil, separable box, matrix-vector, matrix-matrix, prefix, Jacobi-like, and convolution. Evaluate dimensions 2–6. Compare the source graph with a separately written direct formula on five deterministic input vectors. Compile materialized, tiled, and folded layouts with representative lane counts; replay eight deterministic linearizations on every input.

Frozen result: 40 source instances, 234 schedule configurations, 200 source/formula comparisons, 9,360 target executions, and 234 edge-refinement certificate reuses. Every schedule is accepted by the one-restorer baseline; this is reported as a null result.

## Effect-coupled packet suite

Use branch counts `2,3,4,5,6,7,8,12,16,24,32,48,64,96,128,192`. For each, compare:

1. one-cell shared set-valued restoration;
2. two-cell fixed-read quarantine;
3. injective `k+1`-cell recoloring;
4. minimum-edge one-restorer repair;
5. one-cell final-value forwarding; and
6. split effects outside the atom-preserving contract.

Enumerate every unrestricted and repaired middle-region order through `k=5`; use exact formulas plus deterministic representative executions for larger `k`. The split constructor must retain every event identifier, restore, and edge and remove only scratch packet subeffects. For `k=2,3`, compare its complete event-order sets literally with the original 6 and 90 orders and replay all 96. Also exhaust every one/two-cell clobber/restore assignment for `k=2,3` and replay every legal order numerically. Weaken each restore-to-final edge to a restore-to-free edge in turn, preserving the lifetime and entry/exit requirements, and replay a constructed numeric counterorder. Require the trusted checker to reject for `possible wrong last writer` with every legal good predecessor supplied, and separately require producer rejection for `no restoring-writer cover`.

Frozen result: 16 configurations, 122,879 target executions, 116,016 unrestricted orders, 71,225 repaired orders, 96 exact split-order replays with identical order sets, 82 layouts, 5,952 layout-order replays, 647 unsafe controls, and zero mismatch.

## Overfitting interpretation

There is no learned model, parameter fitting, benchmark selection by score, or statistical performance inference. The principal risk is that theorem examples and tests share construction assumptions. Exact complete small universes, a structurally different Set Cover encoding, a frozen larger-event holdout, representation metamorphisms, mutation sensitivity, unfavorable tensor results, and interface-changing counterbaselines reduce that risk. They do not establish production prevalence or real-world performance.

## Resources and determinism

The runner uses one experiment worker, serial suites, and serial public-CLI subprocesses; it uses no network, solver, GPU, model/API, private data, or external compute. On POSIX, the 3 GiB virtual-address and 240-second CPU guards are per process and inherited by children, not aggregate process-tree budgets. `process_time` and `RUSAGE_SELF` measure the worker; completed-child CPU comes from `RUSAGE_CHILDREN`; child RSS is not reported or summed. The reference run was Linux 6.18.44 with CPython 3.13.5; earlier frozen-run OS/Python details are unknown and not recoverable. Deterministic comparison excludes timing fields and compares eight scientific summaries, all case files, and every non-timing CSV field.
