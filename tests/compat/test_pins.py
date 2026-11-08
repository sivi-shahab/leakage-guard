"""Scheduled pin-compat test (not in default CI): upstream releases beyond the pins must STILL fail.

If a case starts passing, the pin in pyproject.toml may be relaxed -- after re-testing on real data,
including regression (see docs/DECISIONS.md D13).
"""

from __future__ import annotations

import subprocess
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.compat

BASE = ["deepchecks==0.19.1", "numpy<2", "pyarrow<=19.0.1", "anywidget"]
CASES = {
    "sklearn-1.8": ["scikit-learn==1.8.0", "setuptools<81", "pandas<2.3"],
    "setuptools-82": ["scikit-learn<1.6", "setuptools==82.*", "pandas<2.3"],
    "pandas-3": ["scikit-learn<1.6", "setuptools<81", "pandas==3.*"],
}
SMOKE = textwrap.dedent(
    """
    import numpy as np, pandas as pd
    from deepchecks.tabular import Dataset
    from deepchecks.tabular.checks import TrainTestSamplesMix, FeatureLabelCorrelation
    rng = np.random.default_rng(0)
    def mk(n):
        d = pd.DataFrame({"a": rng.normal(size=n), "b": rng.integers(0, 5, n)})
        d["y"] = (d.a > 0).astype(int)
        return Dataset(d, label="y", cat_features=["b"])
    tr, te = mk(300), mk(100)
    TrainTestSamplesMix().run(tr, te, with_display=False)
    FeatureLabelCorrelation().run(tr, with_display=False)
    """
)


@pytest.mark.parametrize("case", CASES)
def test_beyond_pin_still_fails(case: str, tmp_path: Path) -> None:
    venv = tmp_path / "v"
    subprocess.run(["uv", "venv", "-q", "--python", "3.11", str(venv)], check=True)  # noqa: S603, S607
    py = str(venv / "bin" / "python")
    subprocess.run(  # noqa: S603, S607
        ["uv", "pip", "install", "-q", "--python", py, *BASE, *CASES[case]], check=True
    )
    r = subprocess.run([py, "-c", SMOKE], capture_output=True, text=True, timeout=600)  # noqa: S603
    assert r.returncode != 0, f"{case} now PASSES: pins may be relaxable (re-test, update D13)"
