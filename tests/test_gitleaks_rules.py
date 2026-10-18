"""The custom gitleaks rules catch each CourtListener token form."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "secrets" / "fake_token.txt"

pytestmark = pytest.mark.skipif(shutil.which("gitleaks") is None, reason="gitleaks not installed")


def test_custom_rules_flag_every_token_form(tmp_path):
    target = tmp_path / "scan"
    target.mkdir()
    shutil.copy(FIXTURE, target / "leak.txt")
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            "gitleaks", "dir", str(target),
            "--config", str(REPO_ROOT / ".gitleaks.toml"),
            "--no-banner", "--redact",
            "--report-format", "json", "--report-path", str(report),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    rule_ids = {finding["RuleID"] for finding in json.loads(report.read_text())}
    assert {
        "courtlistener-token-env",
        "courtlistener-token-header",
        "courtlistener-token-param",
    } <= rule_ids


def test_fixture_path_is_allowlisted_in_repo_scan():
    result = subprocess.run(
        [
            "gitleaks", "dir", str(FIXTURE.parent),
            "--config", str(REPO_ROOT / ".gitleaks.toml"),
            "--no-banner", "--redact",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
