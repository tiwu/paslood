"""Unit tests for the release management script."""

from __future__ import annotations

from pathlib import Path

import pytest

from release import (
    bump_version_str,
    detect_bump_type,
    extract_release_notes,
    has_unreleased_changes,
    main,
    update_changelog,
    update_init_version,
    update_pyproject_version,
)

SAMPLE_CHANGELOG = """# Changelog

All notable changes to this project will be documented in this file.

---

## [Unreleased]

### Added
- Feature A: Added new rebalancing algorithm.
- Feature B: Added cloud backups.

### Fixed
- Bugfix C: Resolved API token timeout.

---

## [0.3.0] - 2026-10-14

### Added
- Initial SQLite database caching.

---

[Unreleased]: https://github.com/tiwu/paslood/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/tiwu/paslood/releases/tag/v0.3.0
"""

SAMPLE_CHANGELOG_EMPTY_UNRELEASED = """# Changelog

## [Unreleased]

### Added
<!-- No changes yet -->

### Changed

### Fixed

---

## [0.3.0] - 2026-10-14
"""


def test_bump_version_str():
    assert bump_version_str("0.3.0", "patch") == "0.3.1"
    assert bump_version_str("0.3.0", "minor") == "0.4.0"
    assert bump_version_str("0.3.0", "major") == "1.0.0"
    assert bump_version_str("0.3.0", "0.5.0") == "0.5.0"
    assert bump_version_str("0.3.0", "auto", changelog_content=SAMPLE_CHANGELOG) == "0.4.0"
    with pytest.raises(ValueError):
        bump_version_str("invalid", "minor")
    with pytest.raises(ValueError):
        bump_version_str("0.3.0", "invalid_bump")


def test_detect_bump_type():
    assert detect_bump_type(SAMPLE_CHANGELOG) == "minor"
    patch_changelog = "## [Unreleased]\n\n### Fixed\n- Fix typo in header\n"
    assert detect_bump_type(patch_changelog) == "patch"
    breaking_changelog = "## [Unreleased]\n\n### Changed\n- BREAKING: Drop Python 3.9\n"
    assert detect_bump_type(breaking_changelog) == "major"


def test_has_unreleased_changes():
    assert has_unreleased_changes(SAMPLE_CHANGELOG) is True
    assert has_unreleased_changes(SAMPLE_CHANGELOG_EMPTY_UNRELEASED) is False
    assert has_unreleased_changes("# Changelog\n\nNo unreleased section") is False


def test_extract_release_notes():
    notes = extract_release_notes(SAMPLE_CHANGELOG, "Unreleased")
    assert "Feature A: Added new rebalancing algorithm." in notes
    assert "Bugfix C: Resolved API token timeout." in notes
    assert "Initial SQLite database caching" not in notes

    old_notes = extract_release_notes(SAMPLE_CHANGELOG, "0.3.0")
    assert "Initial SQLite database caching" in old_notes
    assert "Feature A" not in old_notes


def test_update_changelog():
    updated = update_changelog(SAMPLE_CHANGELOG, "0.4.0", "2026-10-25")
    assert "## [Unreleased]" in updated
    assert "## [0.4.0] - 2026-10-25" in updated
    assert "Feature A: Added new rebalancing algorithm." in updated
    assert "[Unreleased]: https://github.com/tiwu/paslood/compare/v0.4.0...HEAD" in updated
    assert "[0.4.0]: https://github.com/tiwu/paslood/compare/v0.3.0...v0.4.0" in updated


def test_update_pyproject_version():
    content = '[build-system]\nrequires = ["hatchling"]\n\n[project]\nname = "wealth-pilot"\nversion = "0.1.0"\n'
    updated = update_pyproject_version(content, "0.4.0")
    assert 'version = "0.4.0"' in updated
    assert 'version = "0.1.0"' not in updated


def test_update_init_version():
    content = '"""Init."""\n__version__ = "0.1.0"\n'
    updated = update_init_version(content, "0.4.0")
    assert '__version__ = "0.4.0"' in updated


def test_cli_check_unreleased(tmp_path: Path):
    cl_file = tmp_path / "CHANGELOG.md"
    cl_file.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    assert main(["check-unreleased", "--changelog", str(cl_file)]) == 0

    cl_file.write_text(SAMPLE_CHANGELOG_EMPTY_UNRELEASED, encoding="utf-8")
    assert main(["check-unreleased", "--changelog", str(cl_file)]) == 1


def test_cli_extract_notes(tmp_path: Path, capsys):
    cl_file = tmp_path / "CHANGELOG.md"
    cl_file.write_text(SAMPLE_CHANGELOG, encoding="utf-8")
    out_file = tmp_path / "notes.md"

    rc = main(
        [
            "extract-notes",
            "--changelog",
            str(cl_file),
            "--version",
            "0.3.0",
            "--output",
            str(out_file),
        ]
    )
    assert rc == 0
    assert "Initial SQLite database caching" in out_file.read_text(encoding="utf-8")


def test_cli_bump(tmp_path: Path):
    cl_file = tmp_path / "CHANGELOG.md"
    cl_file.write_text(SAMPLE_CHANGELOG, encoding="utf-8")

    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "wealth-pilot"\nversion = "0.3.0"\n', encoding="utf-8"
    )

    init_dir = tmp_path / "src" / "wealth_pilot"
    init_dir.mkdir(parents=True)
    init_file = init_dir / "__init__.py"
    init_file.write_text('__version__ = "0.3.0"\n', encoding="utf-8")

    rc = main(["bump", "minor", "--root-dir", str(tmp_path), "--date", "2026-10-25"])
    assert rc == 0

    assert 'version = "0.4.0"' in pyproject_file.read_text(encoding="utf-8")
    assert '__version__ = "0.4.0"' in init_file.read_text(encoding="utf-8")
    assert "## [0.4.0] - 2026-10-25" in cl_file.read_text(encoding="utf-8")
