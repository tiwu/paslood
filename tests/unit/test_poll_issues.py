"""Unit tests for the autonomous issue poller script."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from poll_issues import GitHubIssue, IssuePoller


def test_github_issue_slug_generation():
    # 1. Clean feature prefix
    issue1 = GitHubIssue(
        number=42,
        title="feat: Add CSV balance sheet export",
        body="Export user balance sheet as CSV",
        labels=["agent:plan"],
        url="https://github.com/tiwu/paslood/issues/42",
    )
    assert issue1.slug == "add-csv-balance-sheet-export"

    # 2. Bug fix prefix with special characters
    issue2 = GitHubIssue(
        number=10,
        title="fix: Rebalancing 0.00% zero-value trap!",
        body="Zero values are truthy",
        labels=["agent:approved"],
        url="https://github.com/tiwu/paslood/issues/10",
    )
    assert issue2.slug == "rebalancing-000-zero-value-trap"

    # 3. Empty or symbols only fallback
    issue3 = GitHubIssue(
        number=5,
        title="???",
        body="",
        labels=[],
        url="https://github.com/tiwu/paslood/issues/5",
    )
    assert issue3.slug == "feature"


def test_get_next_actionable_issue():
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)

    approved_issue = GitHubIssue(
        number=20, title="feat: Build it", body="", labels=["agent:approved"], url=""
    )
    planning_issue = GitHubIssue(
        number=21, title="feat: Plan it", body="", labels=["agent:plan"], url=""
    )

    # 1. Both present: approved takes priority
    poller.get_issues_by_label = MagicMock(
        side_effect=lambda lbl: [approved_issue] if lbl == "agent:approved" else [planning_issue]
    )
    stage, issue = poller.get_next_actionable_issue()
    assert stage == "implementation"
    assert issue == approved_issue

    # 2. Only planning present
    poller.get_issues_by_label = MagicMock(
        side_effect=lambda lbl: [] if lbl == "agent:approved" else [planning_issue]
    )
    stage, issue = poller.get_next_actionable_issue()
    assert stage == "planning"
    assert issue == planning_issue

    # 3. Neither present
    poller.get_issues_by_label = MagicMock(return_value=[])
    stage, issue = poller.get_next_actionable_issue()
    assert stage is None
    assert issue is None


def test_publish_plan_success(tmp_path: Path):
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)
    poller.repo_root = tmp_path
    poller.comment_on_issue = MagicMock()
    poller.update_issue_labels = MagicMock()

    issue = GitHubIssue(
        number=15,
        title="feat: Automated tax loss harvesting",
        body="Simulate tax loss offsets",
        labels=["agent:plan"],
        url="https://github.com/tiwu/paslood/issues/15",
    )
    poller.get_issue = MagicMock(return_value=issue)

    # Create dummy authored plan file
    plans_dir = tmp_path / "docs" / "plans"
    plans_dir.mkdir(parents=True)
    plan_file = plans_dir / "PLAN-15-automated-tax-loss-harvesting.md"
    plan_file.write_text("# Plan content authored by LLM", encoding="utf-8")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        res_path = poller.publish_plan(15)

    assert res_path == plan_file
    poller.update_issue_labels.assert_called_once_with(
        15, add_labels=["agent:plan-review"], remove_labels=["agent:plan"]
    )
    poller.comment_on_issue.assert_called_once()
    comment = poller.comment_on_issue.call_args[0][1]
    assert "Architecture Plan Ready for Review" in comment
    assert "PLAN-15-automated-tax-loss-harvesting.md" in comment


def test_publish_plan_missing_file(tmp_path: Path):
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)
    poller.repo_root = tmp_path
    issue = GitHubIssue(
        number=15,
        title="feat: Missing plan",
        body="",
        labels=["agent:plan"],
        url="",
    )
    poller.get_issue = MagicMock(return_value=issue)

    with pytest.raises(FileNotFoundError, match="does not exist"):
        poller.publish_plan(15)


def test_publish_plan_empty_file(tmp_path: Path):
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)
    poller.repo_root = tmp_path
    issue = GitHubIssue(
        number=15,
        title="feat: Empty plan",
        body="",
        labels=["agent:plan"],
        url="",
    )
    poller.get_issue = MagicMock(return_value=issue)

    plans_dir = tmp_path / "docs" / "plans"
    plans_dir.mkdir(parents=True)
    plan_file = plans_dir / "PLAN-15-empty-plan.md"
    plan_file.write_text("   \n", encoding="utf-8")

    with pytest.raises(ValueError, match="is empty"):
        poller.publish_plan(15)


def test_start_work():
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)
    poller.comment_on_issue = MagicMock()
    poller.update_issue_labels = MagicMock()

    issue = GitHubIssue(
        number=15,
        title="feat: Automated tax loss harvesting",
        body="Simulate tax loss offsets",
        labels=["agent:approved"],
        url="https://github.com/tiwu/paslood/issues/15",
    )
    poller.get_issue = MagicMock(return_value=issue)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        branch_name = poller.start_work(15)

    assert branch_name == "feature/issue-15-automated-tax-loss-harvesting"
    poller.update_issue_labels.assert_called_once_with(
        15, add_labels=["agent:in-progress"], remove_labels=["agent:approved"]
    )
    poller.comment_on_issue.assert_called_once()
    assert "Implementation Started" in poller.comment_on_issue.call_args[0][1]


def test_submit_pr():
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)
    poller.comment_on_issue = MagicMock()
    poller.update_issue_labels = MagicMock()

    issue = GitHubIssue(
        number=15,
        title="feat: Automated tax loss harvesting",
        body="Simulate tax loss offsets",
        labels=["agent:in-progress"],
        url="https://github.com/tiwu/paslood/issues/15",
    )
    poller.get_issue = MagicMock(return_value=issue)
    poller.run_gh = MagicMock(return_value="https://github.com/tiwu/paslood/pull/99")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        pr_url = poller.submit_pr(15)

    assert pr_url == "https://github.com/tiwu/paslood/pull/99"
    poller.update_issue_labels.assert_called_once_with(
        15, add_labels=["agent:review-ready"], remove_labels=["agent:in-progress"]
    )
    poller.comment_on_issue.assert_called_once()
    assert "Pull Request Created for Review" in poller.comment_on_issue.call_args[0][1]


def test_issue_poller_fetch_and_status():
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)

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


def test_checkout_issue():
    poller = IssuePoller(repo="tiwu/paslood", dry_run=False)
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
