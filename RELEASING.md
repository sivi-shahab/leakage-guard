# Releasing leakage-guard to PyPI

Releases are published by `.github/workflows/release.yml` when a tag `v*` is pushed. It uses PyPI
Trusted Publishing (OIDC), so no API token is stored anywhere.

## One-time: register the trusted publisher on PyPI

Use a *pending publisher* because the project does not exist on PyPI yet.

| PyPI field | Value |
|---|---|
| PyPI project name | `leakage-guard` |
| Owner | `sivi-shahab` |
| Repository name | `leakage-guard` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

Steps:

1. Log in at <https://pypi.org> (verified email, 2FA enabled).
2. Check that <https://pypi.org/project/leakage-guard/> returns 404. If the name is taken, the
   package must be renamed before anything else.
3. Open <https://pypi.org/manage/account/publishing/>.
4. Under "Add a new pending publisher", choose the **GitHub** tab.
5. Fill in the five fields from the table above. No leading or trailing spaces. Owner and
   repository are plain names, not URLs. Workflow is the file name only, not the full path.
6. Click **Add**. The entry appears under "Pending publishers". Pending entries cannot be edited:
   if a value is wrong, delete the entry and create it again.

The GitHub environment `pypi` already exists (created by the first tag run). No extra GitHub
setting is needed.

## Release a version

1. Bump `version` in `pyproject.toml` and commit. A published version can never be overwritten.
2. Wait for CI to be green on that commit.
3. Tag and push:

   ```bash
   git tag -a vX.Y.Z -m "leakage-guard X.Y.Z"
   git push origin vX.Y.Z
   ```

4. Watch the `release` workflow: `build` then `publish`.

If `publish` failed only because the publisher was not registered yet, re-run just the failed job:

```bash
gh run rerun <run-id> -R sivi-shahab/leakage-guard --failed
```

## Verify

```bash
python -m venv /tmp/v && /tmp/v/bin/pip install leakage-guard==X.Y.Z
/tmp/v/bin/leakage-guard version
```

Also check <https://pypi.org/project/leakage-guard/X.Y.Z/>.

## Troubleshooting

`invalid-publisher: no corresponding publisher`: the claims GitHub sends do not match a publisher
on PyPI. Compare the `repository`, `workflow_ref` and `environment` lines in the failed log with
the table above, check that the entry lives in the right PyPI account, then delete and re-create
the entry if anything differs.
