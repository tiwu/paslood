"""CI/CD Job Summary Generator for GitHub Actions $GITHUB_STEP_SUMMARY.

Provides structured Markdown summaries for linting, testing, documentation,
and release workflows.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def _status_badge(status: str) -> str:
    status_lower = status.strip().lower()
    if status_lower in ("success", "passed", "true"):
        return "✅ Passed"
    if status_lower in ("failure", "failed", "false"):
        return "❌ Failed"
    if status_lower in ("skipped",):
        return "⚠️ Skipped"
    return status or "❓ Unknown"


def generate_lint_summary(
    linter: str = "success",
    formatter: str = "success",
    docs: str = "success",
    python_version: str = "3.11",
    runner: str = "ubuntu-24.04",
    run_id: str = "",
    repo: str = "tiwu/wealth-pilot",
) -> str:
    """Generate Markdown summary for lint & format checks."""
    lines = [
        "## 🔍 Lint & Formatting Summary",
        "",
        "| Check | Status |",
        "| :--- | :--- |",
        f"| Ruff Linter | {_status_badge(linter)} |",
        f"| Ruff Formatter | {_status_badge(formatter)} |",
        f"| MkDocs Strict Build | {_status_badge(docs)} |",
        "",
        "### Environment",
        f"- **Python**: `{python_version}`",
        f"- **Runner**: `{runner}`",
    ]
    if run_id:
        lines.append(
            f"- **Workflow Run**: [#{run_id}](https://github.com/{repo}/actions/runs/{run_id})"
        )
    lines.append("")
    return "\n".join(lines)


def extract_coverage_percentage(markdown_table: str) -> float | None:
    """Extract the total coverage percentage from coverage markdown report table."""
    match = re.search(r"TOTAL.*?(\d+(?:\.\d+)?)%", markdown_table, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def generate_test_summary(
    status: str = "success",
    ui_status: str = "success",
    coverage_markdown: str = "",
    target_threshold: float = 90.0,
    run_id: str = "",
    repo: str = "tiwu/wealth-pilot",
) -> str:
    """Generate Markdown summary for test suite, UI E2E tests, and coverage reporting."""
    lines = [
        "## 🧪 Test Suite & Coverage Summary",
        "",
        "| Suite | Status |",
        "| :--- | :--- |",
        f"| Unit, Integration & Delivery Tests | {_status_badge(status)} |",
        f"| Frontend JS & Playwright UI E2E | {_status_badge(ui_status)} |",
        "",
    ]

    is_success = status.strip().lower() in (
        "success",
        "passed",
        "true",
    ) and ui_status.strip().lower() in (
        "success",
        "passed",
        "true",
    )
    if is_success:
        lines.append("✅ **All tests passed successfully!**")
    else:
        lines.append("❌ **Test suite or coverage checks failed!**")
    lines.append("")

    if coverage_markdown:
        pct = extract_coverage_percentage(coverage_markdown)
        if pct is not None:
            if pct >= target_threshold:
                lines.append(
                    f"🎯 Coverage: **{pct:.1f}%** (Target: $\\ge {target_threshold:.1f}\\%$ — Met ✅)"
                )
            else:
                lines.append(
                    f"⚠️ Coverage: **{pct:.1f}%** (Target: $\\ge {target_threshold:.1f}\\%$ — Below Threshold ❌)"
                )
            lines.append("")
        lines.append("### Coverage Breakdown")
        lines.append("")
        lines.append(coverage_markdown.strip())
        lines.append("")

    if run_id:
        lines.append(
            f"- **Workflow Run**: [#{run_id}](https://github.com/{repo}/actions/runs/{run_id})"
        )
        lines.append("")

    return "\n".join(lines)


def generate_docs_summary(
    status: str = "success",
    pages_url: str = "https://tiwu.github.io/wealth-pilot/",
    commit_sha: str = "",
    timestamp: str = "",
) -> str:
    """Generate Markdown summary for documentation deployment."""
    ts = timestamp or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    is_success = status.strip().lower() in ("success", "passed", "true")

    lines = [
        "## 📚 Documentation Deployment Summary",
        "",
    ]
    if is_success:
        lines.append("✅ **Documentation deployed successfully!**")
    else:
        lines.append("❌ **Documentation deployment failed!**")

    lines.extend(
        [
            "",
            "- **Target**: GitHub Pages",
            f"- **URL**: [{pages_url}]({pages_url})",
        ]
    )
    if commit_sha:
        lines.append(f"- **Commit**: `{commit_sha}`")
    lines.append(f"- **Built At**: {ts}")
    lines.append("")
    return "\n".join(lines)


def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes} B"


def generate_release_summary(
    dist_dir: str | Path = "dist",
    tag: str = "",
    repo: str = "tiwu/wealth-pilot",
) -> str:
    """Generate Markdown summary for release distributions."""
    dist_path = Path(dist_dir)
    lines = [
        "## 📦 Release Artifact Summary",
        "",
    ]
    if tag:
        lines.append(f"- **Release Tag**: `{tag}`")
    if repo and tag:
        lines.append(f"- **Release Link**: https://github.com/{repo}/releases/tag/{tag}")
    lines.append("")

    artifacts: list[tuple[str, int]] = []
    if dist_path.is_dir():
        for file in sorted(dist_path.iterdir()):
            if file.is_file():
                artifacts.append((file.name, file.stat().st_size))

    if artifacts:
        lines.extend(
            [
                "### Built Packages",
                "",
                "| Artifact | Size |",
                "| :--- | :--- |",
            ]
        )
        for name, size in artifacts:
            lines.append(f"| `{name}` | {_format_size(size)} |")
        lines.append("")
    else:
        lines.append("_No release artifacts found in `dist/`._\n")

    return "\n".join(lines)


def write_summary(content: str, output_path: str | Path | None = None) -> None:
    """Print summary and append to target file (or $GITHUB_STEP_SUMMARY)."""
    sys.stdout.write(content)
    target = output_path or os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate CI/CD Markdown Summaries")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # lint
    lint_p = subparsers.add_parser("lint", help="Generate lint & formatting summary")
    lint_p.add_argument("--linter", default="success", help="Ruff linter status")
    lint_p.add_argument("--formatter", default="success", help="Ruff formatter status")
    lint_p.add_argument("--docs", default="success", help="MkDocs build status")
    lint_p.add_argument("--python", default="3.11", help="Python version")
    lint_p.add_argument("--runner", default="ubuntu-24.04", help="Runner OS and architecture")
    lint_p.add_argument("--run-id", default="", help="GitHub run ID")
    lint_p.add_argument("--repo", default="tiwu/wealth-pilot", help="GitHub repo")
    lint_p.add_argument("--output", default=None, help="Output file path")

    # test
    test_p = subparsers.add_parser("test", help="Generate test & coverage summary")
    test_p.add_argument("--status", default="success", help="Pytest execution status")
    test_p.add_argument("--ui-status", default="success", help="Playwright UI E2E execution status")
    test_p.add_argument("--coverage-file", default=None, help="Path to markdown coverage file")
    test_p.add_argument("--threshold", type=float, default=90.0, help="Target coverage threshold")
    test_p.add_argument("--run-id", default="", help="GitHub run ID")
    test_p.add_argument("--repo", default="tiwu/wealth-pilot", help="GitHub repo")
    test_p.add_argument("--output", default=None, help="Output file path")

    # docs
    docs_p = subparsers.add_parser("docs", help="Generate docs deployment summary")
    docs_p.add_argument("--status", default="success", help="Deployment status")
    docs_p.add_argument("--url", default="https://tiwu.github.io/wealth-pilot/", help="Pages URL")
    docs_p.add_argument("--commit", default="", help="Commit SHA")
    docs_p.add_argument("--timestamp", default="", help="Deployment timestamp")
    docs_p.add_argument("--output", default=None, help="Output file path")

    # release
    rel_p = subparsers.add_parser("release", help="Generate release artifacts summary")
    rel_p.add_argument("--dist-dir", default="dist", help="Dist directory path")
    rel_p.add_argument("--tag", default="", help="Release tag")
    rel_p.add_argument("--repo", default="tiwu/wealth-pilot", help="GitHub repo")
    rel_p.add_argument("--output", default=None, help="Output file path")

    args = parser.parse_args(argv)

    if args.command == "lint":
        summary = generate_lint_summary(
            linter=args.linter,
            formatter=args.formatter,
            docs=args.docs,
            python_version=args.python,
            runner=args.runner,
            run_id=args.run_id,
            repo=args.repo,
        )
        write_summary(summary, args.output)

    elif args.command == "test":
        cov_markdown = ""
        if args.coverage_file and Path(args.coverage_file).exists():
            cov_markdown = Path(args.coverage_file).read_text(encoding="utf-8")
        elif Path(".coverage").exists():
            try:
                res = subprocess.run(
                    ["uv", "run", "coverage", "report", "--format=markdown"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    cov_markdown = res.stdout
            except Exception:
                pass

        summary = generate_test_summary(
            status=args.status,
            ui_status=args.ui_status,
            coverage_markdown=cov_markdown,
            target_threshold=args.threshold,
            run_id=args.run_id,
            repo=args.repo,
        )
        write_summary(summary, args.output)

    elif args.command == "docs":
        summary = generate_docs_summary(
            status=args.status,
            pages_url=args.url,
            commit_sha=args.commit,
            timestamp=args.timestamp,
        )
        write_summary(summary, args.output)

    elif args.command == "release":
        summary = generate_release_summary(
            dist_dir=args.dist_dir,
            tag=args.tag,
            repo=args.repo,
        )
        write_summary(summary, args.output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
