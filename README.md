# mycroft-classic-listener

The classic mycroft-core listener updated to use OVOS packages.

This does not support instant_listen, multiple hotwords, VAD, listening modes or Fallback STT

fallback hotwords are supported via OPM

# Configuration

under mycroft.conf

```javascript
{

  // Speech to Text parameters
  // Override: REMOTE
  "stt": {
    // select a STT plugin as described in the respective readme
    "module": "ovos-stt-plugin-server",
    // the default instance is hosted by a OpenVoiceOS member
    // it is a google proxy equivalent to mycroft selene
    "ovos-stt-plugin-server": {"url": "https://stt.openvoiceos.com/stt"}
  },
  
  // Hotword configurations
  "hotwords": {
    "hey_mycroft": {
        "module": "ovos-ww-plugin-precise-lite",
        "model": "https://github.com/OpenVoiceOS/precise-lite-models/raw/master/wakewords/en/hey_mycroft.tflite",
        "expected_duration": 3,
        "trigger_level": 3,
        "sensitivity": 0.5,
        "fallback_ww": "hey_mycroft_precise"
    },
    "hey_mycroft_precise": {
        "module": "ovos-ww-plugin-precise",
        "version": "0.3",
        "model": "https://github.com/MycroftAI/precise-data/raw/models-dev/hey-mycroft.tar.gz",
        "expected_duration": 3,
        "trigger_level": 3,
        "sensitivity": 0.5,
        "fallback_ww": "hey_mycroft_vosk"
    },
    "hey_mycroft_vosk": {
        "module": "ovos-ww-plugin-vosk",
        "samples": ["hey mycroft", "hey microsoft", "hey mike roft", "hey minecraft"],
        "rule": "fuzzy",
        "fallback_ww": "hey_mycroft_pocketsphinx"
    },
    "hey_mycroft_pocketsphinx": {
        "module": "ovos-ww-plugin-pocketsphinx",
        "phonemes": "HH EY . M AY K R AO F T",
        "threshold": 1e-90,
        "lang": "en-us"
    },
    "wake_up": {
        "module": "ovos-ww-plugin-pocketsphinx",
        "phonemes": "W EY K . AH P",
        "threshold": 1e-20,
        "lang": "en-us"
    }
  },
  
  // Settings used by the wake-up-word listener
  // Override: REMOTE
  "listener": {
    "sample_rate": 16000,

    // if enabled the noise level is saved to a ipc file, useful for
    // debuging if microphone is working but writes a lot to disk,
    // recommended that you set "ipc_path" to a tmpfs
    "mic_meter_ipc": true,

    // Set 'save_path' to configure the location of files stored if
    // 'record_wake_words' and/or 'save_utterances' are set to 'true'.
    // WARNING: Make sure that user 'mycroft' has write-access on the
    // directory!
    // "save_path": "/tmp",
    // Set 'record_wake_words' to save a copy of wake word triggers
    // as .wav files under: /'save_path'/mycroft_wake_words
    "record_wake_words": false,
    
    // Set 'save_utterances' to save each sentence sent to STT -- by default
    // they are only kept briefly in-memory.  This can be useful for for
    // debugging or other custom purposes.  Recordings are saved
    // under: /'save_path'/mycroft_utterances/<TIMESTAMP>.wav
    "save_utterances": false,
    "wake_word_upload": {
      "disable": true,
      // official mycroft endpoint disabled, enable if you want to collect your own
      // eg, eltocino localcroft or personal backend
      "url": ""
    },

    // Override as SYSTEM or USER to select a specific microphone input instead of
    // the PortAudio default input.
    //   "device_name": "somename",  // can be regex pattern or substring
    //       or
    //   "device_index": 12,

    // Retry microphone initialization infinitely on startup
    "retry_mic_init" : true,

    // Stop listing to the microphone during playback to prevent accidental triggering
    // This is enabled by default, but instances with good microphone noise cancellation
    // can disable this to listen all the time, allowing 'barge in' functionality.
    "mute_during_output" : true,

    // How much (if at all) to 'duck' the speaker output during listening.  A
    // setting of 0.0 will not duck at all.  A 1.0 will completely mute output
    // while in a listening state.  Values in between will lower the volume
    // partially (this is optional behavior, depending on the enclosure).
    "duck_while_listening" : 0.3,

    // In milliseconds
    "phoneme_duration": 120,
    "multiplier": 1.0,
    "energy_ratio": 1.5,

    // NOTE, multiple hotwords are supported now, these fields define the main wake_word,
    // this is equivalent to setting "active": true in the "hotwords" section below IF "active" is missing
    // this field is also used to get a speakable string of main wake word, ie, mycrofts name
    // this is set by selene and used in naptime skill
    "wake_word": "hey_mycroft",
    "stand_up_word": "wake_up",

    // Settings used by microphone to set recording timeout
    "recording_timeout": 10.0,
    "recording_timeout_with_silence": 3.0
  }
}
```
