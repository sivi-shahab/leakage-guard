# Waivers

A waiver accepts a known finding for a limited time. Put them in a YAML file and reference it from `gate.waivers_file` (path relative to `guard.yaml`).

```yaml
waivers:
  - finding_id: group_overlap:customer_id     # check_id:column (or scope)
    owner: model.owner@example.com
    approved_by: model.risk@example.com
    reason: "One customer holds several products; impact measured and immaterial"
    expires: 2027-02-28                       # valid through this date, inclusive
```

Rules:

- All five fields are required.
- A waiver applies only while `expires >= run date`. After that the finding **blocks again** automatically.
- A waiver whose `finding_id` matches nothing produces an `orphan_waiver` finding (INFO) so stale waivers get cleaned up.
- Waived findings stay in the report (`waived: true`, with the waiver attached); they are counted separately and do not affect the exit code.
