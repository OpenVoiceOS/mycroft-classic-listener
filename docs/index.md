# mycroft-classic-listener

This page describes the internal architecture of `mycroft-classic-listener`: the
original Mycroft voice listener, ported to the OVOS plugin ecosystem. It implements the
same `recognizer_loop:*` messagebus contract as `ovos-dinkum-listener` and
`ovos-simple-listener`.

## Architecture

```
MessageBusClient
       │
ClassicListener (Thread): service.py:206
       │
RecognizerLoop (EventEmitter): listener.py:316
       ├── AudioProducer (Thread): listener.py:81
       │       └── ResponsiveRecognizer: mic.py:528
       │               ├── MutableMicrophone (PyAudio): mic.py:332
       │               └── NoiseTracker (VAD): mic.py:415
       └── AudioConsumer (Thread): listener.py:143
               └── STT plugin (OVOSSTTFactory)
```

## Key classes

| Class | Description | Location |
|---|---|---|
| `ClassicListener` | Main service thread. Wires the bus to the loop. | `service.py:206` |
| `RecognizerLoop` | Event emitter that spawns the producer and consumer threads. | `listener.py:316` |
| `AudioProducer` | Reads the microphone and feeds `ResponsiveRecognizer`. | `listener.py:81` |
| `AudioConsumer` | Dequeues audio, runs STT, and emits utterance events. | `listener.py:143` |
| `ResponsiveRecognizer` | Detects the wake word and records the phrase. | `mic.py:528` |
| `MutableMicrophone` | Wraps PyAudio and controls mute and unmute. | `mic.py:332` |
| `NoiseTracker` | Detects silence to mark the end of an utterance. | `mic.py:415` |
| `RollingMean` | Sliding window mean, used for energy tracking. | `data_structures.py:18` |
| `CyclicAudioBuffer` | Ring buffer for audio frames. | `data_structures.py:64` |

## Bus events

### Emitted

| Event | Trigger | Location |
|---|---|---|
| `recognizer_loop:record_begin` | The microphone starts recording. | `service.py:38` |
| `recognizer_loop:record_end` | The microphone stops recording. | `service.py:45` |
| `recognizer_loop:wakeword` | The listener detects the wake word. | `service.py:63` |
| `recognizer_loop:utterance` | STT succeeds. | `service.py:76` |
| `mycroft.speech.recognition.unknown` | STT fails. | `service.py:81` |
| `mycroft.awoken` | The listener wakes from sleep. | `service.py:58` |
| `enclosure.notify.no_internet` | The device has no connectivity. | `service.py:51` |
| `speak` | The listener forwards a TTS request. | `service.py:89` |

### Handled

| Event | Handler | Effect | Location |
|---|---|---|---|
| `recognizer_loop:sleep` | `handle_sleep` | Puts the loop to sleep. | `service.py:92` |
| `recognizer_loop:wake_up` | `handle_wake_up` | Wakes the loop. | `service.py:97` |
| `mycroft.mic.mute` | `handle_mic_mute` | Mutes the microphone. | `service.py:102` |
| `mycroft.mic.unmute` | `handle_mic_unmute` | Unmutes the microphone. | `service.py:107` |
| `mycroft.mic.listen` | `handle_mic_listen` | Starts listening without the wake word. | `service.py:112` |
| `mycroft.mic.get_status` | `handle_mic_get_status` | Returns `{muted: bool}`. | `service.py:120` |
| `recognizer_loop:audio_output_start` | `handle_audio_start` | Mutes the microphone if `mute_during_output` is set. | `service.py:131` |
| `recognizer_loop:audio_output_end` | `handle_audio_end` | Restores the previous mute state. | `service.py:142` |
| `mycroft.stop` | `handle_stop` | Force-unmutes the microphone. | `service.py:150` |

## Configuration

All keys below live under `listener` in `mycroft.conf`.

| Key | Default | Source |
|---|---|---|
| `wake_word` | `"hey mycroft"` | `listener.py:374` |
| `stand_up_word` | `"wake up"` | `listener.py:422` |
| `sample_rate` | not set | `listener.py:339` |
| `device_index` | not set | `listener.py:341` |
| `device_name` | not set | `listener.py:342` |
| `mute_during_output` | not set | `service.py:138` |
| `recording_timeout` | `10.0` | `mic.py:597` |
| `recording_timeout_with_silence` | `3.0` | `mic.py:602` |
| `save_utterances` | `False` | `mic.py:579` |
| `record_wake_words` | `False` | `mic.py:580` |
| `save_path` | `gettempdir()` | `mic.py:581` |
| `multiplier` | not set | `mic.py:574` |
| `energy_ratio` | not set | `mic.py:575` |
| `confirm_listening` | not set | `mic.py:948` |
| `overflow_exception` | `False` | `mic.py:560` |

## Install

```bash
uv pip install -e .
```

## Run the tests

```bash
uv run pytest test/ --cov=mycroft_classic_listener
```
