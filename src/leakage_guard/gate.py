"""Gate: exit code from unwaived findings. 0 pass, 1 blocked (2 is raised as an error)."""

from __future__ import annotations

from leakage_guard.models import Finding, Severity


def exit_code(findings: list[Finding], fail_on: list[Severity]) -> int:
    blocked = any((not f.waived) and f.severity in fail_on for f in findings)
    return 1 if blocked else 0
