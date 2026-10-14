---
name: Bug Report
about: Report a bug or defect in Wealth Pilot
title: "fix: "
labels: ["bug", "agent:plan"]
assignees: ""
---

### Bug Description
<!-- Clear and concise description of the bug. -->

### Steps to Reproduce
1. Go to '...'
2. Perform action '...'
3. See error / unexpected behavior

### Expected Behavior
<!-- What should have happened? -->

### Environment Details
- **OS**: macOS / Linux
- **Python Version**: 3.11+
- **Version/Commit**: (e.g. `main` branch commit)

---

### Autonomous Agent Lifecycle
1. **Planning Stage (`agent:plan`)**: The agent will inspect this bug, identify root cause, formulate a reproduction test and fix plan in `docs/plans/`, and update the label to `agent:plan-review`.
2. **Implementation Stage (`agent:approved`)**: After reviewing the fix strategy, apply `agent:approved` to authorize the agent to write tests, fix the issue, and open a PR (`agent:review-ready`).
3. **Manual Only**: To keep this issue human-only, remove `agent:plan` or add `agent:manual`.
