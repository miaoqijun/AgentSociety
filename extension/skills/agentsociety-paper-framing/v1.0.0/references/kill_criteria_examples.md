# Kill Criteria Examples

Kill criteria are explicit statements of what would falsify or fatally
weaken a paper angle. They serve as the angle's testable boundary.

## Purpose

Every `storyline_map.current_angle` must have non-empty `kill_criteria[]`.
These criteria let downstream reviewers determine whether the angle
survives the evidence or needs to be abandoned.

## Paired Examples

Each example shows a weak angle and the kill criterion that exposes it.

### Example 1: Dataset Description as Contribution

**Weak angle:**
> "We propose X for urban simulation and demonstrate it on a city-scale
> dataset with 10M records."

**Kill criterion:**
> "The angle presents dataset scale and coverage as the contribution,
> but never specifies what understanding about urban systems the
> simulation produces that could not be obtained without it. If the
> dataset is the contribution, this is a data paper, not a research
> paper."

**Generalized rule:** A contribution that reduces to "we built it and it
works on data" is a capability demo, not a research finding.

---

### Example 2: Pattern Asserted as Mechanism

**Weak angle:**
> "Our agents show emergent cooperative behavior in multi-round
> interactions."

**Kill criterion:**
> "The angle claims 'emergence' but only shows that a pattern appears
> under specific parameter settings. If removing the agent's memory
> module also removes the pattern, the mechanism is the memory module,
> not emergence. Without a minimal-mechanism test that isolates the
> generative cause, this is observation, not explanation."

**Generalized rule:** Emergence, complexity, and self-organization are
observation words. They become mechanism claims only when the minimal
generative conditions are identified and tested.

---

### Example 3: Benchmark Deltas as Scientific Finding

**Weak angle:**
> "Our framework outperforms baselines by 15% on metric Y, advancing
> the state of the art."

**Kill criterion:**
> "Performance deltas on benchmarks are engineering results, not
> scientific findings. If the improvement comes from a larger model,
> more data, or better hyperparameter tuning — rather than from a
> previously unknown principle — the paper's contribution is incremental
> method improvement, not understanding."

**Generalized rule:** Benchmark improvements are contributions only when
they reveal something about why the improvement occurs, not just that it
occurs.

---

### Example 4: Capability Demo as Theoretical Insight

**Weak angle:**
> "The LLM-based agent paradigm enables Y application, demonstrating
> the potential of AI for Z domain."

**Kill criterion:**
> "Demonstrating that an LLM can perform a task is a capability demo.
> If the paper does not identify what the LLM's success reveals about
> the task's structure, the domain's properties, or the model's
> limitations, the contribution is engineering, not insight."

**Generalized rule:** "We showed it can be done" is a demo. "We showed
why it works and where it breaks" is a finding.

---

### Example 5: Implication Stronger Than Finding

**Weak angle:**
> "Our results suggest transformative implications for policy and
> urban planning."

**Kill criterion:**
> "The implication is stated at a generality level far beyond what the
> evidence supports. If the experiment covers one city, one time period,
> and one agent configuration, 'transformative implications for policy'
> is speculation. The honest implication is what the specific finding
> changes about the specific question."

**Generalized rule:** Implications must be proportional to evidence. A
local finding earns a local implication; scaling to global claims
requires global evidence.
