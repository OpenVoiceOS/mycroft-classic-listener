# Copyright 2017 Mycroft AI Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import audioop
import datetime
import os
from collections import deque, namedtuple
from hashlib import md5
from os.path import isdir, join
from tempfile import gettempdir
from threading import Lock
from time import sleep, time as get_time

import pyaudio
import requests
from ovos_bus_client.session import SessionManager
from ovos_config import Configuration
from ovos_utils.log import LOG
from ovos_utils.sound import play_audio
from ovos_plugin_manager.utils.audio import AudioData, AudioFile

from mycroft_classic_listener.data_structures import RollingMean, CyclicAudioBuffer

WakeWordData = namedtuple('WakeWordData',
                          ['audio', 'found', 'stopped', 'end_audio'])


class MutableStream:
    def __init__(self, wrapped_stream, format, muted=False):
        assert wrapped_stream is not None
        self.wrapped_stream = wrapped_stream

        self.SAMPLE_WIDTH = pyaudio.get_sample_size(format)
        self.muted_buffer = b''.join([b'\x00' * self.SAMPLE_WIDTH])
        self.read_lock = Lock()

        self.muted = muted
        if muted:
            self.mute()

    def mute(self):
        """Stop the stream and set the muted flag."""
        with self.read_lock:
            self.muted = True
            self.wrapped_stream.stop_stream()

    def unmute(self):
        """Start the stream and clear the muted flag."""
        with self.read_lock:
            self.muted = False
            self.wrapped_stream.start_stream()

    def read(self, size, of_exc=False):
        """Read data from stream.

        Args:
            size (int): Number of bytes to read
            of_exc (bool): flag determining if the audio producer thread
                           should throw IOError at overflows.

        Returns:
            (bytes) Data read from device
        """
        frames = deque()
        remaining = size
        with self.read_lock:
            while remaining > 0:
                # If muted during read return empty buffer. This ensures no
                # reads occur while the stream is stopped
                if self.muted:
                    return self.muted_buffer

                to_read = min(self.wrapped_stream.get_read_available(),
                              remaining)
                if to_read <= 0:
                    sleep(.01)
                    continue
                result = self.wrapped_stream.read(to_read,
                                                  exception_on_overflow=of_exc)
                frames.append(result)
                remaining -= to_read

        input_latency = self.wrapped_stream.get_input_latency()
        if input_latency > 0.2:
            LOG.warning("High input latency: %f" % input_latency)
        audio = b"".join(list(frames))
        return audio

    def close(self):
        self.wrapped_stream.close()
        self.wrapped_stream = None

    def is_stopped(self):
        try:
            return self.wrapped_stream.is_stopped()
        except Exception as e:
            LOG.error(repr(e))
            return True  # Assume the stream has been closed and thusly stopped

    def stop_stream(self):
        """
        Stop the underlying wrapped audio stream.
        
        Returns:
            The value returned by the wrapped stream's `stop_stream()` call (typically `None`).
        """
        return self.wrapped_stream.stop_stream()


# Microphone class extracted from https://github.com/Uberi/speech_recognition
class Microphone:
    """
    Creates a new ``Microphone`` instance, which represents a physical microphone on the computer. Subclass of ``AudioSource``.

    This will throw an ``AttributeError`` if you don't have PyAudio (0.2.11 or later) installed.

    If ``device_index`` is unspecified or ``None``, the default microphone is used as the audio source. Otherwise, ``device_index`` should be the index of the device to use for audio input.

    A device index is an integer between 0 and ``pyaudio.get_device_count() - 1`` (assume we have used ``import pyaudio`` beforehand) inclusive. It represents an audio device such as a microphone or speaker. See the `PyAudio documentation <http://people.csail.mit.edu/hubert/pyaudio/docs/>`__ for more details.

    The microphone audio is recorded in chunks of ``chunk_size`` samples, at a rate of ``sample_rate`` samples per second (Hertz). If not specified, the value of ``sample_rate`` is determined automatically from the system's microphone settings.

    Higher ``sample_rate`` values result in better audio quality, but also more bandwidth (and therefore, slower recognition). Additionally, some CPUs, such as those in older Raspberry Pi models, can't keep up if this value is too high.

    Higher ``chunk_size`` values help avoid triggering on rapidly changing ambient noise, but also makes detection less sensitive. This value, generally, should be left at its default.
    """
    def __init__(self, device_index=None, sample_rate=None, chunk_size=1024):
        """
        Initialize a Microphone instance, selecting the audio device and configuring sample parameters.
        
        Parameters:
            device_index (int | None): Index of the input device to use; if None, the default input device is used.
            sample_rate (int | None): Desired sampling rate in Hz; if None, the device's default sample rate is used.
            chunk_size (int): Number of audio frames per buffer (CHUNK).
        
        Raises:
            AssertionError: If arguments are invalid (wrong types or out of range) or if the selected device reports an invalid default sample rate.
        
        Side effects:
            Queries PyAudio for device information and sets instance attributes: pyaudio_module, device_index, format, SAMPLE_WIDTH, SAMPLE_RATE, CHUNK, audio, and stream.
        """
        assert device_index is None or isinstance(device_index, int), "Device index must be None or an integer"
        assert sample_rate is None or (isinstance(sample_rate, int) and sample_rate > 0), "Sample rate must be None or a positive integer"
        assert isinstance(chunk_size, int) and chunk_size > 0, "Chunk size must be a positive integer"

        # set up PyAudio
        self.pyaudio_module = self.get_pyaudio()
        audio = self.pyaudio_module.PyAudio()
        try:
            count = audio.get_device_count()  # obtain device count
            if device_index is not None:  # ensure device index is in range
                assert 0 <= device_index < count, "Device index out of range ({} devices available; device index should be between 0 and {} inclusive)".format(count, count - 1)
            if sample_rate is None:  # automatically set the sample rate to the hardware's default sample rate if not specified
                device_info = audio.get_device_info_by_index(device_index) if device_index is not None else audio.get_default_input_device_info()
                assert isinstance(device_info.get("defaultSampleRate"), (float, int)) and device_info["defaultSampleRate"] > 0, "Invalid device info returned from PyAudio: {}".format(device_info)
                sample_rate = int(device_info["defaultSampleRate"])
        finally:
            audio.terminate()

        self.device_index = device_index
        self.format = self.pyaudio_module.paInt16  # 16-bit int sampling
        self.SAMPLE_WIDTH = self.pyaudio_module.get_sample_size(self.format)  # size of each sample
        self.SAMPLE_RATE = sample_rate  # sampling rate in Hertz
        self.CHUNK = chunk_size  # number of frames stored in each buffer

        self.audio = None
        self.stream = None

    @staticmethod
    def get_pyaudio():
        """
        Import and return the PyAudio module, raising an error if it is not available.
        
        Returns:
            pyaudio: The imported PyAudio module.
        
        Raises:
            AttributeError: If the PyAudio package is not installed.
        """
        try:
            import pyaudio
        except ImportError:
            raise AttributeError("Could not find PyAudio; check installation")
        return pyaudio

    @staticmethod
    def list_microphone_names():
        """
        List the display names of all available audio input devices.
        
        Each entry corresponds to the device index used when creating a Microphone (e.g., the name at index 3 is for Microphone(device_index=3)). If a device's name cannot be retrieved, its entry will be `None`.
        
        Returns:
            list: A list of device names (strings) or `None` for devices with no retrievable name.
        """
        audio = Microphone.get_pyaudio().PyAudio()
        try:
            result = []
            for i in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(i)
                result.append(device_info.get("name"))
        finally:
            audio.terminate()
        return result

    @staticmethod
    def list_working_microphones():
        """
        Detects microphones that are currently producing audible input.
        
        Callers should ensure the microphone is unmuted and produce sound while this runs so active devices are detected.
        
        Returns:
            result (dict): Mapping of device index (int) to microphone name (str) for devices that appear to be receiving audio; empty if none detected.
        """
        pyaudio_module = Microphone.get_pyaudio()
        audio = pyaudio_module.PyAudio()
        try:
            result = {}
            for device_index in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(device_index)
                device_name = device_info.get("name")
                assert isinstance(device_info.get("defaultSampleRate"), (float, int)) and device_info["defaultSampleRate"] > 0, "Invalid device info returned from PyAudio: {}".format(device_info)
                try:
                    # read audio
                    pyaudio_stream = audio.open(
                        input_device_index=device_index, channels=1, format=pyaudio_module.paInt16,
                        rate=int(device_info["defaultSampleRate"]), input=True
                    )
                    try:
                        buffer = pyaudio_stream.read(1024)
                        if not pyaudio_stream.is_stopped(): pyaudio_stream.stop_stream()
                    finally:
                        pyaudio_stream.close()
                except Exception:
                    continue

                # compute RMS of debiased audio
                energy = -audioop.rms(buffer, 2)
                energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
                debiased_energy = audioop.rms(audioop.add(buffer, energy_bytes * (len(buffer) // 2), 2), 2)

                if debiased_energy > 30:  # probably actually audio
                    result[device_index] = device_name
        finally:
            audio.terminate()
        return result

    def __enter__(self):
        """
        Enter the microphone context and open the underlying PyAudio stream.
        
        If opening the stream succeeds, stores a MicrophoneStream in self.stream and the PyAudio
        instance in self.audio. If opening the stream raises an exception, the PyAudio instance
        is terminated and no stream is retained.
        
        Returns:
            self: The Microphone instance with an opened stream when successful.
        """
        assert self.stream is None, "This audio source is already inside a context manager"
        self.audio = self.pyaudio_module.PyAudio()
        try:
            self.stream = Microphone.MicrophoneStream(
                self.audio.open(
                    input_device_index=self.device_index, channels=1, format=self.format,
                    rate=self.SAMPLE_RATE, frames_per_buffer=self.CHUNK, input=True,
                )
            )
        except Exception:
            self.audio.terminate()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Close the microphone stream and terminate the PyAudio instance when exiting the context.
        
        Ensures the stream is closed and the stream reference is cleared even if closing raises an error; always calls audio.terminate(). Does not suppress exceptions from the surrounding context.
        """
        try:
            self.stream.close()
        finally:
            self.stream = None
            self.audio.terminate()

    class MicrophoneStream(object):
        def __init__(self, pyaudio_stream):
            """
            Initialize the MicrophoneStream wrapper.
            
            Parameters:
                pyaudio_stream: The active PyAudio stream object to wrap; expected to provide read(size, exception_on_overflow=False), stop_stream(), and close() methods.
            """
            self.pyaudio_stream = pyaudio_stream

        def read(self, size):
            """
            Read up to `size` frames of audio from the underlying PyAudio stream without raising on buffer overflow.
            
            Parameters:
                size (int): Number of frames to read from the stream.
            
            Returns:
                bytes: Raw audio bytes for the frames read.
            """
            return self.pyaudio_stream.read(size, exception_on_overflow=False)

        def close(self):
            """
            Stop and close the underlying PyAudio stream.
            
            If the stream is not already stopped, attempts to stop it before closing the stream to release resources.
            """
            try:
                # sometimes, if the stream isn't stopped, closing the stream throws an exception
                if not self.pyaudio_stream.is_stopped():
                    self.pyaudio_stream.stop_stream()
            finally:
                self.pyaudio_stream.close()


class MutableMicrophone(Microphone):
    def __init__(self, device_index=None, sample_rate=16000, chunk_size=1024,
                 mute=False):
        """
        Initialize a MutableMicrophone configured for a specific input device and audio parameters, and set its initial mute state.
        
        Parameters:
            device_index (int or None): Index of the audio input device to use, or None to auto-select the default.
            sample_rate (int): Sampling rate in Hz for audio capture.
            chunk_size (int): Number of frames per read from the audio stream.
            mute (bool): If True, start the microphone muted; otherwise start unmuted.
        """
        Microphone.__init__(self, device_index=device_index, sample_rate=sample_rate, chunk_size=chunk_size)
        self.muted = False
        if mute:
            self.mute()

    def __enter__(self):
        return self._start()

    def _start(self):
        """Open the selected device and setup the stream."""
        assert self.stream is None, \
            "This audio source is already inside a context manager"
        self.audio = pyaudio.PyAudio()
        self.stream = MutableStream(self.audio.open(
            input_device_index=self.device_index, channels=1,
            format=self.format, rate=self.SAMPLE_RATE,
            frames_per_buffer=self.CHUNK,
            input=True,  # stream is an input stream
        ), self.format, self.muted)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return self._stop()

    def _stop(self):
        """Stop and close an open stream."""
        try:
            if not self.stream.is_stopped():
                self.stream.stop_stream()
            self.stream.close()
        except Exception:
            LOG.exception('Failed to stop mic input stream')
            # Let's pretend nothing is wrong...

        self.stream = None
        self.audio.terminate()

    def restart(self):
        """Shutdown input device and restart."""
        self._stop()
        self._start()

    def mute(self):
        self.muted = True
        if self.stream:
            self.stream.mute()

    def unmute(self):
        self.muted = False
        if self.stream:
            self.stream.unmute()

    def is_muted(self):
        return self.muted

    def duration_to_bytes(self, sec):
        """Converts a duration in seconds to number of recorded bytes.

        Args:
            sec: number of seconds

        Returns:
            (int) equivalent number of bytes recorded by this Mic
        """
        return int(sec * self.SAMPLE_RATE) * self.SAMPLE_WIDTH


def get_silence(num_bytes):
    return b'\0' * num_bytes


class NoiseTracker:
    """Noise tracker, used to deterimine if an audio utterance is complete.

    The current implementation expects a number of loud chunks (not necessary
    in one continous sequence) followed by a short period of continous quiet
    audio data to be considered complete.

    Args:
        minimum (int): lower noise level will be threshold for "quiet" level
        maximum (int): ceiling of noise level
        sec_per_buffer (float): the length of each buffer used when updating
                                the tracker
        loud_time_limit (float): time in seconds of low noise to be considered
                                 a complete sentence
        silence_time_limit (float): time limit for silence to abort sentence
        silence_after_loud (float): time of silence to finalize the sentence.
                                    default 0.25 seconds.
    """

    def __init__(self, minimum, maximum, sec_per_buffer, loud_time_limit,
                 silence_time_limit, silence_after_loud_time=0.25):
        self.min_level = minimum
        self.max_level = maximum
        self.sec_per_buffer = sec_per_buffer

        self.num_loud_chunks = 0
        self.level = 0

        # Smallest number of loud chunks required to return loud enough
        self.min_loud_chunks = int(loud_time_limit / sec_per_buffer)

        self.max_silence_duration = silence_time_limit
        self.silence_duration = 0

        # time of quite period after long enough loud data to consider the
        # sentence complete
        self.silence_after_loud = silence_after_loud_time

        # Constants
        self.increase_multiplier = 200
        self.decrease_multiplier = 100

    def _increase_noise(self):
        """Bumps the current level.

        Modifies the noise level with a factor depending in the buffer length.
        """
        if self.level < self.max_level:
            self.level += self.increase_multiplier * self.sec_per_buffer

    def _decrease_noise(self):
        """Decrease the current level.

        Modifies the noise level with a factor depending in the buffer length.
        """
        if self.level > self.min_level:
            self.level -= self.decrease_multiplier * self.sec_per_buffer

    def update(self, is_loud):
        """Update the tracking. with either a loud chunk or a quiet chunk.

        Args:
            is_loud: True if a loud chunk should be registered
                     False if a quiet chunk should be registered
        """
        if is_loud:
            self._increase_noise()
            self.num_loud_chunks += 1
        else:
            self._decrease_noise()
        # Update duration of energy under the threshold level
        if self._quiet_enough():
            self.silence_duration += self.sec_per_buffer
        else:  # Reset silence duration
            self.silence_duration = 0

    def _loud_enough(self):
        """Check if the noise loudness criteria is fulfilled.

        The noise is considered loud enough if it's been over the threshold
        for a certain number of chunks (accumulated, not in a row).
        """
        return self.num_loud_chunks > self.min_loud_chunks

    def _quiet_enough(self):
        """Check if the noise quietness criteria is fulfilled.

        The quiet level is instant and will return True if the level is lower
        or equal to the minimum noise level.
        """
        return self.level <= self.min_level

    def recording_complete(self):
        """
        Determine whether the current recording should be considered complete.
        
        The recording is considered complete when the noise level is at or below
        the quiet threshold for longer than `silence_after_loud` and either
        enough loud chunks have been observed to qualify as a phrase or the
        recording has exceeded `max_silence_duration`.
        
        Returns:
            bool: `True` if the recording end criteria are met, `False` otherwise.
        """
        too_much_silence = (self.silence_duration > self.max_silence_duration)
        if too_much_silence:
            LOG.debug('Too much silence recorded without start of sentence '
                      'detected')
        return ((self._quiet_enough() and
                 self.silence_duration > self.silence_after_loud) and
                (self._loud_enough() or too_much_silence))


class ResponsiveRecognizer:
    # Padding of silence when feeding to pocketsphinx
    SILENCE_SEC = 0.01

    # The minimum seconds of noise before a
    # phrase can be considered complete
    MIN_LOUD_SEC_PER_PHRASE = 0.5

    # The minimum seconds of silence required at the end
    # before a phrase will be considered complete
    MIN_SILENCE_AT_END = 0.25

    # Time between pocketsphinx checks for the wake word
    SEC_BETWEEN_WW_CHECKS = 0.2

    def __init__(self, wake_word_recognizer, watchdog=None):
        """
        Initialize the ResponsiveRecognizer with the given wake-word recognizer and optional watchdog.
        
        Loads listener configuration, initializes audio and dynamic energy thresholding parameters, recording timeouts, and directories for saving captured wake words and utterances (if enabled). Also stores flags and internal state used to control listening and recording behaviour.
        
        Parameters:
            wake_word_recognizer: An object responsible for detecting wake words; must expose `key_phrase` and provide the detection interface used by this class.
            watchdog (callable, optional): A callable invoked periodically for liveness monitoring; defaults to a no-op if not provided.
        """
        self._watchdog = watchdog or (lambda: None)  # Default to dummy func
        self.config = Configuration()
        listener_config = self.config.get('listener')
        self.upload_url = listener_config['wake_word_upload']['url']
        self.upload_disabled = listener_config['wake_word_upload']['disable']
        self.wake_word_name = wake_word_recognizer.key_phrase

        self.overflow_exc = listener_config.get('overflow_exception', False)

        self.energy_threshold = 300  # minimum audio energy to consider for recording
        self.dynamic_energy_threshold = True
        self.dynamic_energy_adjustment_damping = 0.15
        self.dynamic_energy_ratio = 1.5
        self.pause_threshold = 0.8  # seconds of non-speaking audio before a phrase is considered complete
        self.operation_timeout = None  # seconds after an internal operation (e.g., an API request) starts before it times out, or ``None`` for no timeout

        self.phrase_threshold = 0.3  # minimum seconds of speaking audio before we consider the speaking audio a phrase - values below this are ignored (for filtering out clicks and pops)
        self.non_speaking_duration = 0.5  # seconds of non-speaking audio to keep on both sides of the recording

        self.wake_word_recognizer = wake_word_recognizer
        self.audio = pyaudio.PyAudio()
        self.multiplier = listener_config.get('multiplier')
        self.energy_ratio = listener_config.get('energy_ratio')

        # Check the config for the flag to save wake words, utterances
        # and for a path under which to save them
        self.save_utterances = listener_config.get('save_utterances', False)
        self.save_wake_words = listener_config.get('record_wake_words', False)
        self.save_path = listener_config.get('save_path', gettempdir())
        self.saved_wake_words_dir = join(self.save_path, 'mycroft_wake_words')
        if self.save_wake_words and not isdir(self.saved_wake_words_dir):
            os.mkdir(self.saved_wake_words_dir)
        self.saved_utterances_dir = join(self.save_path, 'mycroft_utterances')
        if self.save_utterances and not isdir(self.saved_utterances_dir):
            os.mkdir(self.saved_utterances_dir)

        # Signal statuses
        self._stop_signaled = False
        self._listen_triggered = False

        self.account_id = "0"

        # The maximum seconds a phrase can be recorded,
        # provided there is noise the entire time
        self.recording_timeout = listener_config.get('recording_timeout',
                                                     10.0)

        # The maximum time it will continue to record silence
        # when not enough noise has been detected
        self.recording_timeout_with_silence = listener_config.get(
            'recording_timeout_with_silence', 3.0)

    # extracted from https://github.com/Uberi/speech_recognition
    def adjust_for_ambient_noise(self, source: Microphone, duration: float = 1) -> None:
        """
        Calibrates the recognizer's energy threshold from ambient noise captured by a Microphone.
        
        Reads audio chunks from the provided Microphone (which must be entered and have an active stream) for up to `duration` seconds and updates `self.energy_threshold` using a damping-weighted average of measured RMS energy scaled by `self.dynamic_energy_ratio`. Intended to tune sensitivity to current background noise; callers should ensure the sampled period does not contain speech.
        
        Parameters:
            source (Microphone): An entered Microphone instance with an active stream.
            duration (float): Maximum number of seconds to sample ambient audio (should be >= 0.5 for representative calibration).
        """
        assert isinstance(source, Microphone), "Source must be an audio source"
        assert source.stream is not None, "Audio source must be entered before adjusting, see documentation for ``AudioSource``; are you using ``source`` outside of a ``with`` statement?"  # type: ignore[attr-defined]
        assert self.pause_threshold >= self.non_speaking_duration >= 0

        seconds_per_buffer = (source.CHUNK + 0.0) / source.SAMPLE_RATE  # type: ignore[attr-defined]
        elapsed_time = 0

        # adjust energy threshold until a phrase starts
        while True:
            elapsed_time += seconds_per_buffer
            if elapsed_time > duration: break
            buffer = source.stream.read(source.CHUNK)  # type: ignore[attr-defined]
            energy = audioop.rms(buffer, source.SAMPLE_WIDTH)  # type: ignore[attr-defined]  # energy of the audio signal

            # dynamically adjust the energy threshold using asymmetric weighted average
            damping = self.dynamic_energy_adjustment_damping ** seconds_per_buffer  # account for different chunk sizes and rates
            target_energy = energy * self.dynamic_energy_ratio
            self.energy_threshold = self.energy_threshold * damping + target_energy * (1 - damping)

    def record_sound_chunk(self, source):
        """
        Read a single audio chunk from the microphone stream.
        
        Parameters:
            source (Microphone): An active Microphone instance with an open stream.
        
        Returns:
            bytes: Raw audio bytes for one chunk (size = source.CHUNK * sample width).
        """
        return source.stream.read(source.CHUNK, self.overflow_exc)

    @staticmethod
    def calc_energy(sound_chunk, sample_width):
        return audioop.rms(sound_chunk, sample_width)

    def _record_phrase(
            self,
            source,
            sec_per_buffer,
            stream=None,
            ww_frames=None
    ):
        """
        Record audio for a single spoken phrase until end-of-utterance silence or a timeout.
        
        Parameters:
            source (Microphone): Active microphone providing audio chunks (must have SAMPLE_WIDTH).
            sec_per_buffer (float): Duration in seconds of each audio chunk read from the source.
            stream (optional): Target with stream_start() and stream_chunk(bytes) to receive chunks as they are recorded.
            ww_frames (optional deque): Pre-filled frames from wake-word detection to prepend to the recording.
        
        Returns:
            bytearray: Recorded audio bytes for the phrase, including any trailing silence.
        """
        noise_tracker = NoiseTracker(0, 25, sec_per_buffer,
                                     self.MIN_LOUD_SEC_PER_PHRASE,
                                     self.recording_timeout_with_silence)

        # Maximum number of chunks to record before timing out
        max_chunks = int(self.recording_timeout / sec_per_buffer)
        num_chunks = 0

        # bytearray to store audio in, initialized with a single sample of
        # silence.
        byte_data = get_silence(source.SAMPLE_WIDTH)

        if stream:
            stream.stream_start()

        phrase_complete = False
        while num_chunks < max_chunks and not phrase_complete:
            if ww_frames:
                chunk = ww_frames.popleft()
            else:
                chunk = self.record_sound_chunk(source)
            byte_data += chunk
            num_chunks += 1

            if stream:
                stream.stream_chunk(chunk)

            energy = self.calc_energy(chunk, source.SAMPLE_WIDTH)
            test_threshold = self.energy_threshold * self.multiplier
            is_loud = energy > test_threshold
            noise_tracker.update(is_loud)
            if not is_loud:
                self._adjust_threshold(energy, sec_per_buffer)

            # The phrase is complete if the noise_tracker end of sentence
            # criteria is met or if the  top-button is pressed
            phrase_complete = noise_tracker.recording_complete()

            # Periodically write the energy level to the mic level file.
            if num_chunks % 10 == 0:
                self._watchdog()

        return byte_data


    def _skip_wake_word(self):
        """Check if told programatically to skip the wake word

        For example when we are in a dialog with the user.
        """
        if self._listen_triggered:
            return True
        return False

    def stop(self):
        """Signal stop and exit waiting state."""
        self._stop_signaled = True

    def _compile_metadata(self):
        ww_module = self.wake_word_recognizer.__class__.__name__
        if ww_module == 'PreciseHotword':
            model_path = self.wake_word_recognizer.precise_model
            with open(model_path, 'rb') as f:
                model_hash = md5(f.read()).hexdigest()
        else:
            model_hash = '0'

        return {
            'name': self.wake_word_name.replace(' ', '-'),
            'engine': md5(ww_module.encode('utf-8')).hexdigest(),
            'time': str(int(1000 * get_time())),
            'sessionId': SessionManager.get().session_id,
            'accountId': self.account_id,
            'model': str(model_hash)
        }

    def trigger_listen(self):
        """Externally trigger listening."""
        LOG.debug('Listen triggered from external source.')
        self._listen_triggered = True

    def _upload_wakeword(self, audio, metadata):
        """Upload the wakeword in a background thread."""
        LOG.debug(
            "Wakeword uploading has been disabled. The API endpoint used in "
            "Mycroft-core v20.2 and below has been deprecated. To contribute "
            "new wakeword samples please upgrade to v20.8 or above."
        )
        # def upload(audio, metadata):
        #     requests.post(self.upload_url,
        #                   files={'audio': BytesIO(audio.get_wav_data()),
        #                          'metadata': StringIO(json.dumps(metadata))})
        # Thread(target=upload, daemon=True, args=(audio, metadata)).start()

    def _send_wakeword_info(self, emitter):
        """Send messagebus message indicating that a wakeword was received.

        Args:
            emitter: bus emitter to send information on.
        """
        SessionManager.touch()
        payload = {'utterance': self.wake_word_name,
                   'session': SessionManager.get().session_id}
        emitter.emit("recognizer_loop:wakeword", payload)

    def _write_wakeword_to_disk(self, audio, metadata):
        """Write wakeword to disk.

        Args:
            audio: Audio data to write
            metadata: List of metadata about the captured wakeword
        """
        filename = join(self.saved_wake_words_dir,
                        '_'.join(str(metadata[k]) for k in sorted(metadata)) +
                        '.wav')
        with open(filename, 'wb') as f:
            f.write(audio.get_wav_data())

    def _handle_wakeword_found(self, audio_data, source):
        """Perform actions to be triggered after a wakeword is found.

        This includes: emit event on messagebus that a wakeword is heard,
        store wakeword to disk if configured and sending the wakeword data
        to the cloud in case the user has opted into the data sharing.
        """
        # Save and upload positive wake words as appropriate
        upload_allowed = (self.config['opt_in'] and not self.upload_disabled)
        if (self.save_wake_words or upload_allowed):
            audio = self._create_audio_data(audio_data, source)
            metadata = self._compile_metadata()
            if self.save_wake_words:
                # Save wake word locally
                self._write_wakeword_to_disk(audio, metadata)
            # Upload wake word for opt_in people
            if upload_allowed:
                self._upload_wakeword(audio, metadata)

    def _wait_until_wake_word(self, source, sec_per_buffer):
        """
        Listen to the given Microphone until a wake word is detected or listening is stopped.
        
        Args:
            source (Microphone): Audio source providing chunks and metadata (sample rate/width).
            sec_per_buffer (float): Duration in seconds of each audio chunk.
        
        Returns:
            WakeWordData: Named tuple with fields:
                - audio: bytes of the audio immediately preceding detection (plus trailing silence) suitable for STT.
                - found: `True` if a wake word was detected, `False` otherwise.
                - stopped: `True` if listening was interrupted via stop signal, `False` otherwise.
                - end_audio: deque of the raw frames captured immediately after detection (may be empty).
        """

        # The maximum audio in seconds to keep for transcribing a phrase
        # The wake word must fit in this time
        ww_duration = ww_test_duration = 3

        mic_write_counter = 0
        num_silent_bytes = int(self.SILENCE_SEC * source.SAMPLE_RATE *
                               source.SAMPLE_WIDTH)

        silence = get_silence(num_silent_bytes)

        # Max bytes for byte_data before audio is removed from the front
        max_size = source.duration_to_bytes(ww_duration)
        test_size = source.duration_to_bytes(ww_test_duration)
        audio_buffer = CyclicAudioBuffer(max_size, silence)

        buffers_per_check = self.SEC_BETWEEN_WW_CHECKS / sec_per_buffer
        buffers_since_check = 0.0

        # Rolling buffer to track the audio energy (loudness) heard on
        # the source recently.  An average audio energy is maintained
        # based on these levels.
        average_samples = int(5 / sec_per_buffer)  # average over last 5 secs
        audio_mean = RollingMean(average_samples)

        # These are frames immediately after wake word is detected
        # that we want to keep to send to STT
        ww_frames = deque(maxlen=7)

        said_wake_word = False
        audio_data = None
        while (not said_wake_word and not self._stop_signaled and
               not self._skip_wake_word()):
            chunk = self.record_sound_chunk(source)
            audio_buffer.append(chunk)
            ww_frames.append(chunk)

            energy = self.calc_energy(chunk, source.SAMPLE_WIDTH)
            audio_mean.append_sample(energy)

            if energy < self.energy_threshold * self.multiplier:
                self._adjust_threshold(energy, sec_per_buffer)
            # maintain the threshold using average
            if self.energy_threshold < energy < audio_mean.value * 1.5:
                # bump the threshold to just above this value
                self.energy_threshold = energy * 1.2

            # Periodically output energy level stats. This can be used to
            # visualize the microphone input, e.g. a needle on a meter.
            if mic_write_counter % 3:
                self._watchdog()
            mic_write_counter += 1

            buffers_since_check += 1.0
            # Send chunk to wake_word_recognizer
            self.wake_word_recognizer.update(chunk)

            if buffers_since_check > buffers_per_check:
                buffers_since_check -= buffers_per_check
                audio_data = audio_buffer.get_last(test_size) + silence
                said_wake_word = self.wake_word_recognizer.found_wake_word()

        self._listen_triggered = False
        return WakeWordData(audio_data, said_wake_word,
                            self._stop_signaled, ww_frames)

    @staticmethod
    def _create_audio_data(raw_data, source):
        """
        Constructs an AudioData instance with the same parameters
        as the source and the specified frame_data
        """
        return AudioData(raw_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)

    def mute_and_confirm_listening(self, source):
        audio_file = f"{os.path.dirname(__file__)}/res/snd/start_listening.wav"
        if audio_file:
            source.mute()
            play_audio(audio_file).wait()
            source.unmute()
            return True
        else:
            return False

    def listen(self, source, emitter, stream=None):
        """
        Listen for a wake word and record the user's utterance that immediately follows.
        
        Waits for a wake word from the provided Microphone source, emits start/stop events via the emitter, optionally plays a confirmation sound, records the following phrase (excluding the wake word), and may save the utterance to disk depending on configuration.
        
        Parameters:
            source (Microphone): Microphone producing audio chunks; must be entered/active.
            emitter (EventEmitter): Event emitter used to signal "recognizer_loop:record_begin" and "recognizer_loop:record_end".
            stream (AudioStreamHandler): Optional stream target that will receive utterance chunks while recording.
        
        Returns:
            AudioData: Recorded audio containing the user's utterance, excluding the wake word.
        """
        assert isinstance(source, Microphone), "Source must be a Microphone"

        #        bytes_per_sec = source.SAMPLE_RATE * source.SAMPLE_WIDTH
        sec_per_buffer = float(source.CHUNK) / source.SAMPLE_RATE

        # Every time a new 'listen()' request begins, reset the threshold
        # used for silence detection.  This is as good of a reset point as
        # any, as we expect the user and Mycroft to not be talking.
        # NOTE: adjust_for_ambient_noise() doc claims it will stop early if
        #       speech is detected, but there is no code to actually do that.
        self.adjust_for_ambient_noise(source, 1.0)

        LOG.debug("Waiting for wake word...")
        ww_data = self._wait_until_wake_word(source, sec_per_buffer)

        ww_frames = None
        if ww_data.found:
            # If the wakeword was heard send it
            self._send_wakeword_info(emitter)
            self._handle_wakeword_found(ww_data.audio, source)
            ww_frames = ww_data.end_audio
        if ww_data.stopped:
            # If the waiting returned from a stop signal
            return

        LOG.debug("Recording...")
        # If enabled, play a wave file with a short sound to audibly
        # indicate recording has begun.
        if self.config.get('confirm_listening'):
            if self.mute_and_confirm_listening(source):
                # Clear frames from wakeword detctions since they're
                # irrelevant after mute - play wav - unmute sequence
                ww_frames = None

        # Notify system of recording start
        emitter.emit("recognizer_loop:record_begin")

        frame_data = self._record_phrase(
            source,
            sec_per_buffer,
            stream,
            ww_frames
        )
        audio_data = self._create_audio_data(frame_data, source)
        emitter.emit("recognizer_loop:record_end")
        if self.save_utterances:
            LOG.info("Recording utterance")
            stamp = str(datetime.datetime.now())
            filename = "/{}/{}.wav".format(
                self.saved_utterances_dir,
                stamp
            )
            with open(filename, 'wb') as filea:
                filea.write(audio_data.get_wav_data())
            LOG.debug("Thinking...")

        return audio_data

    def _adjust_threshold(self, energy, seconds_per_buffer):
        if self.dynamic_energy_threshold and energy > 0:
            # account for different chunk sizes and rates
            damping = (
                    self.dynamic_energy_adjustment_damping ** seconds_per_buffer)
            target_energy = energy * self.energy_ratio
            self.energy_threshold = (
                    self.energy_threshold * damping +
                    target_energy * (1 - damping))
