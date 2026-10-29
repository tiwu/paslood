# Architecture & Feature Plans

This directory contains version-controlled architectural specifications and implementation plans for **Paslood**.

---

## Two-Stage Issue & Plan Lifecycle

```mermaid
flowchart TD
    A["User Opens Issue<br/>(label: 'agent:plan')"] --> B["Stage 1: Planning<br/>Agent writes docs/plans/PLAN-id-slug.md"]
    B --> C["Plan Review Request<br/>(label: 'agent:plan-review')"]
    C --> D{"Human Review Checkpoint"}
    D -->|"Changes Requested"| B
    D -->|"Approved"| E["Stage 2: Implementation<br/>(label: 'agent:approved' &rarr; 'agent:in-progress')"]
    E --> F["TDD Workflow<br/>Red &rarr; Green &rarr; Refactor (&ge;90% coverage)"]
    F --> G["Open Pull Request<br/>(label: 'agent:review-ready')"]
    G --> H["Human Review & Merge<br/>(PR merged &rarr; Issue closed)"]
```

---

## Naming Standards

Plan files follow the naming convention:
```text
docs/plans/PLAN-<issue_number>-<slug>.md
```

Examples:
- `docs/plans/PLAN-3-option-to-exclude-bucket-from-weight-cal.md`
- `docs/plans/PLAN-30-security-precision-vault.md`

Every non-trivial architectural change must adhere to [`PLAN-TEMPLATE.md`](PLAN-TEMPLATE.md) and specify Clean Architecture layer boundaries, TDD verification strategies, and statutory citations where applicable.
