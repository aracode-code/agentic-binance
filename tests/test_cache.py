import time
import unittest

from tools import cache


class CacheTest(unittest.TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_get_returns_none_when_missing(self):
        self.assertIsNone(cache.get("absent"))

    def test_get_or_fetch_calls_fetch_once(self):
        calls = []

        def fetch():
            calls.append(1)
            return {"value": 1}

        first = cache.get_or_fetch("k", 60, fetch)
        second = cache.get_or_fetch("k", 60, fetch)

        self.assertEqual(len(calls), 1)
        self.assertIs(first, second)

    def test_entry_expires_after_ttl(self):
        cache.set("k", "value", 0.01)
        time.sleep(0.03)

        self.assertIsNone(cache.get("k"))


if __name__ == "__main__":
    unittest.main()
