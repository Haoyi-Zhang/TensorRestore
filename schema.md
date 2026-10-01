# Explicit finite program and witness schema

The command-line checker consumes one UTF-8 JSON object, at most 8 MiB, with fields `program`, `certificate`, and integer `budget_cells`. Other fields such as an input vector or replay evidence are ignored by certificate checking. JSON booleans are not accepted as integer identifiers or budgets. This is a scientific prototype schema, not a hardened general-purpose input service.

## Source and storage

`program.source` contains `inputs`, `nodes`, and `outputs`. There are 1–5,000 nodes, at least one input, and 1–256 output references. The first `inputs` nodes are `{"op":"input","index":i}` in order. Other nodes are constants `{"op":"const","literal":k}` with 0 <= k < 2^32, or `{"op":OP,"args":[a,b]}`. OP is `add`, `sub`, `mul`, or `xor`; a and b refer to preceding nodes. Output references may be any source nodes. A node identity, not its computed integer, is a provenance tag.

`program.buffers` is a list of 2–128 objects with integer `cells` in 1–10,000 and boolean `persistent`. Buffer zero is the persistent read-only input and its size equals the input count. Buffer one is the persistent output and its size equals the output count. All later buffers are scratch. Total declared capacity is at most 100,000 cells. Locations are `[buffer_id, cell_index]` with constant, in-range indices. Different buffer identities never alias.

## Events and precedence

`program.events` has 2–2,500 events, starting with exactly `{"kind":"entry"}` and ending with exactly `{"kind":"exit"}`. Entry precedes all events and exit follows all events. `program.edges` contains at most 20,000 pairs `[before,after]`. Duplicate pairs are semantically harmless; self edges and cycles are rejected. Reachability, not the order of the edge list, gives precedence.

Every scratch buffer has exactly one `{"kind":"alloc","buffer":b}` and one `{"kind":"free","buffer":b}`. Allocation must precede free. Every scratch access is strictly after allocation and before free in the partial order. Allocation initializes each cell to bottom. Entry initializes inputs to their source tags and outputs to bottom.

An evaluation is `{"kind":"eval","value":v,"op":OP,"args":[LOC,LOC],"dst":LOC}`. Its source tag v must denote the exact stated source operation. For a constant, `args` is empty and `literal` must match the source constant. Other evaluations must have exactly two operand locations. The required operand tags are obtained from the source node's ordered arguments. An evaluation cannot create an input node. All operands are snapshotted before the result is written.

A copy is `{"kind":"copy","value":v,"src":LOC,"dst":LOC}` and requires source tag v at its source location. A write to input storage is forbidden.

A packet is `{"kind":"packet","effects":[E1,...,Em]}` with 2--16 scalar `eval` or `copy` effects. Every effect is checked against the same source and location rules as a scalar event. Packet destinations must be pairwise distinct. All effects read the pre-event store and their values commit together, so one effect cannot observe another effect's pending write. The conformance test stores `a` in scratch `h`, then places `h <- x` and `out <- old(h)` in one packet with `a != x`; both effect-list orders must return `a`. If `h` is uninitialized, the same-packet write cannot make the later effect legal, and both checker and snapshot interpreter reject. The packet is one precedence atom: the schema has no edge to an individual subeffect and certificate checking does not authorize deleting or moving one subeffect. Whether a stronger external compiler may split a packet is a separate semantic obligation, not inferred here.

Exit implicitly reads each output cell with the corresponding source output tag. Numeric execution uses actual operations and loads, not just declared result tags.

## Certificate

`certificate.rescue` is a list with one list of writer-event IDs per read. Reads are ordered by event-list order: scalar evaluation operands in argument order, scalar copy sources, then each packet effect's reads in effect-list order, followed by all output reads in output order. A listed writer must write the same physical cell with the required tag and strictly precede the read. Duplicate writer IDs are rejected. Every bad writer not forced after the read must precede a listed good writer. The read's own write is excluded because the read occurs first.

`certificate.flow` contains distinct triples `[u,v,f]`. For n events, network source is n and sink is n+1. Positive-weight event e has source-to-e capacity w(e); negative-weight e has e-to-sink capacity -w(e). A schedule edge u-to-v induces a reversed v-to-u arc of capacity W+ + 1. Unlisted flows are zero. Listed flows must be nonnegative integers, respect capacities, and conserve flow at event vertices. A feasible value F yields the checked bound persistent_cells + W+ - F. That bound, not a separately asserted peak, must be <= `budget_cells`.

Optional `certificate.peak_ideal` is a duplicate-free list of events closed under all predecessors. Its signed weight plus persistent capacity must equal the flow upper bound. It proves tightness for the fixed graph. The checker returns `exact_peak_cells: null` when the ideal is omitted; upper-bound acceptance remains meaningful.

Adding only schedule edges preserves the core lists and old flow, with implicit zero flow on new arcs. It need not preserve the ideal. Source changes, layout changes, deleted edges, or buffer-size changes require fresh checking and are not covered by the reuse theorem.

## Admission is not a performance theorem

The finite mathematical statements are not restricted to the implementation's numerical admission limits. Conversely, acceptance of a size within the schema is not a measured worst-case runtime or process-memory guarantee. The largest frozen tensor-kernel graph has 716 events; the largest effect-coupled packet graph has 390 events and 384 packet subeffects. The runner's CPU/address-space limits are operational guards, separate from the abstract occupancy certificate. They are POSIX per-process limits inherited by serial CLI children, not aggregate process-tree limits; reported `process_time`/`RUSAGE_SELF` values cover the main worker, while completed-child CPU is recorded separately and child RSS is not reported or summed.
