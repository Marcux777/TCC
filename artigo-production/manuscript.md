<!-- WORKING DRAFT. Not ready for submission. No authors or affiliations here for blind review. -->

# Constrained Online Truck Dispatching in Agroindustrial Receiving Yards

## Abstract

**Paper aims:** To design and evaluate a constrained online dispatching policy
for truck receiving yards, where each service decision must respect operational
eligibility and remain traceable.

**Originality:** The study joins event-triggered dispatching, hard feasibility
checks and decision records in a grain-receiving setting. [Position this claim
against the verified related-work corpus before submission.]

**Research method:** A discrete-event model compares a lexicographic policy
with feasible FIFO, local priority and a fixed-score dynamic rule under paired
synthetic scenarios. The protocol evaluates queue waiting, a throughput guard
and independent decision-log audits.

**Main findings:** [Insert only audited results from the complete confirmatory
campaign, with effect estimates and uncertainty. No findings are currently
available.]

**Implications for theory and practice:** [Write after the findings are known;
state the scope of inference for synthetic yards and any conditions for
operational adoption.]

**Keywords:** discrete-event simulation. queueing. decision support. operational
traceability. grain logistics.

## 1. Introduction

Grain-receiving yards must route arriving trucks through gates, scales and
unloading resources while service times and resource availability change during
the day. A dispatching decision is therefore more specific than a queue position:
when a resource becomes free, the operator needs an eligible next truck. A choice
made only from arrival order can be obstructed by documentation, load–resource
compatibility or a temporary disruption. Earlier research on grain-elevator
receiving and truck appointments motivates the operational setting
[@r.berrutoAnalyzingReceivingOperation2001a;
@abdelmagidComprehensiveReviewTruck2022a].

This article studies that decision as constrained online dispatching. The
proposed policy first excludes trucks that cannot operationally enter
the available service stage, then ranks admissible candidates by a fixed
lexicographic rule and records the inputs and rule behind the recommendation.
The discrete-event simulator supplies the experimental state and outcomes. The
same eligibility checks, event stream and logs are used for the comparison
policies, so the comparison isolates the selection rule when several candidates
are admissible.

The research question is whether the proposed rule reduces the paired median
95th percentile of accumulated queue waiting time by at least 15% against each
of three operational comparators in medium- and high-congestion strata, while
respecting a protective throughput margin. This is the prespecified comparative
hypothesis H1 in the source protocol. Safety of final recommendations (A1) and
traceability and human interpretability (A2) are separate engineering
acceptance criteria. Their status must be reported independently of the
performance comparison. The article's contribution will depend on the
confirmatory evidence; the present draft establishes the question and method.

## 2. Methods

### 2.1. Research design and system boundary

The study develops a decision-support artefact for evaluation through
discrete-event simulation. A simulated workday has a 720-minute horizon and
represents gate, inbound scale, unloading and outbound scale stages. Inputs are
synthetic and controlled. The model is intended for comparative analysis in a
defined set of scenarios, not as a calibrated prediction for a named facility.
The simulator is the source of state transitions and measurements; a planned
three-dimensional visual replay is outside the evidence used for H1.

### 2.2. Dispatching policies and scenarios

At each service opportunity, the decision procedure forms an admissible set
from the trucks available to the resource and the hard operational constraints.
If no truck is admissible, the resource remains blocked or idle according to
the registered state. Otherwise, the proposed policy applies its fixed
lexicographic ranking. The three primary comparators select, respectively, the
oldest admissible truck, the highest local operational priority with arrival
order as a tie-breaker, and the largest prespecified weighted score. Strict FIFO
is retained as a descriptive reference outside the substantive H1 test.

The confirmatory plan has 72 scenario configurations, 50 paired seeds per
configuration and five policies, yielding 18,000 planned policy-day runs. The
scenario factors vary truck count, unloading and scale capacity, and four
operating regimes. In the planned comparison, all policies for a scenario–seed pair receive the same
exogenous input. Low congestion is an operational control stratum; medium and
high congestion are the substantive strata for H1. [Before finalizing, insert a
compact table with the exact factor levels and scenario counts from the frozen
configuration and audit its consistency with the run manifests.]

### 2.3. Outcomes and decision rules

The primary outcome is the daily 95th percentile of each truck's accumulated
eligible queue waiting across service stages. Throughput counts trucks that
complete the cycle within the horizon and acts as a non-inferiority guard. For
each comparator and each substantive congestion stratum, H1 requires a paired
median waiting improvement of at least 15% and a throughput loss no greater
than max(2, 0.02 × N) trucks per day, where N is the scenario truck count. The
stratum decision is conjunctive across the three primary comparators. The
protocol prespecifies the intersection–union logic within each stratum and Holm's
adjustment to the two global stratum p-values.

Paired scenario–seed observations are the analysis unit for the Wilcoxon
signed-rank comparisons. The planned report also includes paired median and
interquartile range, Hodges–Lehmann estimates, 95% paired bootstrap intervals
from 5,000 resamples and rank-biserial effect sizes. Secondary outcomes include
system time with censoring counts, makespan, resource use and idleness,
reordering, and an exploratory estimate of idling-related CO₂. These outcomes
do not form extra confirmatory tests of H1.

### 2.4. Safety, traceability and validity

A deterministic independent audit will check final recommendations against
hard constraints (A1). Structural checks will assess all decision records for
required fields and replay consistency. A separate human review must assess
the legibility and reconstructibility of a defined sample (A2). Automatic
acceptance in the current simulator is labelled synthetic and does not
demonstrate human decision making. Face validation of parameters and scenarios
is also a distinct prerequisite. [Describe completed approvals, reviewer
sample, audit outcomes and any deviations only after the corresponding
receipts exist.]

## 3. Results

[Pending. Use audited exports only. Begin with the complete run inventory and
missingness, then stratified p95 and throughput comparisons, followed by A1/A2
and secondary outcomes. Do not insert predicted numbers or engineering smoke
results as confirmatory findings. Planned source:
`experimento-notebook/results/tables/table_h1.csv` and companion exports.]

## 4. Discussion

[Pending. Interpret the observed H1 decision, compare it with verified related
work, and state the synthetic-data, congestion-stratum, model-input and human
review limits. Keep the DES outcome separate from the planned Unreal replay.]

## 5. Conclusions

[Pending. Answer the research question only to the extent supported by the
completed campaign and audits.]

## Artificial Intelligence Use Statement

An initial outline and draft language were prepared with OpenAI Codex. [Before
submission, the authors must verify the precise tool disclosure, describe any
subsequent AI-assisted tasks, and confirm their review of all included text.]

## References

[Generate only the cited and verified entries from `../refs.bib` in APA style.
Do not carry the full TCC bibliography into the article.]
