# Reports and outputs

Written to `--out`:

| File | Content |
|---|---|
| `report.json` | Machine-readable report (schema below) |
| `report.md` | Human-readable report: summary table plus one block per finding |
| `*.html` | Deepchecks HTML reports, if `report.attach_html` and not `--no-html` |

## `report.json`

```json
{
  "model_id": "abc-scoring-pd-v3",
  "run_at": "2026-11-08T02:09:03Z",
  "config_hash": "sha256:...",
  "data_fingerprint": {"...": "row counts and schema hash, never data values"},
  "tools": {"deepchecks": "0.19.1", "...": "..."},
  "summary": {"critical": 8, "warning": 2, "info": 1, "waived": 0},
  "gate": "FAILED",
  "owner_assessment_pending": 10,
  "findings": [ { "finding_id": "blocklist_hit:kolektibilitas_akhir",
                  "check_id": "blocklist_hit", "leakage_type": "L4",
                  "severity": "CRITICAL", "scope": "feature", "column": "kolektibilitas_akhir",
                  "metric": {"name": "...", "value": 0.0, "threshold": 0.0},
                  "threshold_basis": "design", "message": "...",
                  "sources": ["builtin"], "waived": false, "waiver": null,
                  "reason": { "summary": "...", "why_leakage": "...", "evidence": {},
                              "impact": "...", "likely_root_causes": [], "remediation": [],
                              "verification_question": "...", "confidence": "high",
                              "owner_assessment": null } } ]
}
```

Output is **deterministic**: with the same inputs, config and seed, two runs produce identical bytes (apart from `run_at`).

## Owner assessment

Each reason has `owner_assessment`: one of `confirmed_leakage`, `legitimate_feature`, `needs_investigation`, or empty. The reports explain *symptoms*, not verdicts; the model owner decides. With `report.require_owner_assessment: true`, the report counts how many findings still await an assessment.

## Typical workflow when blocked

1. Open `report.md`, start with `[CRITICAL]` blocks.
2. Read "Why this is leakage", the evidence table, and the verification question.
3. Either fix the pipeline (remove the column, split by entity/time, rebuild features) and re-run, or, if the feature is legitimate, request a time-limited waiver ([Waivers](waivers.md)).
4. `leakage-guard explain --report out/report.json --finding-id <id>` to share one finding.
