"""
Unit tests for mycroft_classic_listener.service module-level bus handler functions.

Each handler reads from (or writes to) the module globals `bus` and `loop`.
Tests patch those globals directly so no real bus or audio hardware is needed.
"""
import sys
import types
import unittest
from unittest.mock import MagicMock, patch, call

# Stub out pyaudio before any listener imports try to load it
_pyaudio_stub = types.ModuleType("pyaudio")
_pyaudio_stub.PyAudio = MagicMock
_pyaudio_stub.paInt16 = 8
sys.modules.setdefault("pyaudio", _pyaudio_stub)

from ovos_bus_client.message import Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bus():
    return MagicMock()


def _make_loop():
    lp = MagicMock()
    lp.is_muted.return_value = False
    return lp


# ---------------------------------------------------------------------------
# handle_record_begin / handle_record_end
# ---------------------------------------------------------------------------

class TestHandleRecordBegin(unittest.TestCase):
    def test_emits_record_begin(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        svc.handle_record_begin()
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "recognizer_loop:record_begin")

    def test_context_has_client_name(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        svc.handle_record_begin()
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.context.get("client_name"), "mycroft_listener")


class TestHandleRecordEnd(unittest.TestCase):
    def test_emits_record_end(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        svc.handle_record_end()
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "recognizer_loop:record_end")


# ---------------------------------------------------------------------------
# handle_no_internet / handle_awoken
# ---------------------------------------------------------------------------

class TestHandleNoInternet(unittest.TestCase):
    def test_emits_no_internet(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        svc.handle_no_internet()
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "enclosure.notify.no_internet")


class TestHandleAwoken(unittest.TestCase):
    def test_emits_mycroft_awoken(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        svc.handle_awoken()
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "mycroft.awoken")


# ---------------------------------------------------------------------------
# handle_wakeword
# ---------------------------------------------------------------------------

class TestHandleWakeword(unittest.TestCase):
    def test_forwards_wakeword_event(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterance": "hey mycroft"}
        svc.handle_wakeword(event)
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "recognizer_loop:wakeword")

    def test_passes_event_data(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterance": "hey mycroft"}
        svc.handle_wakeword(event)
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.data, event)


# ---------------------------------------------------------------------------
# handle_utterance
# ---------------------------------------------------------------------------

class TestHandleUtterance(unittest.TestCase):
    def test_emits_utterance_message(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterances": ["hello world"], "lang": "en-us"}
        svc.handle_utterance(event)
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "recognizer_loop:utterance")

    def test_context_destination_is_skills(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterances": ["test"]}
        svc.handle_utterance(event)
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.context.get("destination"), ["skills"])

    def test_ident_popped_into_context(self):
        """ident key is moved from event data into context."""
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterances": ["test"], "ident": "abc123"}
        svc.handle_utterance(event)
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.context.get("ident"), "abc123")
        self.assertNotIn("ident", msg.data)

    def test_no_ident_in_event(self):
        """Without ident in event, no ident in context."""
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterances": ["test"]}
        svc.handle_utterance(event)
        msg = bus.emit.call_args[0][0]
        self.assertNotIn("ident", msg.context)


# ---------------------------------------------------------------------------
# handle_unknown / handle_speak
# ---------------------------------------------------------------------------

class TestHandleUnknown(unittest.TestCase):
    def test_emits_speech_recognition_unknown(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        svc.handle_unknown()
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "mycroft.speech.recognition.unknown")


class TestHandleSpeak(unittest.TestCase):
    def test_emits_speak(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterance": "hello"}
        svc.handle_speak(event)
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.msg_type, "speak")

    def test_passes_event_data(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        svc.bus = bus
        event = {"utterance": "hello"}
        svc.handle_speak(event)
        msg = bus.emit.call_args[0][0]
        self.assertEqual(msg.data, event)


# ---------------------------------------------------------------------------
# handle_sleep / handle_wake_up
# ---------------------------------------------------------------------------

class TestHandleSleep(unittest.TestCase):
    def test_calls_loop_sleep(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        svc.handle_sleep(MagicMock())
        lp.sleep.assert_called_once()


class TestHandleWakeUp(unittest.TestCase):
    def test_calls_loop_awaken(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        svc.handle_wake_up(MagicMock())
        lp.awaken.assert_called_once()


# ---------------------------------------------------------------------------
# handle_mic_mute / handle_mic_unmute / handle_stop
# ---------------------------------------------------------------------------

class TestHandleMicMute(unittest.TestCase):
    def test_calls_loop_mute(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        svc.handle_mic_mute(MagicMock())
        lp.mute.assert_called_once()


class TestHandleMicUnmute(unittest.TestCase):
    def test_calls_loop_unmute(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        svc.handle_mic_unmute(MagicMock())
        lp.unmute.assert_called_once()


class TestHandleStop(unittest.TestCase):
    def test_calls_loop_force_unmute(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        svc.handle_stop(MagicMock())
        lp.force_unmute.assert_called_once()


# ---------------------------------------------------------------------------
# handle_mic_listen
# ---------------------------------------------------------------------------

class TestHandleMicListen(unittest.TestCase):
    def test_calls_trigger_listen(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        svc.handle_mic_listen(MagicMock())
        lp.responsive_recognizer.trigger_listen.assert_called_once()


# ---------------------------------------------------------------------------
# handle_mic_get_status
# ---------------------------------------------------------------------------

class TestHandleMicGetStatus(unittest.TestCase):
    def test_emits_response_with_muted_false(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        lp = _make_loop()
        lp.is_muted.return_value = False
        svc.bus = bus
        svc.loop = lp

        event = MagicMock()
        event.response.return_value = Message("response", {"muted": False})
        svc.handle_mic_get_status(event)

        event.response.assert_called_once_with({"muted": False})
        bus.emit.assert_called_once()

    def test_emits_response_with_muted_true(self):
        import mycroft_classic_listener.service as svc
        bus = _make_bus()
        lp = _make_loop()
        lp.is_muted.return_value = True
        svc.bus = bus
        svc.loop = lp

        event = MagicMock()
        event.response.return_value = Message("response", {"muted": True})
        svc.handle_mic_get_status(event)

        event.response.assert_called_once_with({"muted": True})


# ---------------------------------------------------------------------------
# handle_audio_start / handle_audio_end
# ---------------------------------------------------------------------------

class TestHandleAudioStart(unittest.TestCase):
    def test_mutes_when_mute_during_output_true(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        with patch("mycroft_classic_listener.service.config",
                   {"listener": {"mute_during_output": True}}):
            svc.handle_audio_start(MagicMock())
        lp.mute.assert_called_once()

    def test_no_mute_when_mute_during_output_false(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        with patch("mycroft_classic_listener.service.config",
                   {"listener": {"mute_during_output": False}}):
            svc.handle_audio_start(MagicMock())
        lp.mute.assert_not_called()


class TestHandleAudioEnd(unittest.TestCase):
    def test_unmutes_when_mute_during_output_true(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        with patch("mycroft_classic_listener.service.config",
                   {"listener": {"mute_during_output": True}}):
            svc.handle_audio_end(MagicMock())
        lp.unmute.assert_called_once()

    def test_no_unmute_when_mute_during_output_false(self):
        import mycroft_classic_listener.service as svc
        lp = _make_loop()
        svc.loop = lp
        with patch("mycroft_classic_listener.service.config",
                   {"listener": {"mute_during_output": False}}):
            svc.handle_audio_end(MagicMock())
        lp.unmute.assert_not_called()


# ---------------------------------------------------------------------------
# connect_loop_events / connect_bus_events
# ---------------------------------------------------------------------------

class TestConnectLoopEvents(unittest.TestCase):
    def test_registers_all_expected_events(self):
        import mycroft_classic_listener.service as svc
        lp = MagicMock()
        svc.connect_loop_events(lp)
        registered = {c[0][0] for c in lp.on.call_args_list}
        expected = {
            "recognizer_loop:utterance",
            "recognizer_loop:speech.recognition.unknown",
            "speak",
            "recognizer_loop:record_begin",
            "recognizer_loop:awoken",
            "recognizer_loop:wakeword",
            "recognizer_loop:record_end",
            "recognizer_loop:no_internet",
        }
        self.assertEqual(registered, expected)


class TestConnectBusEvents(unittest.TestCase):
    def test_registers_all_expected_bus_events(self):
        import mycroft_classic_listener.service as svc
        bus = MagicMock()
        svc.connect_bus_events(bus)
        registered = {c[0][0] for c in bus.on.call_args_list}
        expected = {
            "open",
            "recognizer_loop:sleep",
            "recognizer_loop:wake_up",
            "mycroft.mic.mute",
            "mycroft.mic.unmute",
            "mycroft.mic.get_status",
            "mycroft.mic.listen",
            "recognizer_loop:audio_output_start",
            "recognizer_loop:audio_output_end",
            "mycroft.stop",
        }
        self.assertEqual(registered, expected)


if __name__ == "__main__":
    unittest.main()
