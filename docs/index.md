# mycroft-classic-listener

The original Mycroft voice listener ported to the OVOS plugin ecosystem. It
implements the same `recognizer_loop:*` messagebus contract as
`ovos-dinkum-listener` and `ovos-simple-listener`.

## Architecture

```
MessageBusClient
       │
ClassicListener (Thread) — service.py:209
       │
RecognizerLoop (EventEmitter) — listener.py:308
       ├── AudioProducer (Thread) — listener.py:81
       │       └── ResponsiveRecognizer — mic.py:528
       │               ├── MutableMicrophone (PyAudio) — mic.py:332
       │               └── NoiseTracker (VAD) — mic.py:415
       └── AudioConsumer (Thread) — listener.py:143
               └── STT plugin (OVOSSTTFactory)
```

## Key Classes

| Class | File | Description |
|---|---|---|
| `ClassicListener` | `service.py:209` | Main service thread; wires bus ↔ loop |
| `RecognizerLoop` | `listener.py:308` | EventEmitter; spawns producer/consumer threads |
| `AudioProducer` | `listener.py:81` | Reads mic, feeds `ResponsiveRecognizer` |
| `AudioConsumer` | `listener.py:143` | Dequeues audio, runs STT, emits utterance events |
| `ResponsiveRecognizer` | `mic.py:528` | Wake-word detection + phrase recording |
| `MutableMicrophone` | `mic.py:332` | PyAudio wrapper with mute/unmute control |
| `NoiseTracker` | `mic.py:415` | Silence detection for utterance end |
| `RollingMean` | `data_structures.py:19` | Optimized sliding window mean for energy |
| `CyclicAudioBuffer` | `data_structures.py:64` | Ring buffer for audio frames |

## Bus Events

### Emitted

| Event | Trigger |
|---|---|
| `recognizer_loop:record_begin` | Mic starts recording — `service.py:38` |
| `recognizer_loop:record_end` | Mic stops recording — `service.py:46` |
| `recognizer_loop:wakeword` | Wake word detected — `service.py:66` |
| `recognizer_loop:utterance` | STT success — `service.py:77` |
| `mycroft.speech.recognition.unknown` | STT failure — `service.py:83` |
| `mycroft.awoken` | Listener woke from sleep — `service.py:61` |
| `enclosure.notify.no_internet` | No connectivity — `service.py:53` |
| `speak` | TTS request forwarded — `service.py:92` |

### Handled

| Event | Handler | Effect |
|---|---|---|
| `recognizer_loop:sleep` | `handle_sleep` | Puts loop to sleep — `service.py:95` |
| `recognizer_loop:wake_up` | `handle_wake_up` | Wakes loop — `service.py:100` |
| `mycroft.mic.mute` | `handle_mic_mute` | Mutes mic — `service.py:105` |
| `mycroft.mic.unmute` | `handle_mic_unmute` | Unmutes mic — `service.py:110` |
| `mycroft.mic.listen` | `handle_mic_listen` | Triggers listen without WW — `service.py:115` |
| `mycroft.mic.get_status` | `handle_mic_get_status` | Returns `{muted: bool}` — `service.py:123` |
| `recognizer_loop:audio_output_start` | `handle_audio_start` | Mutes if `mute_during_output` — `service.py:134` |
| `recognizer_loop:audio_output_end` | `handle_audio_end` | Restores mute state — `service.py:145` |
| `mycroft.stop` | `handle_stop` | Force-unmutes — `service.py:153` |

## Configuration

All keys are under `listener` in `mycroft.conf`:

| Key | Default | Source |
|---|---|---|
| `wake_word` | `"hey mycroft"` | `listener.py:360` |
| `stand_up_word` | `"wake up"` | `listener.py:404` |
| `sample_rate` | — | `listener.py:331` |
| `device_index` | — | `listener.py:333` |
| `device_name` | — | `listener.py:334` |
| `mute_during_output` | — | `service.py:141` |
| `recording_timeout` | `10.0` | `mic.py:597` |
| `recording_timeout_with_silence` | `3.0` | `mic.py:602` |
| `save_utterances` | `False` | `mic.py:579` |
| `record_wake_words` | `False` | `mic.py:580` |
| `save_path` | `gettempdir()` | `mic.py:581` |
| `multiplier` | — | `mic.py:574` |
| `energy_ratio` | — | `mic.py:575` |
| `confirm_listening` | — | `mic.py:948` |
| `overflow_exception` | `False` | `mic.py:560` |

## Installation

```bash
uv pip install -e .
```

## Running Tests

```bash
uv run pytest test/ --cov=mycroft_classic_listener
```
