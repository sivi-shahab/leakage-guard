# Installation

Requirements: Python 3.11 or 3.12 (3.13 is **not** supported/tested), [`uv`](https://docs.astral.sh/uv/).

Deepchecks and Cleanlab have conflicting pins, so there are separate environments, each rebuilt from a hash-pinned lockfile in `locks/`:

| Environment | Contents | Lockfile | Python |
|---|---|---|---|
| core (`.venv`) | `builtin` detector, CLI, core tests | `locks/core.lock` | 3.11 / 3.12 |
| `.envs/dc` | deepchecks 0.19.1 + ppscore | `locks/dc.lock` | 3.11 |
| `.envs/cl` | cleanlab[datalab] | `locks/cl.lock` | 3.12 |
| `.envs/sg` | semgrep (rule L6 tests only) | `locks/sg.lock` | 3.11+ |

```bash
make_env() {  # usage: make_env <dir> <python> <lock-name>
  uv venv --python "$2" "$1" \
  && uv pip install --python "$1/bin/python" --require-hashes --no-deps -r "locks/$3.lock" \
  && uv pip install --python "$1/bin/python" --no-deps -e .
}
make_env .venv    3.12 core
make_env .envs/dc 3.11 dc      # only if you use deepchecks / ppscore
make_env .envs/cl 3.12 cl      # only if you use cleanlab
```

You only need the environments for the detectors you enable. With just `builtin`, the core environment is enough.

**Do not install deepchecks and cleanlab into one environment.** If you must, you need `pyarrow<=19.0.1` and `numpy<2`; the deepchecks detector logs a warning (not an error) when these pins are not met.

Pins are deliberate (`scikit-learn<1.6`, `numpy<2`, `pandas<2.3`, `setuptools<81`, `pyarrow<=19.0.1`). Do not relax them without re-testing; the scheduled `tests/compat` job checks that versions beyond the pins still fail.
