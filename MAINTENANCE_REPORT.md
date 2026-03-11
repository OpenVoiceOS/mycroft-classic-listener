# Maintenance Report — `mycroft-classic-listener`

## [2026-03-11] — Compliance scaffold + CI modernisation + tests

- **AI Model**: claude-sonnet-4-6
- **Actions Taken**:
  - Added `pyproject.toml` (migrated from `setup.py`; `setup.py` retained for compat)
  - Added `__version__` line to `mycroft_classic_listener/version.py`
  - Replaced stale `TigreGotico/gh-automations@master` workflows with full
    `OpenVoiceOS/gh-automations@dev` set via `ovos-workflows-adder` skill:
    `build-tests.yml`, `lint.yml`, `coverage.yml`, `pip_audit.yml`,
    `repo-health.yml`, `release-preview.yml`, `license_check.yml`,
    `python-support.yml`, `release_workflow.yml`, `publish_stable.yml`
  - Created `test/unittests/test_data_structures.py` — 26 tests for
    `RollingMean` and `CyclicAudioBuffer`
  - Created `test/unittests/test_service_handlers.py` — 27 tests for all
    module-level bus handler functions in `service.py`
  - Created `docs/index.md`, `FAQ.md`, `QUICK_FACTS.md`, `AUDIT.md`,
    `SUGGESTIONS.md`, `MAINTENANCE_REPORT.md`
  - All 53 tests pass
- **Oversight**: Human review and push required
