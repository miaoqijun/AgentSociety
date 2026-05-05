# Figure Role Taxonomy

Every figure in the manuscript must have a clear argumentative role.
This taxonomy defines the five canonical roles, their placement rules,
what reviewers will check, and common anti-patterns.

## The Five Roles

### 1. Pattern Figure

**Purpose:** Shows the phenomenon — the "what".

**Typical content:** Distribution plot, time series, heat map, scatter
plot revealing a regularity.

**Placement:** Usually the first results subsection. The reader needs to
see the pattern before anything else.

**What reviewers check:**
- Is the pattern clearly visible, or does it require statistical
  interpretation to perceive?
- Is the visualization honest (no truncated axes, no cherry-picked
  windows)?
- Does the figure caption state the pattern precisely?

**Anti-patterns:**
- Showing raw data without any aggregation or structure
- Using a complex visualization when a simple one suffices
- Presenting multiple unrelated patterns in one figure

---

### 2. Mechanism Figure

**Purpose:** Explains why — the generative cause behind the pattern.

**Typical content:** Causal diagram, model comparison, ablation study,
intervention result, decomposition.

**Placement:** Middle results, after the pattern is established. The
reader must already believe the pattern exists before accepting a
mechanism for it.

**What reviewers check:**
- Does the figure actually isolate a mechanism, or does it just show
  another correlation?
- Is there a minimal-mechanism test (removing the proposed cause
  removes the effect)?
- Are alternative explanations addressed?

**Anti-patterns:**
- Showing model outputs without comparison to a baseline
- Claiming mechanism from a single experiment
- Using model architecture diagrams as mechanism evidence

---

### 3. Robustness Figure

**Purpose:** Stabilizes the claim — shows it holds under variation.

**Typical content:** Sensitivity analysis, cross-validation results,
parameter sweep, alternative dataset comparison, statistical tests
across conditions.

**Placement:** Late results, before discussion. The claim must be made
before it is stabilized.

**What reviewers check:**
- Are the robustness tests attacking the claim's weakest points?
- Is the variation range reasonable, or conveniently narrow?
- Does the figure show both where the claim holds AND where it breaks?

**Anti-patterns:**
- Testing only obvious robustness (e.g., sample size) while ignoring
  substantive threats
- Showing robustness only under minor perturbations
- Omitting conditions where the claim fails

---

### 4. Qualification Figure

**Purpose:** Marks the boundary — shows where the claim breaks down.

**Typical content:** Failure cases, boundary conditions, domain limits,
comparison of where the model agrees and disagrees with ground truth.

**Placement:** Discussion or supplement. Boundaries are stated after the
claim is made and stabilized.

**What reviewers check:**
- Is the boundary specific enough to be informative?
- Does the qualification honestly assess scope, or is it hedging?
- Could a reader use this figure to decide whether the finding applies
  to their situation?

**Anti-patterns:**
- Token qualification ("of course, larger studies are needed")
- Showing failures without analyzing what causes them
- Burying important qualifications in supplementary material

---

### 5. Implication Figure

**Purpose:** Extends the meaning — shows what follows from the finding.

**Typical content:** Application to a related domain, prediction for a
future scenario, policy-relevant mapping, extrapolation with confidence
bounds.

**Placement:** Discussion close, after the finding and its boundaries
are established.

**What reviewers check:**
- Is the implication proportional to the finding?
- Is the extrapolation grounded in evidence, or speculative?
- Does the figure add understanding, or just decorate the implication?

**Anti-patterns:**
- Implication figures that are stronger than the evidence figures
- Speculative extrapolation without confidence bounds
- Application demos presented as implications

## Placement Summary

```
Results:
  [Pattern] → [Mechanism] → [Robustness]

Discussion:
  [Qualification] → [Implication]
```

A figure whose placement violates this order needs justification. The
most common violation is putting a mechanism figure before the pattern
figure — the reader cannot accept a mechanism for a phenomenon they
have not yet seen.

## Figure-Argument Anti-Patterns

1. **Decorative figure:** Has no clear argumentative role from the
   taxonomy above. Often a screenshot, architecture diagram, or "system
   overview" that does not advance the argument.
2. **Workflow-ordered figure:** Placed by analysis chronology rather
   than persuasive order. Detectable when figures appear in the order
   experiments were run.
3. **Orphan figure:** Not referenced by any claim in the claim_ledger.
   Exists in the manuscript but carries no argumentative weight.
4. **Overloaded figure:** Tries to serve multiple roles simultaneously.
   A figure that is both pattern and mechanism usually does neither well.
