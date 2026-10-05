# Restoration and memory certificates for finite tensor schedules

## 1. Scope and mathematical objects

This document gives human-readable proofs for the finite model implemented by the
artifact. It is not proof-assistant output and does not prove that the Python
implementation is bug-free. The executable oracles test bounded instances of the
mathematical statements. Maximum closure is a classical reduction and is used here
as an attributed component rather than claimed as a new optimization result.

The source is a finite acyclic graph of pure scalar operations over
\(R=\mathbb Z/(2^{32})\). Inputs and constants are leaves. Every other source node
uses two earlier nodes and an operation in addition, subtraction, multiplication,
or bitwise exclusive-or. A list of nodes specifies the outputs. Fixed tensor
instances are expanded to this graph; the result is not a parametric affine-language
front end.

A target contains a finite event set \(E\) and an acyclic precedence relation
\(<_P\). Its meaning is the set of sequential executions given by all linear
extensions of \(P\). This is not a weak-memory or hardware-concurrency semantics.
There are two computational event forms.

* A **scalar event** evaluates or copies one value and writes one destination.
* A **packet event** contains two or more scalar effects. Every effect reads the
  same pre-event store, all destinations are distinct, and the resulting values
  commit atomically. A schedule contract may therefore forbid deleting or moving
  a single packet subeffect while still allowing whole-packet motion.

Every write is annotated by a source-node identity, called its *tag*. Equal
numerical values from different source nodes retain different tags. Input cells
start with their input tags; output and newly allocated scratch cells start with
\(\bot\), which is not a source tag. Inputs are immutable.

Buffers have fixed positive capacities in abstract 32-bit cells. Input and output
buffers are persistent. Every scratch buffer has one allocation and one free event,
and each scratch access is ordered strictly between them. The metric excludes
interpreter objects, allocator metadata, scalar evaluator temporaries, and physical
resident memory.

## 2. Exact all-order read rule

For a read \(r\) of cell \(c\), let \(t\) be its required source tag. Let \(W_c\)
contain every writer of \(c\), including initialization. A writer is *good* when its
tag is \(t\), and *bad* otherwise. The event's own write, if any, happens after its
reads and is excluded. Define

\[
\mathcal R(r,t) \quad\Longleftrightarrow\quad
\forall w\in W_c\text{ bad},\;
  r<_P w\;\lor\;\exists g\in W_c\text{ good}: w<_P g<_P r.
\]

### Theorem 1 (exact provenance condition)

Every linear extension reads tag \(t\) at \(r\) if and only if
\(\mathcal R(r,t)\).

**Sufficiency.** Fix a linear extension and let \(w\) be the last writer before
\(r\). If \(w\) were bad, it cannot satisfy \(r<_P w\). The rule therefore supplies
a good \(g\) with \(w<_P g<_P r\), contradicting that \(w\) is last. Hence the
last writer is good.

**Necessity.** Suppose the rule fails for bad writer \(w\). Thus \(r\not<_P w\),
and no good writer lies strictly between \(w\) and \(r\). Let
\(K=\operatorname{Pred}(r)\cup\downarrow w\). This is an ideal not containing
\(r\). Among writers in \(K\) that are at or after \(w\), choose a maximal writer
\(b\). It is bad: a good such writer would be a forbidden restorer between \(w\)
and \(r\). Add an edge from every other writer in \(K\) to \(b\). A cycle would
imply an original path from \(b\) to another writer and contradict maximality.
Hence \(K\) has a linear extension in which \(b\) is its last writer. Append \(r\),
then extend the remaining events. This legal full order reads the bad tag of
\(b\). QED.

### Corollary 1 (checkable restoration set)

A certificate may provide, for each read, a set \(G_r\) of good writers preceding
\(r\). The checker accepts exactly when every dangerous bad writer precedes at
least one member of \(G_r\). Taking all good predecessors is complete. Acceptance
therefore has a polynomial-size witness and can be checked after reachability is
computed; finding a smallest witness is a separate optimization problem.

### Theorem 1.1 (minimum restoration witnesses are NP-complete)

Given one read obligation and an integer \(k\), deciding whether an accepted
restoration set of size at most \(k\) exists is NP-complete, even for one physical
cell and two tags.

**Proof.** Membership in NP follows by checking a proposed writer set against the
reachability relation. For hardness, reduce Set Cover. For every universe element
\(e\), create a bad writer \(b_e\). For every set \(S_j\), create a good writer
\(g_j\), add \(b_e<_P g_j\) exactly when \(e\in S_j\), and order every
\(g_j\) before the final read \(r\). Add one good initialization before all bad
writers; it supplies an initial correct value but cannot restore a later bad write.
Because the set family covers the universe, every \(b_e\) precedes \(r\). A chosen
good writer \(g_j\) covers exactly the bad writers whose elements lie in \(S_j\).
Thus restoration sets of size at most \(k\) correspond exactly to set covers of
size at most \(k\). The construction is polynomial. QED.

The checker does not require minimality. The reference producer uses a deterministic
maximum-new-coverage heuristic; the exact small-instance audit includes a case whose
optimum has size two while that heuristic chooses three. Soundness is unaffected
because every produced witness is checked independently.

## 3. Source-result soundness

### Theorem 2 (extensional soundness)

Assume well-formed source nodes and buffers, checked operation correspondence for
every scalar effect, distinct packet destinations, and an accepted restoration
certificate for every operand and output read. Every linear extension terminates,
uses only live in-range storage, and returns the source output vector for every
input in \(R\).

**Proof.** A finite acyclic event relation has finite linear extensions. Lifetime
checks place every scratch access after allocation and before free. Along an
arbitrary extension maintain the invariant: a cell tagged by source node \(v\)
holds the source value of \(v\). Inputs establish it. By Theorem 1, every scalar
effect reads the required tags, so the induction hypothesis gives the required
source values and the checked operator computes the declared source node.

For a packet, evaluate all of its effects against the pre-event invariant. Every
pending value is therefore correct for its tag. Distinct destinations let the
values commit together without an internal overwrite, re-establishing the
invariant after the packet. Allocation introduces only \(\bot\), free removes
cells, and read-before-write also covers scalar in-place updates. Accepted output
reads then contain exactly the declared source values. QED.

## 4. Exact scalar-cleanup boundary

Fix a declared observation interface \(\mathcal O\): all output reads and any
explicitly protected internal reads.  In this section the distinguished read
\(r\) is an element of \(\mathcal O\).  Initialization is part of the fixed input
and lifetime contract and is not eligible for deletion in the proposition below.
A family \(D\) of **noninitial scalar write effects** is jointly erasable relative
to \(\mathcal O\) when simultaneously replacing every effect in \(D\) by a no-op
at its destination, while retaining event identifiers, all precedence edges, and
every other event effect, leaves every observation in \(\mathcal O\) unchanged for
every legal linear extension.  This is stronger than deleting each member in
isolation.  Atomic packet subeffects are outside this definition when the external
schedule contract forbids splitting the packet.

### Proposition 3 (conditional single-read cleanup)

Consider a target that is safe at \(r\in\mathcal O\) in every linear extension,
with its initialization fixed.  If either (i) initialization has the required tag
and the family of all noninitial writes to the cell is jointly erasable relative
to the full interface \(\mathcal O\), or (ii) one good writer \(g<_P r\) is
retained and the family of all other noninitial writes to the cell is jointly
erasable relative to \(\mathcal O\), then erasing that family yields a
\(\mathcal O\)-equivalent target in which the distinguished read \(r\)
admits a restoration witness of size at most one. Other reads are not covered
by this conclusion unless the corresponding cleanup hypotheses also hold.

**Proof.** In case (i), erasure leaves the fixed correct initialization as the only
candidate last writer before \(r\), so the empty restoration set is sufficient. In
case (ii), erasure leaves \(g\) as the only noninitial candidate writer before
\(r\); a correct initialization is harmless, and an incorrect initialization is
ordered before and covered by \(g\). Thus at most the single restorer \(g\) is
needed. Equality of all protected observations, including \(r\), is exactly the
joint-erasability premise. QED.

Individual erasability is insufficient under this full observation definition.
Fix initialization at tag zero, let two unordered noninitial scalar effects both
write tag one, and protect a final read of tag one after both.  Deleting either
write alone preserves the protected read, whereas deleting both changes it to zero;
therefore the pair is not jointly erasable relative to \(\mathcal O=\{r\}\).  The
artifact replays this counterexample. Consequently, the bounded scalar diagnostic
does not justify a universal scalar-collapse theorem: it establishes only that its
six small set-valued separations admit an exact simultaneous cleanup preserving all
reads in that finite diagnostic. A durable positive example must instead make the
interfering effect inseparable from a required effect or another explicit interface
obligation.

## 5. Effect-coupled residual fan and the exact transformation boundary

For \(k\ge2\), the source takes \(a,x_1,\ldots,x_k\), computes
\(y_i=a\mathbin{\mathtt{xor}}x_i\), and returns
\((y_1,\ldots,y_k,a)\). The shared target allocates one scratch cell \(h\),
initializes it with \(a\), and creates, for each branch \(i\):

* an atomic packet \(p_i\) that writes \(y_i\) both to unique output \(i\) and to
  the shared cell \(h\); and
* a restore \(q_i\) that copies \(a\) to \(h\).

The order contains \(p_i<_P q_i<_P f\) for every \(i\), where \(f\) copies \(h\)
to the residual output. Apart from common initialization and finalization, the
\(k\) packet/restore pairs are unordered.

The storage lower bound needs an explicit comparison class. A **fixed-final-read
storage recoloring** preserves the source, event set, precedence edges, packet grouping, every effect's
operation, operands, result tag, and value computation, all non-scratch destinations,
and the final copy from a distinguished scratch anchor cell. It may change the
scratch-buffer capacity and reassign only packet-clobber and restore destinations
among scratch cells. Thus it
preserves the entire original order set and the final dataflow interface. It does
not permit changing the final copy to read the immutable input, changing an effect's
value, deleting an event, adding an edge, or splitting a packet.

### Theorem 4 (shared-target separation and fixed-read optimum)

For every \(k\ge2\):

1. every legal order of the shared target returns the source result;
2. the final read's minimum restoration set in the shared target has exactly \(k\)
   writers, so the single-restorer rule rejects it;
3. in the shared target, every whole packet is the unique writer of a required
   output, and removing any restore-to-final obligation admits a concrete bad order;
4. among fixed-final-read storage recolorings that retain every original order and
   pass the single-restorer rule, at least two scratch cells are necessary;
5. a two-cell **quarantine** recoloring attains that lower bound by leaving the
   anchor in cell zero and routing every packet clobber and restore to cell one;
6. an injective recoloring using one private clobber/restore cell per branch uses
   \(k+1\) cells and is correct, but it is not storage optimal;
7. making one existing restore dominate all packets adds exactly \(k-1\)
   inter-branch precedence edges, preserves the one-cell capacity, and makes the
   single-restorer rule accept;
8. directly forwarding the immutable input to the residual output preserves packet
   atoms, one-cell capacity, and all original orders and passes the single-restorer
   rule, but changes the final-read interface; the split baseline removes only each
   packet's scratch subeffect while retaining every original event identifier,
   restore, and edge, so it also matches one cell and the identical order relation
   but changes the packet contract.

**Proof.** For (1), every packet \(p_i\) is followed by its matching restore
\(q_i\), and every \(q_i\) precedes \(f\). Therefore the last writer of \(h\) before
\(f\) is some restore and has tag \(a\). Each unique output is written by its
packet from immutable inputs, so Theorem 2 applies.

For (2), each \(p_i\) is a bad writer of \(h\). Its own \(q_i\) is a good writer
with \(p_i<_P q_i<_P f\). For \(j\ne i\), \(p_i\not<_P q_j\); initialization also
precedes \(p_i\). Consequently only \(q_i\) can cover bad writer \(p_i\), so every
valid cover contains all \(k\) restores. They suffice, hence the minimum is exactly
\(k\), and no single restorer can cover all bad writers.

For (3), packet \(p_i\) is the unique writer of output \(y_i\), so deleting the
whole packet loses that output. If the obligation \(q_i<_P f\) is removed, order
all other packet/restore pairs first, then \(p_i\), then \(f\), and only then
\(q_i\). The residual output receives \(y_i\), which differs from \(a\) for, for
example, \(x_i=1\). This is a statement about the original shared target and fixed
final read, not a claim that a later interface rewrite can never make a restore
dead.

For (4), a one-cell recoloring has only the distinguished anchor destination.
Every packet clobber and every restore therefore still writes that cell, while the
event relation is unchanged. The argument for (2) applies verbatim, so the
single-restorer rule rejects. Hence any accepting recoloring in the stated class
needs at least two cells.

For (5), allocate cells \(h_0,h_1\). Keep initialization and final copy on
\(h_0\), and redirect every packet clobber and restore to \(h_1\). No event can
write \(h_0\) after initialization, so the final read has no dangerous writer and
the single-restorer rule accepts. Events, edges, packets, and all original linear
extensions are unchanged. Thus two cells suffice and the lower bound is tight.

For (6), give branch \(i\) a separate cell for both \(p_i\)'s clobber and \(q_i\)'s
restore while retaining an anchor cell. This uses \(k+1\) cells, preserves the
fixed-read interface, and leaves the anchor unmodified. It is a transparent
construction but is dominated in storage by quarantine.

For (7), choose \(q_1\) and add \(p_i<_P q_1\) for every \(i\ne1\). Then \(q_1\)
covers every bad packet and is a single restorer. For the lower bound, contract each
original branch pair \(p_i<_P q_i\) to one vertex and ignore the common source and
finalization vertices, which cannot create a path from one branch to another without
a cycle. Initially the \(k\) branch vertices are disconnected. If one restore is
to follow every packet, every branch vertex must have a directed path to its branch
vertex; the underlying undirected graph on the contracted branches must therefore
be connected. Connecting \(k\) isolated vertices requires at least \(k-1\) added
inter-branch edges. The construction uses exactly that many. No buffer changes, so
capacity is unchanged.

For (8), change only \(f\)'s source from \(h\) to the immutable input cell holding
\(a\). Packet atoms and precedence edges remain intact, but the distinguished
scratch read has been replaced, so this transformation lies outside fixed-final-read
recoloring.  For the split construction, start from the shared graph, retain every
event identifier, restore, and edge, and replace each packet at the same event site
by its surviving scalar output effect.  Only the scratch-clobber subeffect is
removed.  The reachability relation and linear-extension set are therefore
literally unchanged rather than compared through a projection; the retained
restores keep the final anchor correct.  This target changes the packet/effect
contract.  Both constructions show why atomicity by itself is insufficient for a
universal one-cell advantage. QED.

### Corollary 4.1 (exact order-space cost of edge repair)

The shared schedule has

\[
N_k=\frac{(2k)!}{2^k}
\]

middle-region linear extensions. After choosing \(q_1\) as the dominating restore,
its count is

\[
M_k=(k-1)!\sum_{m=0}^{k-1}\frac{(k+m)!}{2^m m!}.
\]

**Proof.** The unrestricted region consists of \(k\) independent ordered pairs,
so exactly one of the two internal orders survives for each pair. For the repaired
region, let \(m\) be the number of other restores placed before \(q_1\). Choose
those branches, order all \(k\) packets and those \(m\) restores subject to their
\(m\) pair constraints, place \(q_1\), then order the remaining restores. The
factor
\(\binom{k-1}{m}(k+m)!/2^m\,(k-1-m)!\) simplifies to the summand above. QED.

The precise design result is therefore conditional. Inside fixed-final-read
atom-preserving storage recoloring, the set-valued shared target saves exactly one
scratch cell over the optimal all-order single-restorer layout; edge repair instead
spends order freedom. Outside that class, value forwarding removes the storage
separation and effect splitting removes the atomicity premise. The injective
\(k+1\)-cell layout is useful as a simple reference, not as a lower bound.

## 6. Exact abstract-buffer peak

Let \(M_0\) be persistent capacity. Give allocation of a buffer of size \(s\) weight
\(+s\), its free weight \(-s\), and every other event weight zero. For an event
prefix \(I\), occupancy is \(M_0+\sum_{e\in I}w(e)\).

### Lemma 5 (prefix/ideal correspondence)

A prefix of a linear extension is an ideal of \(P\), and every ideal is a prefix of
some linear extension. The latter follows by concatenating a linear extension of
the ideal with one of its complement; no edge enters an ideal from its complement.
Hence

\[
M_{\max}=M_0+\max_{I\text{ ideal}}\sum_{e\in I}w(e).
\]

### Theorem 6 (flow upper certificate and optional tight ideal)

Let \(W^+=\sum_{w(e)>0}w(e)\). Build a network with source \(S\), sink \(T\), arc
\(S\to e\) of capacity \(w(e)\) for positive weights, arc \(e\to T\) of capacity
\(-w(e)\) for negative weights, and arc \(v\to u\) of capacity \(W^++1\) for each
precedence edge \(u\to v\). Any feasible integral flow of value \(F\) certifies

\[
M_{\max}\le M_0+W^+-F.
\]

A maximum flow reaches equality. A downward-closed ideal with the same weight may
be supplied as an independently checked tightness witness.

**Proof.** For any ideal \(I\), the cut \(\{S\}\cup I\) crosses no large precedence
arc and has capacity \(W^+-\sum_{e\in I}w(e)\). Flow conservation and capacities
bound \(F\) by every such cut, proving the upper bound. A minimum cut cannot use an
arc of capacity \(W^++1\), because the source-only cut costs \(W^+\); its event
vertices therefore form an ideal. Integral augmenting paths give a maximum flow
whose value equals that cut, yielding equality. QED.

This is the classical maximum-closure construction. The contribution here is its
use as a small independently checkable resource witness alongside the read
certificate, not the reduction itself.

## 7. Refinement by adding precedence edges

### Theorem 7 (core-certificate reuse)

If \(P'\) is obtained from \(P\) only by adding edges while preserving acyclicity,
then an accepted restoration set and feasible flow for \(P\) remain valid for
\(P'\). The same numerical memory budget remains an upper bound. An optional tight
ideal need not remain an ideal and must be omitted or rechecked.

**Proof.** Reachability can only grow. A good writer that covered a bad writer under
\(P\) still covers it, and more bad writers may become forced after the read. The
closure network gains finite-capacity precedence arcs; assigning zero flow to new
arcs preserves the old flow's capacities and conservation. Hence the old upper
bound remains certified. Added predecessors can invalidate downward closure of a
previous ideal, and the true maximum can decrease, so tightness is not reusable in
general. QED.

## 8. Boundaries of the result

Theorems concern sequential linear extensions, exact source tags, fixed finite
programs, whole-buffer abstract occupancy, and explicit atomic packet boundaries.
They do not establish numerical completeness when different tags happen to have
equal values, optimal schedule synthesis, a production tensor front end, physical
memory usage, GPU behavior, throughput, or weak-memory safety. Packet splitting is a legitimate stronger compiler transformation when an external
semantics proves it legal.  Even when packet atoms are fixed, direct value forwarding
can eliminate the one-cell separation by changing the final dataflow interface.  The
storage optimum in Theorem 4 therefore applies only to the explicitly defined
fixed-final-read recoloring class; the broader contribution is the exact boundary,
not universal dominance over compiler rewrites.

The Python producer and checker share structural parsing and reachability code.
Finite enumeration, mutation tests, formula checks, and clean reproduction provide
engineering evidence, not an independently mechanized correspondence proof.
