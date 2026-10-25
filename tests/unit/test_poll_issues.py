"""Unit tests for the autonomous issue poller script."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from poll_issues import GitHubIssue, IssuePoller


def test_github_issue_slug_generation():
    # 1. Clean feature prefix
    issue1 = GitHubIssue(
        number=42,
        title="feat: Add CSV balance sheet export",
        body="Export user balance sheet as CSV",
        labels=["agent:plan"],
        url="https://github.com/tiwu/wealth-pilot/issues/42",
    )
    assert issue1.slug == "add-csv-balance-sheet-export"

    # 2. Bug fix prefix with special characters
    issue2 = GitHubIssue(
        number=10,
        title="fix: Rebalancing 0.00% zero-value trap!",
        body="Zero values are truthy",
        labels=["agent:approved"],
        url="https://github.com/tiwu/wealth-pilot/issues/10",
    )
    assert issue2.slug == "rebalancing-000-zero-value-trap"

    # 3. Empty or symbols only fallback
    issue3 = GitHubIssue(
        number=5,
        title="???",
        body="",
        labels=[],
        url="https://github.com/tiwu/wealth-pilot/issues/5",
    )
    assert issue3.slug == "feature"


def test_draft_plan_content_structure():
    poller = IssuePoller(repo="tiwu/wealth-pilot", dry_run=True)
    issue = GitHubIssue(
        number=7,
        title="feat: Integrate Bunq bank CSV",
        body="Parse Bunq multi-currency statements",
        labels=["agent:plan"],
        url="https://github.com/tiwu/wealth-pilot/issues/7",
    )
    content = poller.draft_plan_content(issue)
    assert "# Architecture Plan: [Issue #7] feat: Integrate Bunq bank CSV" in content
    assert "https://github.com/tiwu/wealth-pilot/issues/7" in content
    assert "feature/issue-7-integrate-bunq-bank-csv" in content
    assert "Parse Bunq multi-currency statements" in content
    assert "Hexagonal Architecture Impact" in content
    assert "Test-Driven Development (TDD) Plan" in content


def test_process_planning_stage(tmp_path):
    poller = IssuePoller(repo="tiwu/wealth-pilot", dry_run=False)
    poller.repo_root = tmp_path
    poller.comment_on_issue = MagicMock()
    poller.update_issue_labels = MagicMock()

    issue = GitHubIssue(
        number=15,
        title="feat: Automated tax loss harvesting",
        body="Simulate tax loss offsets",
        labels=["agent:plan"],
        url="https://github.com/tiwu/wealth-pilot/issues/15",
    )

    plan_path = poller.process_planning_stage(issue)

    # Verify plan file created in docs/plans/
    assert plan_path.exists()
    assert plan_path.name == "PLAN-15-automated-tax-loss-harvesting.md"
    assert "Automated tax loss harvesting" in plan_path.read_text(encoding="utf-8")

    # Verify label update called: remove agent:plan, add agent:plan-review
    poller.update_issue_labels.assert_called_once_with(
        15, add_labels=["agent:plan-review"], remove_labels=["agent:plan"]
    )

    # Verify comment called
    poller.comment_on_issue.assert_called_once()
    comment_arg = poller.comment_on_issue.call_args[0][1]
    assert "Architecture Plan Ready for Review" in comment_arg
    assert "agent:approved" in comment_arg


def test_process_approved_stage():
    poller = IssuePoller(repo="tiwu/wealth-pilot", dry_run=False)
    poller.comment_on_issue = MagicMock()
    poller.update_issue_labels = MagicMock()

    issue = GitHubIssue(
        number=15,
        title="feat: Automated tax loss harvesting",
        body="Simulate tax loss offsets",
        labels=["agent:approved"],
        url="https://github.com/tiwu/wealth-pilot/issues/15",
    )

    branch_name = poller.process_approved_stage(issue)
    assert branch_name == "feature/issue-15-automated-tax-loss-harvesting"

    poller.update_issue_labels.assert_called_once_with(
        15, add_labels=["agent:in-progress"], remove_labels=["agent:approved"]
    )
    poller.comment_on_issue.assert_called_once()
    comment_arg = poller.comment_on_issue.call_args[0][1]
    assert "Implementation Started" in comment_arg


def test_issue_poller_fetch_and_status():
    poller = IssuePoller(repo="tiwu/wealth-pilot", dry_run=False)

    fake_issues = [
        {
            "number": 1,
            "title": "feat: Goal A",
            "body": "Body A",
            "labels": [{"name": "agent:plan"}],
            "url": "url1",
        },
        {
            "number": 2,
            "title": "fix: Bug B",
            "body": "Body B",
            "labels": [{"name": "agent:plan"}],
            "url": "url2",
        },
    ]

    with patch.object(poller, "run_gh", return_value=json.dumps(fake_issues)):
        issues = poller.get_issues_by_label("agent:plan")
        assert len(issues) == 2
        assert issues[0].number == 1
        assert issues[0].slug == "goal-a"

    with patch.object(poller, "run_gh", return_value=json.dumps(fake_issues[0])):
        issue = poller.get_issue(1)
        assert issue is not None
        assert issue.number == 1
        assert issue.title == "feat: Goal A"

    with patch.object(poller, "run_gh", side_effect=RuntimeError("API rate limit")):
        empty = poller.get_issues_by_label("agent:plan")
        assert empty == []


def test_run_cycle_prioritizes_approved_over_planning():
    poller = IssuePoller(repo="tiwu/wealth-pilot", dry_run=False)

    approved_issue = GitHubIssue(
        number=20, title="feat: Ready to build", body="", labels=["agent:approved"], url=""
    )
    planning_issue = GitHubIssue(
        number=21, title="feat: Needs plan", body="", labels=["agent:plan"], url=""
    )

    poller.process_approved_stage = MagicMock()
    poller.process_planning_stage = MagicMock()

    # When both exist, approved should be processed first
    def mock_get(label):
        if label == "agent:approved":
            return [approved_issue]
        if label == "agent:plan":
            return [planning_issue]
        return []

    poller.get_issues_by_label = MagicMock(side_effect=mock_get)

    poller.run_cycle()
    poller.process_approved_stage.assert_called_once_with(approved_issue)
    poller.process_planning_stage.assert_not_called()


def test_checkout_issue():
    poller = IssuePoller(repo="tiwu/wealth-pilot", dry_run=False)
    issue = GitHubIssue(number=15, title="feat: cool-feature", body="", labels=[], url="")
    poller.get_issue = MagicMock(return_value=issue)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        poller.checkout_issue(15)
        mock_run.assert_called_with(
            ["git", "checkout", "feature/issue-15-cool-feature"],
            capture_output=True,
            text=True,
            check=False,
        )
