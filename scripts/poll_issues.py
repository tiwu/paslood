#!/usr/bin/env python3
"""Autonomous Issue Poller & Lifecycle Manager for Paslood.

Provides queue inspection and git/GitHub lifecycle helper commands for
the autonomous Antigravity worker and local developers:

  Inspection:
    - --status: Display current status of all queue labels.
    - --next [--json]: Fetch next actionable issue (agent:approved > agent:plan).

  Planning Stage:
    - --publish-plan <id>: Validates agent-authored docs/plans/PLAN-<id>-<slug>.md,
      commits to feature/issue-<id>-<slug>, pushes to remote, comments on the issue,
      and transitions label to 'agent:plan-review'.

  Implementation Stage:
    - --start-work <id>: Checks out feature branch, comments on the issue,
      and transitions label to 'agent:in-progress'.
    - --submit-pr <id>: Pushes branch, creates GitHub Pull Request linking
      the issue and plan, and transitions label to 'agent:review-ready'.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
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
    def __init__(self, repo: str = "tiwu/paslood", dry_run: bool = False) -> None:
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

    def get_next_actionable_issue(self) -> tuple[str, GitHubIssue] | tuple[None, None]:
        """Find the next highest-priority issue in the queue.

        Priority:
          1. 'agent:approved' (ready for implementation)
          2. 'agent:plan' (ready for architecture design)
        """
        approved = self.get_issues_by_label("agent:approved")
        if approved:
            return "implementation", approved[0]

        planning = self.get_issues_by_label("agent:plan")
        if planning:
            return "planning", planning[0]

        return None, None

    def ensure_git_identity(self) -> None:
        """Ensure git user name and email are configured."""
        user_res = subprocess.run(
            ["git", "config", "user.name"],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
        )
        if not user_res.stdout.strip():
            subprocess.run(
                ["git", "config", "user.name", "Paslood Agent"],
                cwd=self.repo_root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "agent@paslood.local"],
                cwd=self.repo_root,
                check=True,
            )

    def publish_plan(self, issue_number: int) -> Path:
        """Validate agent-drafted architecture plan, push branch, comment on issue, and mark agent:plan-review."""
        issue = self.get_issue(issue_number)
        if not issue:
            raise ValueError(f"Issue #{issue_number} not found in repo {self.repo}")

        plan_filename = f"PLAN-{issue.number}-{issue.slug}.md"
        branch_name = f"feature/issue-{issue.number}-{issue.slug}"
        plan_path = self.repo_root / "docs" / "plans" / plan_filename

        if not plan_path.exists():
            raise FileNotFoundError(
                f"Architecture plan '{plan_path.relative_to(self.repo_root)}' does not exist.\n"
                f"The Antigravity agent must draft the architecture plan file before calling --publish-plan."
            )

        content = plan_path.read_text(encoding="utf-8")
        if not content.strip():
            raise ValueError(f"Architecture plan '{plan_path.name}' is empty.")

        if not self.dry_run:
            self.ensure_git_identity()
            # Checkout feature branch
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
        else:
            print(f"[DRY-RUN] Would commit and push {plan_path} to branch {branch_name}")

        plan_remote_url = (
            f"https://github.com/{self.repo}/blob/{branch_name}/docs/plans/{plan_filename}"
        )
        comment = (
            f"### 📋 Architecture Plan Ready for Review\n\n"
            f"An architecture plan has been drafted and published to "
            f"[`docs/plans/{plan_filename}`]({plan_remote_url}).\n\n"
            f"<details><summary>Click to preview full architecture plan</summary>\n\n"
            f"{content}\n\n"
            f"</details>\n\n"
            f"---\n"
            f"**Next Steps**:\n"
            f"1. Review the proposed architecture plan above.\n"
            f"2. To request modifications, comment your feedback below.\n"
            f"3. When ready for implementation, apply the label **`agent:approved`**."
        )
        self.comment_on_issue(issue.number, comment)
        self.update_issue_labels(
            issue.number,
            add_labels=["agent:plan-review"],
            remove_labels=["agent:plan"],
        )
        print(f"✓ Issue #{issue.number} transitioned to 'agent:plan-review'")
        return plan_path

    def start_work(self, issue_number: int) -> str:
        """Stage 2: Transition to agent:in-progress, prepare branch, and comment on issue."""
        issue = self.get_issue(issue_number)
        if not issue:
            raise ValueError(f"Issue #{issue_number} not found in repo {self.repo}")

        branch_name = f"feature/issue-{issue.number}-{issue.slug}"
        print(f"✓ Issue #{issue.number} is approved! Preparing `{branch_name}`...")

        if not self.dry_run:
            self.ensure_git_identity()
            # Try checking out existing branch or create from main
            res = subprocess.run(
                ["git", "checkout", branch_name],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
            )
            if res.returncode != 0:
                subprocess.run(
                    ["git", "checkout", "-B", branch_name],
                    cwd=self.repo_root,
                    check=True,
                    capture_output=True,
                )

        self.update_issue_labels(
            issue.number,
            add_labels=["agent:in-progress"],
            remove_labels=["agent:approved"],
        )
        comment = (
            f"🚀 **Implementation Started**\n\n"
            f"The architecture plan was approved. Implementation is underway on branch `{branch_name}`.\n"
            f"The agent will follow TDD (tests first), verify 90%+ coverage, and submit a Pull Request."
        )
        self.comment_on_issue(issue.number, comment)
        print(f"✓ Issue #{issue.number} transitioned to 'agent:in-progress'")
        return branch_name

    def submit_pr(self, issue_number: int) -> str:
        """Stage 3: Push branch, create GitHub Pull Request, comment, and transition to agent:review-ready."""
        issue = self.get_issue(issue_number)
        if not issue:
            raise ValueError(f"Issue #{issue_number} not found in repo {self.repo}")

        branch_name = f"feature/issue-{issue.number}-{issue.slug}"
        plan_filename = f"PLAN-{issue.number}-{issue.slug}.md"

        if not self.dry_run:
            self.ensure_git_identity()
            subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                cwd=self.repo_root,
                check=True,
                capture_output=True,
            )

            pr_body = (
                f"Closes #{issue.number}\n\n"
                f"### Architecture Plan\n"
                f"- [`docs/plans/{plan_filename}`](docs/plans/{plan_filename})\n\n"
                f"### Automated Verification\n"
                f"- Test suite passes with $\\ge 90\\%$ coverage\n"
                f"- Zero linting errors (`uv run ruff check`)\n"
                f"- Documentation builds cleanly (`uv run mkdocs build`)\n"
            )

            pr_title = f"feat: [Issue #{issue.number}] {issue.title}"
            pr_out = self.run_gh(
                [
                    "pr",
                    "create",
                    "--repo",
                    self.repo,
                    "--head",
                    branch_name,
                    "--base",
                    "main",
                    "--title",
                    pr_title,
                    "--body",
                    pr_body,
                ]
            )
            pr_url = pr_out.strip()
            print(f"✓ Created Pull Request: {pr_url}")
        else:
            pr_url = f"https://github.com/{self.repo}/pull/mock"
            print(f"[DRY-RUN] Would create PR on branch {branch_name}")

        self.update_issue_labels(
            issue.number,
            add_labels=["agent:review-ready"],
            remove_labels=["agent:in-progress"],
        )
        comment = (
            f"✅ **Pull Request Created for Review**\n\n"
            f"Implementation complete. Pull Request: {pr_url}\n"
            f"Target: `main` | Branch: `{branch_name}`"
        )
        self.comment_on_issue(issue.number, comment)
        print(f"✓ Issue #{issue.number} transitioned to 'agent:review-ready'")
        return pr_url

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
        print(f"\n=== Paslood Autonomous Issue Queue ({self.repo}) ===")
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
                self.start_work(iss.number)
            elif "agent:plan" in iss.labels:
                self.publish_plan(iss.number)
            else:
                print(
                    f"Issue #{target_issue} does not have 'agent:plan' or 'agent:approved' label."
                )
            return

        stage, iss = self.get_next_actionable_issue()
        if stage == "implementation" and iss:
            print(f"Found approved issue #{iss.number}: '{iss.title}'")
            self.start_work(iss.number)
            return

        if stage == "planning" and iss:
            print(f"Found issue #{iss.number} ready for planning: '{iss.title}'")
            plan_path = self.repo_root / "docs" / "plans" / f"PLAN-{iss.number}-{iss.slug}.md"
            if plan_path.exists():
                self.publish_plan(iss.number)
            else:
                print(
                    f"Issue #{iss.number} needs an architecture plan drafted at docs/plans/{plan_path.name} "
                    f"by the Antigravity agent before publishing."
                )
            return

        print("No issues currently queued with 'agent:approved' or 'agent:plan'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Paslood Autonomous Issue Poller & Queue Helper")
    parser.add_argument("--repo", default="tiwu/paslood", help="GitHub repo (owner/name)")
    parser.add_argument("--status", action="store_true", help="Display queue status")
    parser.add_argument("--next", action="store_true", help="Fetch next actionable issue")
    parser.add_argument(
        "--json", action="store_true", help="Output in JSON format (used with --next)"
    )
    parser.add_argument(
        "--publish-plan", type=int, metavar="ISSUE_NUM", help="Publish drafted plan for issue"
    )
    parser.add_argument(
        "--start-work",
        type=int,
        metavar="ISSUE_NUM",
        help="Start implementation for approved issue",
    )
    parser.add_argument(
        "--submit-pr", type=int, metavar="ISSUE_NUM", help="Submit pull request for completed issue"
    )
    parser.add_argument(
        "--checkout", type=int, metavar="ISSUE_NUM", help="Checkout feature branch for issue"
    )
    parser.add_argument("--issue", type=int, help="Target specific issue number for cycle")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions without changes")

    args = parser.parse_args()
    poller = IssuePoller(repo=args.repo, dry_run=args.dry_run)

    if args.status:
        poller.display_queue_status()
    elif args.next:
        stage, issue = poller.get_next_actionable_issue()
        if args.json:
            result = {
                "stage": stage,
                "issue": {
                    "number": issue.number,
                    "title": issue.title,
                    "body": issue.body,
                    "slug": issue.slug,
                    "url": issue.url,
                    "labels": issue.labels,
                }
                if issue
                else None,
            }
            print(json.dumps(result, indent=2))
        else:
            if stage and issue:
                print(f"Next task: [{stage.upper()}] Issue #{issue.number} - {issue.title}")
                print(f"URL: {issue.url}")
            else:
                print("Queue is clear. No actionable issues found.")
    elif args.publish_plan:
        poller.publish_plan(args.publish_plan)
    elif args.start_work:
        poller.start_work(args.start_work)
    elif args.submit_pr:
        poller.submit_pr(args.submit_pr)
    elif args.checkout:
        poller.checkout_issue(args.checkout)
    else:
        poller.run_cycle(target_issue=args.issue)


if __name__ == "__main__":
    main()
