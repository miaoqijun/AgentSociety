# Reviewer Profiles

This reference defines the three reviewer profiles used in skeptical
review rounds and their specific focus areas.

## Profile 1: significance-calibrator

**Focus:** Is the manuscript's significance honestly calibrated?

**Checks:**
- Are significance claims (important, novel, transformative) earned by
  the evidence?
- Is the contribution type honest? (no pattern→mechanism elevation)
- Is the implication proportional to the finding?
- Does the paper overclaim generality?
- Does the paper underclaim where it has genuinely earned strong
  implications?

**Severity rules:**
- Overclaim on central claims → `fatal` or `major`
- Inflation words without justification → `major`
- Timid implication where evidence supports strong claim → `minor`

**Target layer:** `framing` (for overclaim) or `evidence` (for weak
support)

---

## Profile 2: precision-editor

**Focus:** Is the prose precise, controlled, and free of congestion?

**Checks:**
- Word-level: inflated verbs, vague nouns, hedging that hides meaning
- Sentence-level: hidden leaps, non-sequiturs, decorative transitions
- Paragraph-level: multiple competing functions, repeated reversals,
  unclear direction
- Flow: paragraph-to-paragraph transitions that don't move the argument

**Severity rules:**
- Multiple paragraphs with competing functions → `major`
- Hidden logical leaps (result → implication without bridge) → `major`
- Word-level inflation → `minor`
- Transition decoration → `minor`

**Target layer:** `wording` or `paragraph`

---

## Profile 3: evidence-skeptic

**Focus:** Is the manuscript's use of evidence honest and precise?

**Checks:**
- Does the prose accurately represent the evidence strength?
- Are qualifications placed where needed?
- Are caveats missing, delayed, or buried?
- Does the manuscript use strong verbs where evidence is weak?
- Are confidence intervals or uncertainty ranges present where needed?
- Does the prose claim mechanism while evidence shows only pattern?

**Severity rules:**
- Central claim with strong verbs on weak evidence → `fatal`
- Missing qualification on a major claim → `major`
- Buried caveat → `minor`

**Target layer:** `evidence` or `section`

## Dispatch Rules

- Layer 1 reviewers (significance-calibrator, evidence-skeptic) run
  before Layer 2 (precision-editor).
- If Layer 1 finds `fatal` issues, skip Layer 2.
- Layer 2 receives Layer 1 issues as context to avoid re-flagging the
  same problems.
