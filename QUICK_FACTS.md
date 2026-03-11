# Quick Facts — `mycroft-classic-listener`

Original Mycroft AI voice listener adapted for the OVOS plugin ecosystem.

| Feature | Details |
|---------|---------|
| Package Name | `mycroft-classic-listener` |
| Version | `0.1.1a6` |
| License | Apache-2.0 |
| Repository | https://github.com/OpenVoiceOS/mycroft-classic-listener |
| Python Support | >=3.10 |

## Entry Points

| Script | Module |
|---|---|
| `mycroft-classic-listener` | `mycroft_classic_listener.__main__:main` |

## Key Classes

| Class | File | Role |
|---|---|---|
| `ClassicListener` | `service.py:209` | Main service thread |
| `RecognizerLoop` | `listener.py:308` | Audio producer/consumer orchestrator |
| `ResponsiveRecognizer` | `mic.py:528` | Wake word detection + recording |
| `RollingMean` | `data_structures.py:19` | Sliding mean for energy tracking |
| `CyclicAudioBuffer` | `data_structures.py:64` | Ring buffer for audio frames |

## Primary Config Keys (under `listener`)

`wake_word`, `stand_up_word`, `sample_rate`, `recording_timeout`,
`recording_timeout_with_silence`, `save_utterances`, `record_wake_words`,
`mute_during_output`, `confirm_listening`
