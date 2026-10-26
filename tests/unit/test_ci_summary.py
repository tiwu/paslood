"""Unit tests for CI/CD job summary generator script."""

from __future__ import annotations

from pathlib import Path

import pytest

from ci_summary import (
    extract_coverage_percentage,
    generate_docs_summary,
    generate_lint_summary,
    generate_release_summary,
    generate_test_summary,
    main,
    write_summary,
)


def test_generate_lint_summary_success():
    summary = generate_lint_summary(
        linter="success",
        formatter="success",
        docs="success",
        python_version="3.11",
        runner="ubuntu-24.04 (X64)",
        run_id="123456",
    )
    assert "## 🔍 Lint & Formatting Summary" in summary
    assert "| Ruff Linter | ✅ Passed |" in summary
    assert "| Ruff Formatter | ✅ Passed |" in summary
    assert "| MkDocs Strict Build | ✅ Passed |" in summary
    assert "**Python**: `3.11`" in summary
    assert "**Runner**: `ubuntu-24.04 (X64)`" in summary
    assert "https://github.com/tiwu/paslood/actions/runs/123456" in summary


def test_generate_lint_summary_failure():
    summary = generate_lint_summary(
        linter="failure",
        formatter="success",
        docs="failure",
        python_version="3.11",
        runner="Linux",
    )
    assert "| Ruff Linter | ❌ Failed |" in summary
    assert "| Ruff Formatter | ✅ Passed |" in summary
    assert "| MkDocs Strict Build | ❌ Failed |" in summary


def test_extract_coverage_percentage():
    table = (
        "| Name | Stmts | Miss | Cover |\n"
        "|---|---:|---:|---:|\n"
        "| src/wealth_pilot/domain.py | 10 | 0 | 100% |\n"
        "| **TOTAL** | **100** | **9** | **91%** |\n"
    )
    assert extract_coverage_percentage(table) == 91.0

    table_decimal = "| TOTAL | 100 | 8 | 92.5% |"
    assert extract_coverage_percentage(table_decimal) == 92.5

    assert extract_coverage_percentage("no coverage here") is None


def test_generate_test_summary_success_and_threshold():
    cov_table = (
        "| Name | Stmts | Miss | Cover |\n"
        "|---|---:|---:|---:|\n"
        "| **TOTAL** | **100** | **9** | **91%** |\n"
    )
    summary_met = generate_test_summary(
        status="success",
        ui_status="success",
        coverage_markdown=cov_table,
        target_threshold=90.0,
    )
    assert "## 🧪 Test Suite & Coverage Summary" in summary_met
    assert "| Unit, Integration & Delivery Tests | ✅ Passed |" in summary_met
    assert "| Frontend JS & Playwright UI E2E | ✅ Passed |" in summary_met
    assert "✅ **All tests passed successfully!**" in summary_met
    assert "🎯 Coverage: **91.0%** (Target: $\\ge 90.0\\%$ — Met ✅)" in summary_met
    assert cov_table in summary_met

    summary_failed = generate_test_summary(
        status="failure",
        ui_status="failure",
        coverage_markdown="| **TOTAL** | **100** | **20** | **80%** |\n",
        target_threshold=90.0,
    )
    assert "| Frontend JS & Playwright UI E2E | ❌ Failed |" in summary_failed
    assert "❌ **Test suite or coverage checks failed!**" in summary_failed
    assert "⚠️ Coverage: **80.0%** (Target: $\\ge 90.0\\%$ — Below Threshold ❌)" in summary_failed


def test_generate_docs_summary():
    summary = generate_docs_summary(
        status="success",
        pages_url="https://tiwu.github.io/paslood/",
        commit_sha="abcdef123456",
        timestamp="2026-10-25 18:00 UTC",
    )
    assert "## 📚 Documentation Deployment Summary" in summary
    assert "✅ **Documentation deployed successfully!**" in summary
    assert "[https://tiwu.github.io/paslood/](https://tiwu.github.io/paslood/)" in summary
    assert "`abcdef123456`" in summary
    assert "2026-10-25 18:00 UTC" in summary


def test_generate_release_summary(tmp_path: Path):
    dist = tmp_path / "dist"
    dist.mkdir()
    whl = dist / "wealth_pilot-1.0.0-py3-none-any.whl"
    whl.write_bytes(b"x" * 2048)
    tar = dist / "wealth_pilot-1.0.0.tar.gz"
    tar.write_bytes(b"y" * 1024)

    summary = generate_release_summary(
        dist_dir=dist,
        tag="v1.0.0",
        repo="tiwu/paslood",
    )
    assert "## 📦 Release Artifact Summary" in summary
    assert "- **Release Tag**: `v1.0.0`" in summary
    assert "wealth_pilot-1.0.0-py3-none-any.whl" in summary
    assert "wealth_pilot-1.0.0.tar.gz" in summary
    assert "https://github.com/tiwu/paslood/releases/tag/v1.0.0" in summary


def test_write_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    write_summary("Line 1\n")
    write_summary("Line 2\n")

    captured = capsys.readouterr()
    assert "Line 1" in captured.out
    assert "Line 2" in captured.out

    content = summary_file.read_text(encoding="utf-8")
    assert content == "Line 1\nLine 2\n"


def test_cli_subcommands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    # Test lint CLI
    exit_code = main(["lint", "--linter", "success", "--formatter", "success", "--docs", "success"])
    assert exit_code == 0
    assert "Lint & Formatting Summary" in summary_file.read_text(encoding="utf-8")

    # Reset summary
    summary_file.unlink()

    # Test test CLI with mock coverage
    cov_file = tmp_path / "cov.md"
    cov_file.write_text("| **TOTAL** | **10** | **0** | **100%** |\n", encoding="utf-8")
    exit_code = main(["test", "--status", "success", "--coverage-file", str(cov_file)])
    assert exit_code == 0
    assert "Test Suite & Coverage Summary" in summary_file.read_text(encoding="utf-8")

    # Test docs CLI
    exit_code = main(["docs", "--status", "success", "--commit", "123456"])
    assert exit_code == 0

    # Test release CLI
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "pkg.whl").write_bytes(b"content")
    exit_code = main(["release", "--dist-dir", str(dist_dir), "--tag", "v1.0.0"])
    assert exit_code == 0
