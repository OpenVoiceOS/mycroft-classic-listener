"""
Unit tests for mycroft_classic_listener.data_structures.

Covers RollingMean and CyclicAudioBuffer — pure data structures with
no external dependencies; all tests are deterministic.
"""
import unittest

from mycroft_classic_listener.data_structures import CyclicAudioBuffer, RollingMean


# ---------------------------------------------------------------------------
# RollingMean
# ---------------------------------------------------------------------------

class TestRollingMeanInit(unittest.TestCase):
    def test_value_none_before_any_sample(self):
        rm = RollingMean(mean_samples=5)
        self.assertIsNone(rm.value)

    def test_num_samples_stored(self):
        rm = RollingMean(mean_samples=3)
        self.assertEqual(rm.num_samples, 3)


class TestRollingMeanBuildup(unittest.TestCase):
    """Phase 1: buffer filling (fewer samples than mean_samples)."""

    def test_single_sample_equals_value(self):
        rm = RollingMean(mean_samples=4)
        rm.append_sample(10.0)
        self.assertAlmostEqual(rm.value, 10.0)

    def test_two_samples_correct_mean(self):
        rm = RollingMean(mean_samples=4)
        rm.append_sample(10.0)
        rm.append_sample(20.0)
        self.assertAlmostEqual(rm.value, 15.0)

    def test_three_samples_correct_mean(self):
        rm = RollingMean(mean_samples=4)
        for v in [10.0, 20.0, 30.0]:
            rm.append_sample(v)
        self.assertAlmostEqual(rm.value, 20.0)


class TestRollingMeanSliding(unittest.TestCase):
    """Phase 2: sliding window (more samples than mean_samples)."""

    def test_rolls_out_oldest_sample(self):
        """With window=2, adding [10, 20, 30] → mean of [20, 30] = 25."""
        rm = RollingMean(mean_samples=2)
        rm.append_sample(10.0)
        rm.append_sample(20.0)
        rm.append_sample(30.0)
        self.assertAlmostEqual(rm.value, 25.0)

    def test_rolling_window_of_one(self):
        """Window=1 always returns the latest sample."""
        rm = RollingMean(mean_samples=1)
        for v in [5.0, 15.0, 99.0]:
            rm.append_sample(v)
        self.assertAlmostEqual(rm.value, 99.0)

    def test_constant_series_stays_constant(self):
        rm = RollingMean(mean_samples=3)
        for _ in range(10):
            rm.append_sample(42.0)
        self.assertAlmostEqual(rm.value, 42.0)

    def test_integer_samples_accepted(self):
        rm = RollingMean(mean_samples=2)
        rm.append_sample(4)
        rm.append_sample(6)
        self.assertAlmostEqual(rm.value, 5.0)

    def test_replace_pos_wraps(self):
        """replace_pos should cycle through the window correctly."""
        rm = RollingMean(mean_samples=3)
        for v in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]:
            rm.append_sample(v)
        # Last 3 values: 4, 5, 6 → mean = 5
        self.assertAlmostEqual(rm.value, 5.0)


# ---------------------------------------------------------------------------
# CyclicAudioBuffer
# ---------------------------------------------------------------------------

class TestCyclicAudioBufferInit(unittest.TestCase):
    def test_initial_data_truncated_to_size(self):
        data = b"\x01" * 20
        buf = CyclicAudioBuffer(size=10, initial_data=data)
        self.assertEqual(len(buf), 10)
        self.assertEqual(buf.get(), data[-10:])

    def test_initial_data_shorter_than_size_kept_as_is(self):
        data = b"\xab\xcd"
        buf = CyclicAudioBuffer(size=10, initial_data=data)
        self.assertEqual(buf.get(), data)

    def test_empty_initial_data(self):
        buf = CyclicAudioBuffer(size=5, initial_data=b"")
        self.assertEqual(buf.get(), b"")
        self.assertEqual(len(buf), 0)


class TestCyclicAudioBufferAppend(unittest.TestCase):
    def test_append_within_capacity(self):
        buf = CyclicAudioBuffer(size=10, initial_data=b"")
        buf.append(b"\x01\x02\x03")
        self.assertEqual(buf.get(), b"\x01\x02\x03")

    def test_append_fills_to_capacity(self):
        buf = CyclicAudioBuffer(size=4, initial_data=b"")
        buf.append(b"\x01\x02\x03\x04")
        self.assertEqual(len(buf), 4)

    def test_append_overflows_drops_oldest(self):
        buf = CyclicAudioBuffer(size=4, initial_data=b"\x01\x02\x03\x04")
        buf.append(b"\x05\x06")
        self.assertEqual(buf.get(), b"\x03\x04\x05\x06")

    def test_append_larger_than_size_keeps_tail(self):
        buf = CyclicAudioBuffer(size=4, initial_data=b"")
        buf.append(b"\x01\x02\x03\x04\x05\x06\x07\x08")
        self.assertEqual(buf.get(), b"\x05\x06\x07\x08")

    def test_multiple_appends(self):
        buf = CyclicAudioBuffer(size=4, initial_data=b"")
        buf.append(b"\x01\x02")
        buf.append(b"\x03\x04")
        buf.append(b"\x05\x06")
        self.assertEqual(buf.get(), b"\x03\x04\x05\x06")


class TestCyclicAudioBufferGetLast(unittest.TestCase):
    def test_get_last_fewer_than_total(self):
        buf = CyclicAudioBuffer(size=10, initial_data=b"\x01\x02\x03\x04\x05")
        self.assertEqual(buf.get_last(2), b"\x04\x05")

    def test_get_last_equal_to_total(self):
        buf = CyclicAudioBuffer(size=10, initial_data=b"\x01\x02\x03")
        self.assertEqual(buf.get_last(3), b"\x01\x02\x03")

    def test_get_last_zero_returns_full_buffer(self):
        # get_last(0) uses [-0:] which is the full buffer — document actual behaviour
        buf = CyclicAudioBuffer(size=10, initial_data=b"\x01\x02\x03")
        self.assertEqual(buf.get_last(0), b"\x01\x02\x03")


class TestCyclicAudioBufferIndexing(unittest.TestCase):
    def test_getitem_slice(self):
        buf = CyclicAudioBuffer(size=10, initial_data=b"\x01\x02\x03\x04\x05")
        self.assertEqual(buf[1:3], b"\x02\x03")

    def test_getitem_single(self):
        buf = CyclicAudioBuffer(size=10, initial_data=b"\x0a\x0b\x0c")
        self.assertEqual(buf[0], 0x0a)

    def test_len(self):
        buf = CyclicAudioBuffer(size=10, initial_data=b"\xff" * 7)
        self.assertEqual(len(buf), 7)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

class TestVersion(unittest.TestCase):
    def test_version_importable(self):
        from mycroft_classic_listener.version import __version__
        self.assertIsInstance(__version__, str)
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+")
