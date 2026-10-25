#!/usr/bin/env python3
"""Autonomous Issue Poller & Lifecycle Manager for Wealth Pilot.

Handles the 2-stage issue queue:
  Stage 1 (Planning):
    - Polls issues labeled 'agent:plan'
    - Formulates an architecture plan in docs/plans/PLAN-<id>-<slug>.md
    - Posts plan comment to the issue
    - Transitions label to 'agent:plan-review'

  Stage 2 (Implementation):
    - Polls issues labeled 'agent:approved'
    - Transitions label to 'agent:in-progress'
    - Creates git branch feature/issue-<id>-<slug>
    - Prepares the workspace for TDD execution
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class GitHubIssue:
    number: int
    title: str
    body: str
    labels: list[str]
    url: str

    @property
    def slug(self) -> str:
        clean = re.sub(r"[^\w\s-]", "", self.title.lower())
        clean = re.sub(r"[\s_]+", "-", clean).strip("-")
        clean = re.sub(r"^(feat|fix|chore|docs|refactor)-+", "", clean)
        return clean[:40] or "feature"


class IssuePoller:
    def __init__(self, repo: str = "tiwu/wealth-pilot", dry_run: bool = False) -> None:
        self.repo = repo
        self.dry_run = dry_run
        self.repo_root = Path(__file__).resolve().parent.parent

    def run_gh(self, args: list[str]) -> str:
        """Execute a GitHub CLI command and return stdout."""
        cmd = ["gh", *args]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            err = result.stderr.strip() or f"Command failed with returncode {result.returncode}"
            raise RuntimeError(f"gh error: {err}")
        return result.stdout.strip()

    def get_issues_by_label(self, label: str) -> list[GitHubIssue]:
        """Fetch open issues with a specific label."""
        try:
            output = self.run_gh(
                [
                    "issue",
                    "list",
                    "--repo",
                    self.repo,
                    "--state",
                    "open",
                    "--label",
                    label,
                    "--json",
                    "number,title,body,labels,url",
                ]
            )
            if not output:
                return []
            data = json.loads(output)
            return [
                GitHubIssue(
                    number=item["number"],
                    title=item.get("title", ""),
                    body=item.get("body", ""),
                    labels=[lbl["name"] for lbl in item.get("labels", [])],
                    url=item.get("url", ""),
                )
                for item in data
            ]
        except Exception as e:
            print(f"Warning: Failed to fetch issues for label '{label}': {e}", file=sys.stderr)
            return []

    def get_issue(self, issue_number: int) -> GitHubIssue | None:
        """Fetch a specific issue by number."""
        try:
            output = self.run_gh(
                [
                    "issue",
                    "view",
                    str(issue_number),
                    "--repo",
                    self.repo,
                    "--json",
                    "number,title,body,labels,url",
                ]
            )
            data = json.loads(output)
            return GitHubIssue(
                number=data["number"],
                title=data.get("title", ""),
                body=data.get("body", ""),
                labels=[lbl["name"] for lbl in data.get("labels", [])],
                url=data.get("url", ""),
            )
        except Exception:
            return None

    def update_issue_labels(
        self, issue_number: int, add_labels: list[str], remove_labels: list[str]
    ) -> None:
        """Add and remove labels from an issue."""
        if self.dry_run:
            print(
                f"[DRY-RUN] Update issue #{issue_number}: add={add_labels}, remove={remove_labels}"
            )
            return
        args = ["issue", "edit", str(issue_number), "--repo", self.repo]
        for lbl in add_labels:
            args.extend(["--add-label", lbl])
        for lbl in remove_labels:
            args.extend(["--remove-label", lbl])
        self.run_gh(args)

    def comment_on_issue(self, issue_number: int, comment: str) -> None:
        """Post a comment on an issue."""
        if self.dry_run:
            print(f"[DRY-RUN] Comment on issue #{issue_number}:\n{comment}\n")
            return
        self.run_gh(["issue", "comment", str(issue_number), "--repo", self.repo, "--body", comment])

    def draft_plan_content(self, issue: GitHubIssue) -> str:
        """Generate structured plan markdown content for an issue."""
        today = datetime.now().strftime("%Y-%m-%d")
        branch_name = f"feature/issue-{issue.number}-{issue.slug}"

        return f"""# Architecture Plan: [Issue #{issue.number}] {issue.title}

- **Issue**: [#{issue.number}]({issue.url})
- **Status**: Plan Review
- **Author**: Autonomous Issue Worker
- **Date**: {today}
- **Target Branch**: `{branch_name}`

---

## 1. Problem Statement & Motivation
{issue.body or "No description provided in issue."}

---

## 2. Requirements & Acceptance Criteria
- [ ] Address core requirements stated in Issue #{issue.number}
- [ ] Maintain Clean Architecture boundaries (Domain pure, Use Cases isolated, Adapters modular)
- [ ] Implement unit and integration tests with $\\ge 90\\%$ test coverage
- [ ] Verify zero linting errors (`uv run ruff check`) and documentation build (`uv run mkdocs build`)

---

## 3. Hexagonal Architecture Impact

### 3.1 Domain Layer (`src/wealth_pilot/domain/`)
- Ensure all financial math uses `Money` / `Decimal` (no floats)
- Avoid zero-value truthiness trap (`value or fallback`)

### 3.2 Use Cases Layer (`src/wealth_pilot/use_cases/`)
- Application orchestrators receive domain entities and return typed outputs

### 3.3 Adapters & Repositories (`src/wealth_pilot/adapters/`)
- Persistence via `LocalDbRepository` (SQLite) or `ConfigRepository` (YAML)

### 3.4 Delivery Frameworks (`src/wealth_pilot/delivery/`)
- REST APIs in `src/wealth_pilot/delivery/web/app.py`
- Web UI in `src/wealth_pilot/delivery/web/templates/index.html`

---

## 4. Test-Driven Development (TDD) Plan
1. **Red**: Write test cases in `tests/` reproducing requirements and verifying failure.
2. **Green**: Write minimal implementation satisfying the tests.
3. **Refactor**: Clean up and verify full test suite passes with $\\ge 90\\%$ coverage.

---

## 5. Verification Checklist
- [ ] `uv run ruff check src tests`
- [ ] `uv run ruff format --check src tests`
- [ ] `uv run mkdocs build --strict`
- [ ] `uv run pytest -v --cov=src/wealth_pilot --cov-fail-under=90`
- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] PR created with `Closes #{issue.number}`
"""

    def process_planning_stage(self, issue: GitHubIssue) -> Path:
        """Stage 1: Generate plan file, commit & push to remote branch, comment on issue, and mark agent:plan-review."""
        plan_filename = f"PLAN-{issue.number}-{issue.slug}.md"
        branch_name = f"feature/issue-{issue.number}-{issue.slug}"
        plans_dir = self.repo_root / "docs" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan_path = plans_dir / plan_filename

        content = self.draft_plan_content(issue)
        if not self.dry_run:
            plan_path.write_text(content, encoding="utf-8")
            print(f"✓ Created architecture plan: {plan_path.relative_to(self.repo_root)}")

            # Commit and push plan to remote branch so it is accessible on GitHub remotely
            try:
                # Ensure user identity is set
                user_res = subprocess.run(
                    ["git", "config", "user.name"],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                )
                if not user_res.stdout.strip():
                    subprocess.run(
                        ["git", "config", "user.name", "github-actions[bot]"],
                        cwd=self.repo_root,
                        check=True,
                    )
                    subprocess.run(
                        [
                            "git",
                            "config",
                            "user.email",
                            "github-actions[bot]@users.noreply.github.com",
                        ],
                        cwd=self.repo_root,
                        check=True,
                    )

                subprocess.run(
                    ["git", "checkout", "-B", branch_name],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                )
                subprocess.run(
                    ["git", "add", str(plan_path.relative_to(self.repo_root))],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                )
                status_res = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                )
                if status_res.stdout.strip():
                    subprocess.run(
                        [
                            "git",
                            "commit",
                            "-m",
                            f"docs: add architecture plan for issue #{issue.number}",
                        ],
                        cwd=self.repo_root,
                        check=True,
                        capture_output=True,
                    )
                subprocess.run(
                    ["git", "push", "-u", "origin", branch_name],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                )
                print(f"✓ Committed and pushed plan to remote branch '{branch_name}'")
            except Exception as e:
                print(f"Warning: Failed to git push plan to remote: {e}", file=sys.stderr)
        else:
            print(f"[DRY-RUN] Would create architecture plan: {plan_path}")

        # Post plan comment on issue with direct link to the remote branch
        plan_remote_url = (
            f"https://github.com/{self.repo}/blob/{branch_name}/docs/plans/{plan_filename}"
        )
        comment = (
            f"### 📋 Architecture Plan Ready for Review\n\n"
            f"An initial architecture plan has been drafted and published to "
            f"[`docs/plans/{plan_filename}`]({plan_remote_url}).\n\n"
            f"<details><summary>Click to preview full architecture plan</summary>\n\n"
            f"{content}\n\n"
            f"</details>\n\n"
            f"---\n"
            f"**Next Steps**:\n"
            f"1. Review the proposed plan above.\n"
            f"2. To request modifications, comment your feedback below.\n"
            f"3. When you are ready for implementation to begin, apply the label **`agent:approved`**."
        )
        self.comment_on_issue(issue.number, comment)
        self.update_issue_labels(
            issue.number,
            add_labels=["agent:plan-review"],
            remove_labels=["agent:plan"],
        )
        print(f"✓ Issue #{issue.number} transitioned to 'agent:plan-review'")
        return plan_path

    def process_approved_stage(self, issue: GitHubIssue) -> str:
        """Stage 2: Transition to agent:in-progress and prepare branch."""
        branch_name = f"feature/issue-{issue.number}-{issue.slug}"
        print(f"✓ Issue #{issue.number} is approved! Ready for implementation on `{branch_name}`.")

        self.update_issue_labels(
            issue.number,
            add_labels=["agent:in-progress"],
            remove_labels=["agent:approved"],
        )
        comment = (
            f"🚀 **Implementation Started**\n\n"
            f"The architecture plan was approved. Implementation is beginning on branch `{branch_name}`.\n"
            f"The agent will follow TDD (tests first), verify 90%+ coverage, and submit a Pull Request."
        )
        self.comment_on_issue(issue.number, comment)
        print(f"✓ Issue #{issue.number} transitioned to 'agent:in-progress'")
        return branch_name

    def display_queue_status(self) -> None:
        """Display an overview of the current queue state."""
        labels = [
            "agent:plan",
            "agent:plan-review",
            "agent:approved",
            "agent:in-progress",
            "agent:review-ready",
            "agent:blocked",
        ]
        print(f"\n=== Wealth Pilot Autonomous Issue Queue ({self.repo}) ===")
        for lbl in labels:
            issues = self.get_issues_by_label(lbl)
            print(f"  {lbl:<20}: {len(issues)} issue(s)")
            for iss in issues:
                print(f"    - #{iss.number}: {iss.title}")
        print("=====================================================\n")

    def checkout_issue(self, issue_number: int) -> None:
        """Finds and checks out the feature branch associated with an issue."""
        iss = self.get_issue(issue_number)
        if not iss:
            print(f"Issue #{issue_number} not found.", file=sys.stderr)
            return
        branch_name = f"feature/issue-{iss.number}-{iss.slug}"
        print(f"Checking out branch '{branch_name}' for issue #{iss.number}...")
        res = subprocess.run(
            ["git", "checkout", branch_name], capture_output=True, text=True, check=False
        )
        if res.returncode != 0:
            # Try fetching from origin
            subprocess.run(
                ["git", "fetch", "origin", branch_name], capture_output=True, text=True, check=False
            )
            res2 = subprocess.run(
                ["git", "checkout", branch_name], capture_output=True, text=True, check=False
            )
            if res2.returncode != 0:
                print(
                    f"Could not checkout branch '{branch_name}': {res2.stderr.strip()}",
                    file=sys.stderr,
                )
                return
        print(f"Switched to branch '{branch_name}' successfully.")

    def run_cycle(self, target_issue: int | None = None) -> None:
        """Execute one complete polling cycle."""
        if target_issue:
            iss = self.get_issue(target_issue)
            if not iss:
                print(f"Issue #{target_issue} not found.", file=sys.stderr)
                return
            if "agent:approved" in iss.labels:
                self.process_approved_stage(iss)
            elif "agent:plan" in iss.labels:
                self.process_planning_stage(iss)
            else:
                print(
                    f"Issue #{target_issue} does not have 'agent:plan' or 'agent:approved' label."
                )
            return

        # 1. Check for approved issues ready for implementation
        approved = self.get_issues_by_label("agent:approved")
        if approved:
            target = approved[0]
            print(f"Found approved issue #{target.number}: '{target.title}'")
            self.process_approved_stage(target)
            return

        # 2. Check for new issues needing architecture plans
        planning = self.get_issues_by_label("agent:plan")
        if planning:
            target = planning[0]
            print(f"Found issue #{target.number} ready for planning: '{target.title}'")
            self.process_planning_stage(target)
            return

        print("No issues currently queued with 'agent:approved' or 'agent:plan'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Wealth Pilot Autonomous Issue Poller")
    parser.add_argument("--repo", default="tiwu/wealth-pilot", help="GitHub repo (owner/name)")
    parser.add_argument("--status", action="store_true", help="Display queue status")
    parser.add_argument("--issue", type=int, help="Target specific issue number")
    parser.add_argument("--checkout", type=int, help="Checkout feature branch for specific issue")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without changes")

    args = parser.parse_args()
    poller = IssuePoller(repo=args.repo, dry_run=args.dry_run)

    if args.status:
        poller.display_queue_status()
    elif args.checkout:
        poller.checkout_issue(args.checkout)
    else:
        poller.run_cycle(target_issue=args.issue)


if __name__ == "__main__":
    main()
