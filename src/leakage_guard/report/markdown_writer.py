"""Write ``report.md`` (SPEC 9.3): one reason block per finding, in Indonesian."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from leakage_guard.models import Finding, Report

_BASIS = {
    "design": "pilihan desain (belum dikalibrasi)",
    "deepchecks_default": "default Deepchecks",
    "calibrated": "dikalibrasi",
}


def _val(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.6g}"
    if isinstance(v, dict):
        return ", ".join(f"{k}={_val(x)}" for k, x in v.items())
    if isinstance(v, list):
        return ", ".join(str(x) for x in v)
    return str(v)


def _finding_md(f: Finding) -> str:
    r = f.reason
    title = f"## [{f.severity.value}] {f.check_id}: {f.column or f.scope}"
    if f.waived:
        title += " (DIWAIVER)"
    elif f.waiver is not None:
        title += " (waiver kedaluwarsa)"
    rows = "\n".join(f"| {k} | {_val(v)} |" for k, v in r.evidence.items())
    return "\n".join(
        [
            title,
            "",
            f"**Kenapa ini leakage:** {r.why_leakage}",
            "",
            "| Bukti | Nilai |",
            "|---|---|",
            rows,
            "",
            f"**Dampak:** {r.impact}",
            f"**Kemungkinan akar masalah:** {'; '.join(r.likely_root_causes)}",
            f"**Perbaikan:** {'; '.join(r.remediation)}",
            f"**Keyakinan:** {r.confidence}",
            f"**Basis ambang:** {_BASIS[f.threshold_basis]}",
            f"**Pertanyaan verifikasi:** {r.verification_question}",
            "**Penilaian pemilik model:** (diisi)",
            "",
        ]
    )


def write_markdown(report: Report, path: Path) -> None:
    s = report.summary
    head = [
        f"# Laporan ML Leakage Guard: {report.model_id}",
        "",
        "| | |",
        "|---|---|",
        f"| Gate | **{report.gate}** |",
        f"| Waktu run | {report.run_at} |",
        f"| Config hash | `{report.config_hash}` |",
        f"| Baris train / test | {report.data_fingerprint.get('train_rows')} / "
        f"{report.data_fingerprint.get('test_rows')} |",
        "| CRITICAL / WARNING / INFO / waived | "
        f"{s['critical']} / {s['warning']} / {s['info']} / {s['waived']} |",
        f"| Penilaian pemilik model tertunda | {report.owner_assessment_pending} |",
        "",
        "> Alasan di bawah menjelaskan gejala, bukan vonis. "
        "Keputusan akhir ada pada pemilik model.",
        "",
    ]
    body = [_finding_md(f) for f in report.findings] or ["Tidak ada temuan.", ""]
    path.write_text("\n".join(head + body), encoding="utf-8")
