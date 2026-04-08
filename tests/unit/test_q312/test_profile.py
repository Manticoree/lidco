"""Tests for Q312 Task 1672 — LoadProfile."""

from __future__ import annotations

import unittest

from lidco.loadtest.profile import (
    LoadProfile,
    ProfileType,
    RequestMethod,
    RequestPattern,
    create_ramp_profile,
    create_spike_profile,
    create_soak_profile,
    create_steady_profile,
)


class TestRequestPattern(unittest.TestCase):
    def test_defaults(self):
        rp = RequestPattern(url="http://example.com")
        self.assertEqual(rp.method, RequestMethod.GET)
        self.assertEqual(rp.weight, 1.0)
        self.assertIsNone(rp.body)
        self.assertEqual(rp.headers, {})

    def test_validate_empty_url(self):
        rp = RequestPattern(url="")
        errors = rp.validate()
        self.assertTrue(any("url" in e for e in errors))

    def test_validate_negative_weight(self):
        rp = RequestPattern(url="http://x", weight=-1)
        errors = rp.validate()
        self.assertTrue(any("weight" in e for e in errors))

    def test_valid_pattern(self):
        rp = RequestPattern(url="http://x", method=RequestMethod.POST, body='{"a":1}')
        self.assertEqual(rp.validate(), [])


class TestLoadProfile(unittest.TestCase):
    def _make(self, **kw):
        defaults = dict(
            name="test",
            requests=[RequestPattern(url="http://x")],
        )
        defaults.update(kw)
        return LoadProfile(**defaults)

    def test_defaults(self):
        lp = self._make()
        self.assertEqual(lp.profile_type, ProfileType.STEADY)
        self.assertEqual(lp.duration_seconds, 60)
        self.assertEqual(lp.max_users, 10)

    def test_validate_ok(self):
        lp = self._make()
        self.assertEqual(lp.validate(), [])

    def test_validate_empty_name(self):
        lp = self._make(name="")
        errors = lp.validate()
        self.assertTrue(any("name" in e for e in errors))

    def test_validate_no_requests(self):
        lp = LoadProfile(name="t", requests=[])
        errors = lp.validate()
        self.assertTrue(any("request" in e for e in errors))

    def test_validate_spike_no_spike_users(self):
        lp = self._make(profile_type=ProfileType.SPIKE, spike_users=0)
        errors = lp.validate()
        self.assertTrue(any("spike_users" in e for e in errors))

    def test_validate_negative_duration(self):
        lp = self._make(duration_seconds=-1)
        errors = lp.validate()
        self.assertTrue(any("duration" in e for e in errors))

    def test_validate_nested_request_error(self):
        lp = self._make(requests=[RequestPattern(url="")])
        errors = lp.validate()
        self.assertTrue(any("requests[0]" in e for e in errors))

    # --- users_at ---

    def test_users_at_steady(self):
        lp = self._make(max_users=20)
        self.assertEqual(lp.users_at(0), 20)
        self.assertEqual(lp.users_at(30), 20)
        self.assertEqual(lp.users_at(60), 20)

    def test_users_at_out_of_range(self):
        lp = self._make()
        self.assertEqual(lp.users_at(-1), 0)
        self.assertEqual(lp.users_at(61), 0)

    def test_users_at_ramp_up(self):
        lp = self._make(
            profile_type=ProfileType.RAMP_UP,
            max_users=100,
            ramp_up_seconds=50,
            duration_seconds=100,
        )
        self.assertLessEqual(lp.users_at(0), 2)
        self.assertGreater(lp.users_at(25), 0)
        self.assertEqual(lp.users_at(50), 100)
        self.assertEqual(lp.users_at(80), 100)

    def test_users_at_ramp_up_zero_ramp(self):
        lp = self._make(
            profile_type=ProfileType.RAMP_UP,
            max_users=50,
            ramp_up_seconds=0,
        )
        self.assertEqual(lp.users_at(10), 50)

    def test_users_at_spike(self):
        lp = self._make(
            profile_type=ProfileType.SPIKE,
            max_users=20,
            spike_users=80,
            ramp_up_seconds=5,
            ramp_down_seconds=10,
            duration_seconds=60,
        )
        # After ramp, should be max_users
        self.assertEqual(lp.users_at(10), 20)
        # During spike window
        self.assertEqual(lp.users_at(30), 100)  # 20 + 80

    def test_users_at_soak(self):
        lp = self._make(
            profile_type=ProfileType.SOAK,
            max_users=15,
            duration_seconds=3600,
        )
        self.assertEqual(lp.users_at(0), 15)
        self.assertEqual(lp.users_at(1800), 15)

    # --- helpers ---

    def test_total_weight(self):
        lp = self._make(requests=[
            RequestPattern(url="http://a", weight=2.0),
            RequestPattern(url="http://b", weight=3.0),
        ])
        self.assertAlmostEqual(lp.total_weight(), 5.0)

    def test_summary(self):
        lp = self._make(name="mytest", max_users=42)
        s = lp.summary()
        self.assertIn("mytest", s)
        self.assertIn("42", s)


class TestFactoryHelpers(unittest.TestCase):
    def test_create_steady(self):
        p = create_steady_profile("s", "http://x", users=5, duration=30)
        self.assertEqual(p.profile_type, ProfileType.STEADY)
        self.assertEqual(p.max_users, 5)
        self.assertEqual(p.duration_seconds, 30)
        self.assertEqual(len(p.requests), 1)
        self.assertEqual(p.validate(), [])

    def test_create_ramp(self):
        p = create_ramp_profile("r", "http://x", users=50, duration=120, ramp_up=30)
        self.assertEqual(p.profile_type, ProfileType.RAMP_UP)
        self.assertEqual(p.ramp_up_seconds, 30)
        self.assertEqual(p.validate(), [])

    def test_create_spike(self):
        p = create_spike_profile("sp", "http://x", users=20, spike_users=80)
        self.assertEqual(p.profile_type, ProfileType.SPIKE)
        self.assertEqual(p.spike_users, 80)
        self.assertEqual(p.validate(), [])

    def test_create_soak(self):
        p = create_soak_profile("sk", "http://x", users=10, duration=3600)
        self.assertEqual(p.profile_type, ProfileType.SOAK)
        self.assertEqual(p.duration_seconds, 3600)
        self.assertEqual(p.validate(), [])


if __name__ == "__main__":
    unittest.main()
