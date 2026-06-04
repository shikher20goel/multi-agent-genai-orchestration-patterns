# Draft manuscript edit: abstract + scope reframe (Task 059, HUMAN-gated)

Converts the manuscript's "prospective rig" language to an "executed
study on an open mock rig", with placeholder slots
`[USER: INSERT GITHUB URL]` and `[USER: INSERT DOI]`. The original
passages are quoted verbatim from the submitted PDF for diffing.
[HUMAN: insert final links, verify every quoted original against the
current PDF, and approve before any edit lands in the manuscript.]

---

## 1. Original abstract (quoted from the submitted PDF)

> "Enterprises building multi-agent generative artificial intelligence
> (AI) systems must decide how to wire several large language model
> (LLM) agents together—which agent supervises which, how control and
> data flow, where humans intervene, and how the topology spans an
> enterprise customer-relationship-management (CRM) platform and a
> hyperscaler cloud. These wiring decisions are made ad hoc, paper by
> paper and project by project, because the field has no shared
> catalog of integration patterns comparable to the
> enterprise-integration-pattern catalogs that organized
> message-oriented middleware two decades ago. This paper contributes
> such a catalog: seven named integration patterns for multi-agent
> generative AI orchestration—Supervisor–Collaborator Hierarchy,
> Sequential Pipeline, Event-Driven Choreography, Shared-Memory
> Blackboard, Tool-Routed Gateway, Human-in-the-Loop Adjudication, and
> Federated Cross-Platform Bridge. Each pattern is presented under a
> uniform nine-element template, platform-agnostic first and then with
> two parallel reference instantiations on Salesforce Agentforce 360
> and Amazon Bedrock. The paper specifies a reproducible reference
> implementation and a prospective evaluation rig—a synthetic load
> generator, a fault-injection campaign, and a cost-capture
> harness—released as open code so that the latency, cost, and
> fault-isolation behavior of each pattern can be measured by any
> reader. In place of a measurement campaign, which the released rig
> enables but which is out of scope here, the paper provides a
> structural consequence analysis: a directional account, grounded in
> established distributed-systems results, of how each pattern behaves
> on three platform-stress scenarios, together with a
> pattern-selection decision tree. The contribution is the catalog,
> the reference implementations, and the rig; an empirical measurement
> study executing the rig is the immediate next step."

## 2. Revised abstract (proposed)

Enterprises building multi-agent generative artificial intelligence
(AI) systems must decide how to wire several large language model
(LLM) agents together—which agent supervises which, how control and
data flow, where humans intervene, and how the topology spans an
enterprise customer-relationship-management (CRM) platform and a
hyperscaler cloud. These wiring decisions are made ad hoc, paper by
paper and project by project, because the field has no shared catalog
of integration patterns comparable to the
enterprise-integration-pattern catalogs that organized
message-oriented middleware two decades ago. This paper contributes
such a catalog: seven named integration patterns for multi-agent
generative AI orchestration—Supervisor–Collaborator Hierarchy,
Sequential Pipeline, Event-Driven Choreography, Shared-Memory
Blackboard, Tool-Routed Gateway, Human-in-the-Loop Adjudication, and
Federated Cross-Platform Bridge. Each pattern is presented under a
uniform nine-element template, platform-agnostic first and then with
two parallel reference instantiations on Salesforce Agentforce 360 and
Amazon Bedrock. The paper then reports an executed measurement study
on an open, deterministic mock rig released with the paper: a
synthetic open-loop load generator, a 336-cell fault-injection
campaign, and a cost-capture harness drive every pattern on locally
mocked instantiations of both platforms across three platform-stress
scenarios (42 baseline conditions, n = 500 requests each), with 95%
BCa bootstrap confidence intervals, Mann–Whitney comparisons with
effect sizes, and Holm correction throughout. The study quantifies
each pattern's latency, cost, and fault-isolation behavior—including
which topologies saturate under open-loop load and an executed
fault-containment matrix with zero propagation cells—and grounds a
pattern-selection decision tree and a governance mapping (EU AI Act
Article 14, NIST AI RMF, ISO/IEC 42001) backed by a runnable
human-oversight example. Because the platforms are mocked, the
study's claims are comparative and structural rather than absolute;
the full artifact, regenerating every table and figure from one
command, is released at [USER: INSERT GITHUB URL] (archived DOI:
[USER: INSERT DOI]).

## 3. Original scope passages (quoted from the submitted PDF)

Introduction (Section I):

> "A scope statement is load-bearing. This paper is a pattern catalog
> with a prospective rig, not a completed measurement campaign. The
> catalog's value, in the tradition of [1], [2], [3], is the
> abstraction itself and the reproducible reference implementations;
> empirical measurement of the abstraction is a distinct, subsequent
> contribution that the released rig enables for any reader. In place
> of measured numbers, the paper provides a structural consequence
> analysis: a directional account, grounded in established
> distributed-systems results on tail latency [26], datacenter
> behavior [27], and failure containment [28], of how each pattern
> behaves on three platform-stress scenarios. This posture is
> deliberate: it avoids reporting measurements that have not been
> taken, and it produces a catalog that is content-complete and
> immediately usable."

Section III.D ("SCOPE: A CATALOG WITH A PROSPECTIVE RIG"):

> "This paper presents the catalog and a prospective evaluation rig.
> The rig (Section V) is released as open code so that the structural
> consequences of Section VI can be measured; the measurement campaign
> itself is a distinct contribution, identified as the immediate next
> step (Section VIII). Section VI is therefore titled a structural
> consequence analysis, not a results section, and reports directional
> structural reasoning grounded in [26], [27], [28], never measured
> values. This scope is consistent with the catalog tradition [1],
> [2], in which the catalog and its empirical validation are separate
> contributions."

Artifact statement (Section VIII vicinity):

> "...six rejected candidate patterns) are released at [USER: INSERT
> GitHub URL] under a permissive open-source license, with an
> executable capsule at [USER: INSERT Code Ocean DOI] and
> machine-readable citation metadata. The package targets the IEEE
> Access Code Available badge; the Code Reviewed badge is deferred,
> because it requires independent reproduction of a measurement
> campaign that this paper, by its Tier-A scope, does not perform."

## 4. Revised scope passages (proposed)

Introduction (replacement):

A scope statement is load-bearing. This paper is a pattern catalog
**with an executed measurement study on an open mock rig**. The
catalog's value, in the tradition of [1], [2], [3], remains the
abstraction itself and the reproducible reference implementations; the
study adds executed evidence for the catalog's structural-consequence
claims. The rig mocks both platforms locally with documented interface
shapes and configured service-time and cost models, runs entirely on a
virtual clock from a fixed seed, and regenerates every reported table
and figure from a single command. Because the platforms are mocked,
the measured numbers are comparative and structural — they order the
patterns and exhibit isolation properties under a common synthetic
environment — and carry no claim about absolute production
performance, a limitation analyzed in the threats-to-validity
discussion. The artifact is released at [USER: INSERT GITHUB URL]
(archived DOI: [USER: INSERT DOI]).

Section III.D (replacement; retitle to "SCOPE: A CATALOG WITH AN
EXECUTED MOCK-RIG STUDY"):

This paper presents the catalog and an executed evaluation on the
released rig. The rig (Section V) is open code; the measurement study
(Section: Executed Measurement Study) reports its results — 42
baseline conditions at n = 500 with bootstrap confidence intervals and
a 336-cell fault campaign (trace: results/manifest.json). Section VI's
structural consequence analysis is retained as the *predictions* the
study tests, with directional reasoning grounded in [26], [27], [28];
where measured values exist they supersede directional statements.
Mock fidelity, not absence of measurement, is now the study's
principal limitation, and is treated explicitly as a threat to
validity. This scope remains consistent with the catalog tradition
[1], [2]: the abstraction is the contribution, and its open, executed
evaluation strengthens rather than replaces it.

Artifact statement (replacement):

...six rejected candidate patterns (docs/REJECTED_CANDIDATES.md), the
executed study's full provenance (results/manifest.json), and the
governance mappings are released at [USER: INSERT GITHUB URL] under
the Apache-2.0 license, with an executable capsule at
[USER: INSERT DOI] and machine-readable citation metadata
(CITATION.cff). The package targets the IEEE Access Code Available
badge, and — because the measurement campaign is now executed and
regenerable by one command (`bash run.sh`) — the Code Reviewed badge
is within reach via independent reproduction.

## 5. Change list vs. the current PDF abstract

1. **"prospective evaluation rig" → "executed measurement study on an
   open, deterministic mock rig"** (the central reframe).
2. Deleted: "In place of a measurement campaign, which the released
   rig enables but which is out of scope here..." — the campaign is no
   longer out of scope; the structural consequence analysis is
   repositioned as the predictions the study tests.
3. Deleted: "an empirical measurement study executing the rig is the
   immediate next step." — replaced by the study's headline facts
   (42 conditions × n = 500; 336 fault cells; BCa CIs; Mann–Whitney +
   Holm; zero propagation cells) — all traced to
   results/manifest.json, figures/table3.csv, and results/faults.csv
   per docs/manuscript/results_section.md.
4. Added: explicit mock-fidelity caveat in the abstract ("claims are
   comparative and structural rather than absolute") so the reframe
   does not overclaim.
5. Added: governance deliverables (Art. 14 / NIST AI RMF / ISO 42001
   mappings + runnable HITL example) now part of the contribution
   sentence.
6. Added: artifact slots [USER: INSERT GITHUB URL] and
   [USER: INSERT DOI] in the abstract's final sentence; the PDF's
   "[USER: INSERT Code Ocean DOI]" slot is normalized to
   [USER: INSERT DOI].
7. Scope passages (Sections I and III.D) revised in parallel (Section
   4 above); Section III.D retitled.
8. Index terms: [HUMAN: consider adding "fault injection" and
   "performance evaluation" to INDEX TERMS to match the executed
   study.]

[HUMAN: verify all quoted originals character-for-character against
the submitted PDF; insert the final GitHub URL and DOI; approve the
saturation and zero-propagation phrasing after re-checking
figures/table3.csv and results/faults.csv.]
