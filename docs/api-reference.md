# API reference

The public Python API. The command-line interface is documented in {doc}`cli`.

## Running the gate

```{eval-rst}
.. autofunction:: leakage_guard.orchestrator.run_guard

.. autofunction:: leakage_guard.gate.exit_code

.. autoclass:: leakage_guard.gate.GateHook
   :members:
```

## Configuration

```{eval-rst}
.. autofunction:: leakage_guard.config.load_config

.. autoclass:: leakage_guard.config.GuardConfig
   :members: config_hash

.. autoclass:: leakage_guard.config.ThresholdsCfg
```

## Findings and reports

```{eval-rst}
.. autoclass:: leakage_guard.models.RawFinding
.. autoclass:: leakage_guard.models.Finding
.. autoclass:: leakage_guard.models.Report
.. autoclass:: leakage_guard.models.Reason
.. autoclass:: leakage_guard.models.Waiver
.. autoclass:: leakage_guard.models.Severity
```

## Detectors

```{eval-rst}
.. autoclass:: leakage_guard.detectors.base.DetectorContext
.. autoclass:: leakage_guard.detectors.base.Detector
   :members:
.. autofunction:: leakage_guard.detectors.base.register
.. autofunction:: leakage_guard.detectors.base.get_detector
.. autofunction:: leakage_guard.detectors.common.classify
.. autofunction:: leakage_guard.detectors.common.make_raw
```

## Prevention

```{eval-rst}
.. automodule:: leakage_guard.prevention.splits
   :members:

.. automodule:: leakage_guard.prevention.pipeline_integrity
   :members:
```
