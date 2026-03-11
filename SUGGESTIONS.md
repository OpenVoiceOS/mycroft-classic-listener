# Suggestions — `mycroft-classic-listener`

## 1. Replace PyAudio with OVOSMicrophoneFactory

**Problem**: `mic.py:23` imports `pyaudio` directly. This blocks use of
`ovos-microphone-plugin-*` ecosystem and requires system-level PortAudio.

**Proposed fix**: Replace `Microphone`/`MutableMicrophone` with
`OVOSMicrophoneFactory.create()` (as done in `ovos-simple-listener`).
This removes the PyAudio hard dependency.

**Impact**: High — enables any microphone plugin; removes C extension dep.

## 2. Replace NoiseTracker with OVOSVADFactory

**Problem**: `mic.py:415` implements inline energy-based VAD (`NoiseTracker`).
Cannot use silero, webrtcvad, or other VAD plugins.

**Proposed fix**: Replace `NoiseTracker` usage with `OVOSVADFactory.create()`
and its `is_silence()` interface.

**Impact**: High — enables plugin-based VAD; aligns with dinkum/simple.

## 3. Eliminate global mutable state

**Problem**: `service.py:28-30` uses module-level globals `bus`, `loop`,
`config`. Makes testing fragile and prevents multiple instances.

**Proposed fix**: Move globals into `ClassicListener.__init__` and thread all
handler functions through `self`.

**Impact**: Medium — improves testability; aligns with OVOS service patterns.

## 4. Add STT fallback

**Problem**: No fallback STT path. If the primary STT fails, the utterance
is lost.

**Proposed fix**: Read `stt.fallback_module` from config and load a fallback
STT as done in `ovos-dinkum-listener/plugins.py:102`.

**Impact**: Medium — improves resilience.

## 5. Remove setup.py

**Problem**: Both `setup.py` and `pyproject.toml` are present.

**Proposed fix**: Remove `setup.py` after confirming CI builds pass with
pyproject.toml alone.

**Impact**: Low effort, removes packaging ambiguity.
