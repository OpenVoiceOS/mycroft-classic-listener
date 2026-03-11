# Audit — `mycroft-classic-listener`

## Config Key Cross-check vs canonical mycroft.conf

### Keys read — present in canonical mycroft.conf ✅

| Key | Source |
|---|---|
| `listener.wake_word` | `listener.py:360` |
| `listener.stand_up_word` | `listener.py:404` |
| `listener.sample_rate` | `listener.py:331` |
| `listener.recording_timeout` | `mic.py:597` |
| `listener.recording_timeout_with_silence` | `mic.py:602` |
| `listener.save_utterances` | `mic.py:579` |
| `listener.record_wake_words` | `mic.py:580` |
| `listener.save_path` | `mic.py:581` |
| `listener.mute_during_output` | `service.py:141` |
| `confirm_listening` (top-level) | `mic.py:948` |
| `listener.multiplier` | `mic.py:574` |
| `listener.energy_ratio` | `mic.py:575` |

### Keys read — absent from canonical mycroft.conf ⚠️ (undocumented)

| Key | Default | Source | Notes |
|---|---|---|---|
| `listener.overflow_exception` | `False` | `mic.py:560` | PyAudio stream overflow handling |
| `listener.device_index` | None | `listener.py:333` | Specific mic device index |
| `listener.device_name` | None | `listener.py:334` | Specific mic device name (regex) |
| `listener.wake_word_upload.url` | `""` | `mic.py:556` | Upload endpoint for WW data collection |
| `listener.wake_word_upload.disable` | `True` | `mic.py:557` | Disable WW upload |
| `opt_in` (top-level) | `False` | `listener.py:303`, `mic.py:796` | Mycroft data opt-in flag |

**Action needed**: add `device_index`, `device_name`, `overflow_exception`,
`opt_in` to canonical `ovos-config/mycroft.conf`.

Note: `wake_word_upload` is already in canonical mycroft.conf but the
`opt_in` key and device selection keys are not.

### Stale Mycroft-era keys still consumed

| Key | Status |
|---|---|
| `listener.multiplier` | Legacy energy multiplier — no effect in most VAD configs |
| `listener.energy_ratio` | Legacy energy ratio — dinkum ignores these |
| `opt_in` | Mycroft data collection; no OVOS backend supports this |

---

## Technical Debt

- **No VAD plugin support** — noise detection is implemented via `NoiseTracker`
  inline energy tracking (`mic.py:415`) rather than OVOSVADFactory. Cannot
  use silero or other VAD plugins.
- **PyAudio hard dependency** — `mic.py:23` imports pyaudio directly; cannot
  use `ovos-microphone-plugin-*` ecosystem.
- **`setup.py` retained** — `pyproject.toml` added but `setup.py` still present.
  Remove `setup.py` once CI confirms `pyproject.toml` builds cleanly.
- **Global mutable state** — `service.py` uses module-level globals `bus`, `loop`,
  `config` (`service.py:28-30`). Makes unit testing fragile (must patch globals).
- **`actions/checkout@v6`** — stale ref in old workflows; replaced by @dev workflow set.
- **No STT fallback** — `listener.py` creates a single STT via `OVOSSTTFactory`;
  no fallback STT path like dinkum-listener provides.
- **AudioStreamHandler** (`listener.py:52`) — streaming STT path exists but is
  largely untested; `handle_stream_start/chunk/stop` have no unit tests.
