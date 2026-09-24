# Refinement Certificates for User-Schedulable Tensor Programs

This standalone artifact accompanies the anonymous internal article **Restoration Frontiers for Effect-Coupled Tensor Schedules under Bounded Memory**. It implements a finite event-DAG checker, an untrusted witness producer, exact bounded semantic oracles, a modular-arithmetic interpreter, bounded tensor constructors, robustness audits, and the effect-coupled residual-fan family.

## Scientific scope

For a fixed finite sequential event DAG with exact source tags, read-before-write scalar effects, pairwise-distinct packet destinations, and an externally justified atomic packet contract, a set-valued restoration cover exactly characterizes all-order read provenance. Checked operation correspondence lifts the result to modular-32-bit output equality. A classical maximum-closure flow separately certifies a declared all-order whole-buffer occupancy bound.

A supplied restoration witness is polynomial-time checkable. Finding a smallest witness is NP-complete by a Set Cover reduction. The reference producer therefore uses a deterministic heuristic and the checker validates whatever witness it receives.

The packet comparison is conditional. In the **fixed-final-read, atom-preserving storage-recoloring class**—same source, events, edges, packets, effect computations, non-scratch destinations, and final scratch read—the shared target uses one cell, whereas every all-order single-restorer target needs at least two. A two-cell quarantine reaches the lower bound. Value forwarding and effect splitting escape by changing, respectively, the final-read interface and packet contract.

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

`run.py` uses only the Python standard library, one process, a 3 GiB virtual-address guard, and a 240-second CPU guard. Timing and RSS are excluded from deterministic comparison.

The representative four-branch case must be accepted with 14 events, four packet events, eight packet effects, 27 read obligations, and an exact/certified total peak of 11 abstract cells.

## Frozen evidence

| Check | Frozen result |
|---|---:|
| Unit tests | 29 passed |
| Exact tagged-read cases | 298,212; production predicate called on every case; zero mismatch |
| Unsafe cases with replayed countertrace | 235,699 |
| Exact maximum-closure cases | 90,198; zero mismatch |
| Set Cover/restoration systems | 4,612; zero optimum mismatch |
| Frozen six-event holdout | 1,152 cases; 11,542 extension replays; zero mismatch |
| Metamorphic / black-box / mutation audits | 4 / 4 / 1; all passed |
| Tensor source instances / schedules | 40 / 234 |
| Tensor target executions | 9,360; zero mismatch |
| One-restorer tensor acceptances | 234 / 234; retained negative result |
| Packet configurations | 16, through `k=192` at recorded points |
| Packet target executions | 122,783; zero mismatch |
| Exact unrestricted / repaired orders | 116,016 / 71,225 |
| Fixed-read recolorings / order replays | 82 / 5,952; zero mismatch |
| One-cell / two-cell single-restorer acceptances | 0 / 28 |
| Unsafe packet controls | 647; all rejected and numerically wrong |
| Packet / restore indispensability checks | 647 / 647 |
| Largest tensor / packet target | 716 / 390 events |
| Full-project bibliography | 73 entries; all cited; audit PASS |

Counts are finite validation evidence, not production-workload breadth. The tensor suite is deliberately unfavorable to the new certificate: every conventional schedule is accepted by the one-restorer baseline.

## Contents

- `refcert/checker.py` — trusted schema, provenance, packet, lifetime, and flow checks; contains the production `check_read_cover` predicate.
- `refcert/producer.py` — untrusted restoration and maximum-closure witness construction; one-restorer baseline.
- `refcert/interpreter.py` — independent modular-32-bit source/target execution.
- `refcert/oracles.py` — exact poset, provenance, memory, scalar-cleanup, and Set Cover/restoration comparisons.
- `refcert/robustness.py` — held-out, metamorphic, black-box CLI, and mutation-sensitivity audits.
- `refcert/kernels.py` — eight bounded tensor families and schedule layouts.
- `refcert/packets.py` — shared residual fan, quarantine, injective recoloring, edge repair, forwarding, splitting, and exact order formulas.
- `tests/test_checker.py` — positive, forged, malformed, unsafe, packet, lifetime, source-availability, memory, and reuse tests.
- `proofs/theory.md` — self-contained written mathematics; not proof-assistant output.
- `results/` — frozen summaries, CSVs, and concrete accepted/unsafe cases.
- `reference_inventory.csv`, `external_resources.csv`, `reference_audit.py` — bibliography inventory, evidence ledger, and closure audit.
- `claim_evidence_ledger.csv` — claim-to-proof/test/result mapping.
- `experiment-design.md`, `schema.md` — frozen experiment plan and accepted JSON contract.

## Boundaries

The checker is not a verified implementation. Producer and checker share schema/reachability code; exact execution, production-path exhaustive calls, holdout cases, mutation sensitivity, and clean reproduction reduce but do not remove that trust. The source constructors are bounded and hand-written. Packet atomicity is supplied by an external front end or target contract. Exact tags reject some numerically equivalent rewrites. Abstract cells are not RSS, cache occupancy, bank usage, or allocator bytes. No GPU, accelerator, production-compiler, physical-memory, throughput, or speedup claim is made.

Substantive generative-model assistance was used in research formulation, literature examination, proof development, implementation, testing, analysis, and documentation. Accountable human authors must independently verify science, citations, authorship, originality, disclosure, and then-current venue rules before external use.
