# FAQ — `mycroft-classic-listener`

## What is `mycroft-classic-listener`?
The original Mycroft AI voice listener ported to the OVOS plugin ecosystem.
It implements the same `recognizer_loop:*` messagebus contract as the other
OVOS listeners (`ovos-dinkum-listener`, `ovos-simple-listener`).

## How is it different from ovos-dinkum-listener?
Classic-listener is the original Mycroft implementation using PyAudio directly.
It lacks audio transformers, VAD pre-wake, multiple wake-word support,
and the dinkum FSM. Choose it for maximum backward-compatibility with Mycroft.

## How do I install it?
```bash
pip install mycroft-classic-listener
```
Or for development:
```bash
uv pip install -e .
```

## How do I run it?
```bash
mycroft-classic-listener
```
The service connects to the OVOS messagebus and begins listening.

## Where do I report bugs?
Open an issue on GitHub targeting the `dev` branch.

## How do I run tests?
```bash
uv run pytest test/ --cov=mycroft_classic_listener
```

## What Python versions are supported?
Python 3.10+ (see `pyproject.toml`).

## Does it support multiple wake words?
No. Classic-listener supports one wake word and one stand-up word.
Use `ovos-dinkum-listener` for multiple wake words or hotwords.

## How do I configure the wake word?
Set `listener.wake_word` in `mycroft.conf`. The value must match a key in
the `hotwords` section.

## Why does it require PyAudio?
Classic-listener uses the PyAudio microphone implementation directly
(pre-plugin-manager era). Install PyAudio with:
```bash
sudo apt install portaudio19-dev && pip install PyAudio
```
