# Framing Principles

This reference distills the design principles, calibration patterns, and
section-specific framing rules that govern the framing producer.

## Core Principles

1. **Argument first, prose second.** The storyline_map is an argument
   scaffold, not a writing plan. Every element (question, angle,
   contribution type) must be defensible before any prose is written.

2. **Evidence first, ambition second.** The angle must survive the
   available evidence, not the desired narrative. Low-provenance
   materials weaken the angle.

3. **One main line, not a pile of results.** The storyline must have
   a single dominant direction. Supporting results strengthen the main
   line; they do not compete with it.

4. **Precision over flourish.** Prefer the weakest verb that still
   truthfully captures the evidence. "Suggests" is stronger than
   "reveals" when the evidence only suggests.

5. **Flow should feel inevitable, not decorative.** A good angle makes
   the reader feel the conclusion was unavoidable given the evidence.

6. **Author exemplars teach control logic, not surface mannerisms.**
   AB/JE exemplars (see `exemplars/ab/` and `exemplars/je/`) are for
   learning argument structure, not for copying style.

## Contribution Type Taxonomy

Every paper has one dominant contribution type:

| Type | Definition | Anti-pattern |
|------|-----------|--------------|
| **new empirical pattern** | A previously unobserved regularity, demonstrated with data | Dataset description masquerading as contribution |
| **new mechanism** | A causal or generative explanation for a pattern, tested against alternatives | Pattern asserted as mechanism without minimal-mechanism test |
| **new measure** | A quantitative or conceptual tool that captures something previously unmeasured | Metric introduced without justification for why existing measures fail |
| **new method** | A procedure or framework that solves a problem better than alternatives | Capability demo presented as methodological advance |
| **new implication** | A consequence of existing findings that changes how a field thinks | Speculation presented as demonstrated implication |

## Calibration Patterns

These four patterns appear repeatedly in high-impact framing. Use them
as structural templates, not word templates.

### Pattern 1: Stakes -> Gap Compression

**Structure:** broad importance -> precise unresolved question

**Good:**
> "Human mobility shapes epidemics, cities, and infrastructure, yet
> prevailing stochastic accounts describe population dispersion more
> convincingly than individual regularity. We therefore ask whether
> individual trajectories are sufficiently structured to reveal
> reproducible behavioral laws."

**Why it works:** starts broad, narrows fast, creates a precise question,
avoids hype.

**Exemplar reference:** `exemplars/ab/AB_2_Understanding_individual_human_mobility_patterns.md`,
`exemplars/ab/AB_3_Limits_of_Predictability_in_Human_Mobility.md`

### Pattern 2: Progress -> Trade-off Framing

**Structure:** field has advanced -> but that advance creates a tension

**Good:**
> "AI tools appear to broaden scientific capability by accelerating
> prediction and publication. Yet those same tools may concentrate
> collective attention on the problems richest in data. We therefore
> separate individual gains from collective narrowing."

**Why it works:** frames a tension rather than a flat result, gives the
paper a reason to exist, sets up later measurement work.

**Exemplar reference:** `exemplars/je/JE_2.md`, `exemplars/je/JE_5.md`

### Pattern 3: Concept Before Explanatory Use

**Structure:** existing concept is insufficient -> define a new
distinction -> use it

**Good:**
> "Citation counts capture visibility but not the character of
> contribution. We therefore distinguish work that redirects later
> attention from work that consolidates existing lines, and
> operationalize that distinction before using it to compare teams."

**Why it works:** defines the conceptual need, introduces a measure only
after motivating it, prevents metric arbitrariness.

**Exemplar reference:** `exemplars/je/JE_1.md`, `exemplars/je/JE_4.md`

### Pattern 4: Minimal Mechanism Compression

**Structure:** phenomenon exists -> description is not explanation ->
find minimal generative set

**Good:**
> "The observed heterogeneity is not, by itself, an explanation. The
> productive question is which minimal set of mechanisms is necessary to
> reproduce the pattern without importing the full complexity of the
> system."

**Why it works:** refuses descriptive overload, compresses toward
mechanism, creates a clean bridge from phenomenon to model.

**Exemplar reference:** `exemplars/ab/AB_1_Emergence_of_Scaling_in_Random_Networks.md`,
`exemplars/ab/AB_5_Quantifying_Long_Term_Scientific_Impact.md`

## Exemplar Selection Rule

When the producer reads exemplars, it should select based on the
detected contribution type:

| Contribution type | Primary exemplars |
|-------------------|-------------------|
| new empirical pattern | AB_2, AB_3, JE_3 |
| new mechanism | AB_1, AB_5, JE_2 |
| new measure | JE_1, JE_4 |
| new method | JE_5, AB_4 |
| new implication | JE_2, JE_5 |

Do not read all exemplars. Read only the 2-3 most relevant.
