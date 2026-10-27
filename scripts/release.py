"""Release management utility for Paslood.

Automates version bumping, changelog updates, and release note extraction.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a semantic version string (e.g. '0.3.0' or 'v0.3.0')."""
    clean_ver = version.lstrip("v").strip()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", clean_ver)
    if not match:
        raise ValueError(f"Invalid semver string: {version!r}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def detect_bump_type(changelog_content: str) -> str:
    """Detect whether unreleased changes represent a major, minor, or patch bump."""
    notes = extract_release_notes(changelog_content, "Unreleased")
    if not notes.strip():
        return "patch"

    # Check for breaking changes
    if "BREAKING" in notes.upper():
        return "major"

    # Check for Added section having bullet points
    added_match = re.search(r"###\s+Added\s*\n(.*?)(?=\n###|\Z)", notes, flags=re.DOTALL)
    if added_match:
        added_text = added_match.group(1)
        for line in added_text.splitlines():
            line_str = line.strip()
            if line_str.startswith("- ") or line_str.startswith("* "):
                return "minor"

    return "patch"


def bump_version_str(current: str, bump_type: str, changelog_content: str = "") -> str:
    """Calculate next version string based on bump type (patch, minor, major, auto) or explicit semver."""
    clean_bump = bump_type.strip().lower()
    if clean_bump == "auto":
        clean_bump = detect_bump_type(changelog_content) if changelog_content else "minor"

    if clean_bump in ("patch", "minor", "major"):
        major, minor, patch = parse_semver(current)
        if clean_bump == "patch":
            return f"{major}.{minor}.{patch + 1}"
        if clean_bump == "minor":
            return f"{major}.{minor + 1}.0"
        return f"{major + 1}.0.0"

    # Treat as explicit version
    major, minor, patch = parse_semver(clean_bump)
    return f"{major}.{minor}.{patch}"


def has_unreleased_changes(changelog_content: str) -> bool:
    """Check if the ## [Unreleased] section contains substantive changes."""
    notes = extract_release_notes(changelog_content, "Unreleased")
    if not notes.strip():
        return False

    for line in notes.splitlines():
        trimmed = line.strip()
        if not trimmed:
            continue
        if trimmed.startswith("### "):
            continue
        if trimmed.startswith("<!--") and trimmed.endswith("-->"):
            continue
        if trimmed.startswith("<!--"):
            continue
        if trimmed.endswith("-->"):
            continue
        if trimmed == "---" or trimmed.startswith("---"):
            continue
        if trimmed.startswith("- ") or trimmed.startswith("* "):
            # Has an item
            return True

    return False


def extract_release_notes(changelog_content: str, version: str = "Unreleased") -> str:
    """Extract markdown notes for a specific version section from CHANGELOG.md."""
    # Pattern to match ## [version] or ## [version] - YYYY-MM-DD
    escaped_ver = re.escape(version)
    pattern = rf"^##\s+\[{escaped_ver}\](?:[^\n]*)?\n(.*?)(?=\n##\s+\[|\Z)"
    match = re.search(pattern, changelog_content, flags=re.MULTILINE | re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def update_changelog(changelog_content: str, new_version: str, release_date: str) -> str:
    """Promote ## [Unreleased] to ## [new_version] - release_date and insert fresh Unreleased section."""
    unreleased_pattern = r"(##\s+\[Unreleased\](?:[^\n]*)?\n)"
    match = re.search(unreleased_pattern, changelog_content)
    if not match:
        raise ValueError("Could not find ## [Unreleased] section in CHANGELOG.md")

    new_section_header = f"## [Unreleased]\n\n### Added\n\n### Changed\n\n### Fixed\n\n---\n\n## [{new_version}] - {release_date}\n"

    # Replace the ## [Unreleased] header with the new header and the stamped release
    updated = (
        changelog_content[: match.start()] + new_section_header + changelog_content[match.end() :]
    )

    # Update bottom comparison links if present
    # e.g.:
    # [Unreleased]: https://github.com/tiwu/paslood/compare/v0.3.0...HEAD
    # [0.3.0]: https://github.com/tiwu/paslood/releases/tag/v0.3.0
    link_unreleased = re.search(
        r"\[Unreleased\]:\s+https://github\.com/([^/]+/[^/]+)/compare/v([0-9.]+)\.\.\.HEAD", updated
    )
    if link_unreleased:
        repo = link_unreleased.group(1)
        prev_ver = link_unreleased.group(2)
        old_link_block = link_unreleased.group(0)
        new_link_block = (
            f"[Unreleased]: https://github.com/{repo}/compare/v{new_version}...HEAD\n"
            f"[{new_version}]: https://github.com/{repo}/compare/v{prev_ver}...v{new_version}"
        )
        updated = updated.replace(old_link_block, new_link_block, 1)

    return updated


def update_pyproject_version(pyproject_content: str, new_version: str) -> str:
    """Update version = "..." under [project] in pyproject.toml."""
    pattern = r'(version\s*=\s*")[^"]+(")'
    updated, count = re.subn(pattern, rf"\g<1>{new_version}\g<2>", pyproject_content, count=1)
    if count == 0:
        raise ValueError("Could not find version field in pyproject.toml")
    return updated


def update_init_version(init_content: str, new_version: str) -> str:
    """Update __version__ = "..." in src/paslood/__init__.py."""
    pattern = r'(__version__\s*=\s*")[^"]+(")'
    updated, count = re.subn(pattern, rf"\g<1>{new_version}\g<2>", init_content, count=1)
    if count == 0:
        raise ValueError("Could not find __version__ in __init__.py")
    return updated


def perform_bump(
    root_dir: str | Path = ".",
    bump_type: str = "minor",
    release_date: str | None = None,
) -> str:
    """Orchestrate version bumping across pyproject.toml, __init__.py, and CHANGELOG.md."""
    root = Path(root_dir)
    pyproject_path = root / "pyproject.toml"
    init_path = root / "src" / "paslood" / "__init__.py"
    changelog_path = root / "CHANGELOG.md"

    if not pyproject_path.exists():
        raise FileNotFoundError(f"Missing {pyproject_path}")
    if not init_path.exists():
        raise FileNotFoundError(f"Missing {init_path}")
    if not changelog_path.exists():
        raise FileNotFoundError(f"Missing {changelog_path}")

    rel_date = release_date or date.today().isoformat()

    pyproject_content = pyproject_path.read_text(encoding="utf-8")
    init_content = init_path.read_text(encoding="utf-8")
    changelog_content = changelog_path.read_text(encoding="utf-8")

    # Determine current version from pyproject.toml
    ver_match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_content)
    if not ver_match:
        raise ValueError("Could not parse current version from pyproject.toml")
    current_ver = ver_match.group(1)

    # If changelog has a higher released version than pyproject, use changelog highest
    cl_highest = re.search(r"##\s+\[([0-9]+\.[0-9]+\.[0-9]+)\]", changelog_content)
    if cl_highest:
        cl_ver = cl_highest.group(1)
        if parse_semver(cl_ver) > parse_semver(current_ver):
            current_ver = cl_ver

    new_version = bump_version_str(current_ver, bump_type, changelog_content=changelog_content)

    new_pyproject = update_pyproject_version(pyproject_content, new_version)
    new_init = update_init_version(init_content, new_version)
    new_changelog = update_changelog(changelog_content, new_version, rel_date)

    pyproject_path.write_text(new_pyproject, encoding="utf-8")
    init_path.write_text(new_init, encoding="utf-8")
    changelog_path.write_text(new_changelog, encoding="utf-8")

    return new_version


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paslood release management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check-unreleased
    check_p = subparsers.add_parser(
        "check-unreleased", help="Check if CHANGELOG has unreleased changes"
    )
    check_p.add_argument("--changelog", default="CHANGELOG.md", help="Path to CHANGELOG.md")

    # Subcommand: extract-notes
    notes_p = subparsers.add_parser("extract-notes", help="Extract release notes for a version")
    notes_p.add_argument("--changelog", default="CHANGELOG.md", help="Path to CHANGELOG.md")
    notes_p.add_argument("--version", default="Unreleased", help="Version to extract notes for")
    notes_p.add_argument(
        "--output", default=None, help="File to write notes to (defaults to stdout)"
    )

    # Subcommand: bump
    bump_p = subparsers.add_parser("bump", help="Bump version across files")
    bump_p.add_argument(
        "bump_type", default="minor", nargs="?", help="Bump type (patch, minor, major) or semver"
    )
    bump_p.add_argument("--root-dir", default=".", help="Root directory of repository")
    bump_p.add_argument("--date", default=None, help="Release date override (YYYY-MM-DD)")

    args = parser.parse_args(argv)

    if args.command == "check-unreleased":
        cl_path = Path(args.changelog)
        if not cl_path.exists():
            sys.stderr.write(f"Error: {args.changelog} not found\n")
            return 1
        content = cl_path.read_text(encoding="utf-8")
        if has_unreleased_changes(content):
            sys.stdout.write("Unreleased changes detected.\n")
            return 0
        sys.stdout.write("No unreleased changes detected.\n")
        return 1

    if args.command == "extract-notes":
        cl_path = Path(args.changelog)
        if not cl_path.exists():
            sys.stderr.write(f"Error: {args.changelog} not found\n")
            return 1
        content = cl_path.read_text(encoding="utf-8")
        notes = extract_release_notes(content, args.version)
        if args.output:
            Path(args.output).write_text(notes + "\n", encoding="utf-8")
        else:
            sys.stdout.write(notes + "\n")
        return 0

    if args.command == "bump":
        new_ver = perform_bump(
            root_dir=args.root_dir, bump_type=args.bump_type, release_date=args.date
        )
        sys.stdout.write(f"new_version={new_ver}\n")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
