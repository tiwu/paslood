---
name: Feature Request
about: Propose a new capability or architectural enhancement for Wealth Pilot
title: "feat: "
labels: ["enhancement", "agent:plan"]
assignees: ""
---

### Problem & Motivation
<!-- What problem does this solve? What user need or financial planning workflow does it address? -->

### Proposed Solution & Requirements
<!-- What should the feature do? Include any financial domain specifics (e.g., Belgian tax rules, bucket rebalancing, statement parsing, etc.) -->

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Automated tests cover new behavior with $\ge 90\%$ statement coverage

---

### Autonomous Agent Lifecycle
Wealth Pilot uses a two-stage autonomous agent queue:
1. **Planning Stage (`agent:plan`)**: The agent will inspect this issue, formulate an architecture plan in `docs/plans/`, post it as a comment below, and transition the label to `agent:plan-review`.
2. **Implementation Stage (`agent:approved`)**: After reviewing the plan, apply the label `agent:approved` to authorize the agent to implement code, run tests, and open a linked PR (`agent:review-ready`).
3. **Manual Only**: To keep this issue human-only, remove `agent:plan` or add `agent:manual`.
