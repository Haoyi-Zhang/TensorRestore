# Refinement Certificates for User-Schedulable Tensor Programs

This standalone artifact accompanies the anonymous internal article **Restoration Frontiers for Effect-Coupled Tensor Schedules under Bounded Memory**. It implements a finite event-DAG checker, an untrusted witness producer, exact bounded semantic oracles, a modular-arithmetic interpreter, bounded tensor constructors, robustness audits, and the effect-coupled residual-fan family.

## Scientific scope

For a fixed finite sequential event DAG with exact source tags, read-before-write scalar effects, pairwise-distinct packet destinations, and an externally justified atomic packet contract, a set-valued restoration cover exactly characterizes all-order read provenance. Checked operation correspondence lifts the result to modular-32-bit output equality. A classical maximum-closure flow separately certifies a declared all-order whole-buffer occupancy bound.

A supplied restoration witness is polynomial-time checkable. Finding a smallest witness is NP-complete by a Set Cover reduction. The reference producer therefore uses a deterministic heuristic and the checker validates whatever witness it receives.

The packet comparison is conditional. In the **fixed-final-read, atom-preserving storage-recoloring class**—same source, events, edges, packets, effect computations, non-scratch destinations, and final scratch read—the shared target uses one cell, whereas every all-order single-restorer target needs at least two. A two-cell quarantine reaches the lower bound. Value forwarding changes the final-read interface. Effect splitting keeps every event identifier, restore, and edge but removes each packet's scratch subeffect, so it preserves the literal event order while changing the packet contract.

## Reproduce

From this directory:

```sh
python run.py --suite all --out reproduced
python compare.py results reproduced
python -m refcert check results/case-packet-fan-4.json
python tables.py --results results --out reproduced-tables
```

In the full project, also run:

```sh
python reference_audit.py --bib ../paper/references.bib --tex ../paper/paper.tex \
  --out results/references-summary.json
cd ../paper
python build.py
```

`run.py` uses one experiment worker; suites and public-CLI subprocesses are serial. On POSIX, the 3 GiB virtual-address and 240-second CPU guards apply per process and are inherited by children; the CPU guard is not an aggregate tree limit. `process_time` and `RUSAGE_SELF` describe only the worker, while completed-child CPU is recorded from `RUSAGE_CHILDREN`. Child RSS is neither reported nor added to the worker peak. Deterministic comparison excludes timing fields but checks eight scientific summaries, every retained case, and all non-timing CSV fields.

The representative four-branch case must be accepted with 14 events, four packet events, eight packet effects, 27 read obligations, and an exact/certified total peak of 11 abstract cells.

The flow producer sorts its immutable adjacency once before augmentation, retaining
the same ascending traversal and certificates. Focused file-free checks enumerate
small ideals independently and exercise reverse residual arcs, signed weights,
duplicate edges, consumer statistics, and checker rejections:

```sh
python -B tests/closure_regression.py
```

These six regressions run as a separate scientific-workflow step, so the retained
39-test campaign summary and its exact comparison remain unchanged. No runtime
improvement is measured or claimed.

## Frozen evidence

The deterministic expectations include the current 39-test suite and direct
checker rejection of all 647 lifetime-valid unsafe packet controls. The retained
`results/tests.txt` and `results/run-summary.json` describe the earlier 36-test
Linux run; they are historical logs, not measurements of the current test suite.
An owned Windows/CPython 3.12.14 rerun of the reviewed suite functions recovered
the same finite scientific counts. Only the unavailable POSIX `resource` import
was excluded, and `run.main` was not invoked, so this does not reproduce its
Linux CPU/RSS measurements or validate the unmodified POSIX entry point.

| Check | Frozen result |
|---|---:|
| Current unit tests | 39 passed (historical Linux run: 36) |
| Exact tagged-read cases | 298,212; production predicate called on every case; zero mismatch |
| Unsafe cases with replayed countertrace | 235,699 |
| Exact maximum-closure cases | 90,198; zero mismatch |
| Set Cover/restoration systems | 4,612; zero optimum mismatch |
| Frozen six-event holdout | 1,152 cases; 11,542 extension replays; zero mismatch |
| Metamorphic / black-box / focused mutation audits | 4 / 4 / 1; all passed |
| Tensor source instances / schedules | 40 / 234 |
| Tensor target executions | 9,360; zero mismatch |
| One-restorer tensor acceptances | 234 / 234; retained negative result |
| Packet configurations | 16, through `k=192` at recorded points |
| Packet target executions | 122,879; zero mismatch |
| Exact unrestricted / repaired orders | 116,016 / 71,225 |
| Split exact-order replays | 96 for `k=2,3`; identical original event-order sets |
| Fixed-read recolorings / order replays | 82 / 5,952; zero mismatch |
| One-cell / two-cell single-restorer acceptances | 0 / 28 |
| Unsafe packet controls | 647; all lifetime-valid, checker coverage-rejected, producer-rejected, and numerically wrong |
| Packet / restore indispensability checks | 647 / 647 |
| Largest tensor / packet target | 716 / 390 events |
| Full-project bibliography | 73 entries; all cited; metadata/closure audit passes |

Counts are finite validation evidence, not production-workload breadth. The tensor suite is deliberately unfavorable to the new certificate: every conventional schedule is accepted by the one-restorer baseline.

The bibliography script checks consistency with the supplied inventory and its
recorded reading levels; it does not fetch papers or establish citation entailment.
The prepared `Finite scientific checks` workflow runs from this flat artifact
repository on Ubuntu 24.04, retains the comparison and acceptance fail gates,
and uploads the isolated nonhidden `scientific-output/` directory even on step
failure. Preparing this workflow is not evidence of a successful remote run.

## Contents

- `refcert/checker.py` — trusted schema, provenance, packet, lifetime, and flow checks; contains the production `check_read_cover` predicate.
- `refcert/producer.py` — untrusted restoration and maximum-closure witness construction; one-restorer baseline.
- `refcert/interpreter.py` — independent modular-32-bit source/target execution.
- `refcert/oracles.py` — exact poset, provenance, memory, scalar-cleanup, and Set Cover/restoration comparisons.
- `refcert/robustness.py` — held-out, metamorphic, black-box CLI, focused coverage-mutation, and packet snapshot-semantics audits.
- `refcert/kernels.py` — eight bounded tensor families and schedule layouts.
- `refcert/packets.py` — shared residual fan, quarantine, injective recoloring, edge repair, forwarding, splitting, and exact order formulas.
- `tests/test_checker.py` — positive, forged, malformed, unsafe, packet snapshot, lifetime, source-availability, memory, split-order, and reuse tests.
- `tests/test_compare.py` — regression tests for all eight summaries, cases, and non-timing CSV comparison.
- `proofs/theory.md` — self-contained written mathematics; not proof-assistant output.
- `results/` — frozen summaries, CSVs, and concrete accepted/unsafe cases.
- `reference_inventory.csv`, `external_resources.csv`, `reference_audit.py` — bibliography inventory, evidence ledger, and closure audit.
- `claim_evidence_ledger.csv` — claim-to-proof/test/result mapping.
- `experiment-design.md`, `schema.md` — frozen experiment plan and accepted JSON contract.

## Boundaries

The checker is not a verified implementation. Producer and checker share schema/reachability code; exact execution, production-path exhaustive calls, holdout cases, mutation sensitivity, and clean reproduction reduce but do not remove that trust. The source constructors are bounded and hand-written. Packet atomicity is supplied by an external front end or target contract. Exact tags reject some numerically equivalent rewrites. Abstract cells are not RSS, cache occupancy, bank usage, or allocator bytes. No GPU, accelerator, production-compiler, physical-memory, throughput, or speedup claim is made.

Substantive generative-model assistance was used in research formulation, literature examination, proof development, implementation, testing, analysis, and documentation. Accountable human authors must independently verify science, citations, authorship, originality, disclosure, and then-current venue rules before external use.
