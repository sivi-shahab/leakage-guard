# Privacy guarantees

- Columns in `data.pii_columns` are dropped before any detector sees the data. Exception: if a role column (`entity_col`, `time_col`, `index_col`, `target`) is also listed as PII, it is replaced by a truncated SHA-256 pseudonym so overlap checks still work. (A hash is **not** anonymisation under the Indonesian PDP law, Art. 4(3)(f), so the values are still never written to any output.)
- Reports, logs and evidence contain **aggregates only**, never row values. Quasi-identifier columns may be used by detectors but their values never appear in outputs.
- The data fingerprint contains row counts and a schema hash, not value hashes.
- Preflight warns (`quasi_identifier_risk`, WARNING) when a combination of quasi-identifier columns yields groups smaller than `privacy.min_group_size`.
- Automated tests plant unique marker values in PII and quasi-identifier columns and assert they appear in none of `report.json`, `report.md` or the HTML files (AC-5).

Regulatory statements in the project are limited to what `SPEC.md` claims; compliance confirmation is a `TODO(owner)`.
