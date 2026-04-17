"""
tests/test_api.py
─────────────────
Integration tests for the DNS Resolution Service REST API.

Run:  python -m pytest tests/ -v
      (or: python tests/test_api.py)

Requires: Flask server running on http://127.0.0.1:5000
"""

import sys
import os
import time
import json
import unittest
import requests

API = "http://127.0.0.1:5000"
TIMEOUT = 20   # seconds – recursive resolution can be slow

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def get(path, **kwargs):
    return requests.get(API + path, timeout=TIMEOUT, **kwargs)

def post(path, **kwargs):
    return requests.post(API + path, timeout=TIMEOUT, **kwargs)

def delete(path, **kwargs):
    return requests.delete(API + path, timeout=TIMEOUT, **kwargs)

# ─────────────────────────────────────────────────────────────────────────────
#  Test class
# ─────────────────────────────────────────────────────────────────────────────

class TestDNSAPI(unittest.TestCase):

    # ── Health ───────────────────────────────────────────────────────────────

    def test_01_health(self):
        r = get("/health")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("status", d)
        self.assertIn("binary_ok", d)
        print(f"  Health: {d}")

    # ── Resolve — valid domains ───────────────────────────────────────────────

    def test_02_resolve_google_A(self):
        r = get("/resolve", params={"domain": "google.com", "type": "A"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("domain",     d)
        self.assertIn("ip",         d)
        self.assertIn("cached",     d)
        self.assertIn("latency_ms", d)
        self.assertEqual(d["domain"],      "google.com")
        self.assertEqual(d["record_type"], "A")
        self.assertFalse(d["cached"])        # first call must be a miss
        self.assertTrue(d["ip"], "should have an IP")
        print(f"  google.com A → {d['ip']} ({d['latency_ms']} ms)")

    def test_03_resolve_cache_hit(self):
        """Second request for the same domain must be served from cache."""
        get("/resolve", params={"domain": "example.com", "type": "A"})   # warm up
        r = get("/resolve", params={"domain": "example.com", "type": "A"})
        d = r.json()
        self.assertTrue(d["cached"], "second request should be a cache hit")
        self.assertLess(d["latency_ms"], 100, "cached response should be fast (<100 ms)")
        print(f"  example.com A (cached) → {d['ip']} ({d['latency_ms']} ms)")

    def test_04_resolve_NS_record(self):
        r = get("/resolve", params={"domain": "cloudflare.com", "type": "NS"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["record_type"], "NS")
        print(f"  cloudflare.com NS → {d.get('ip')}")

    def test_05_resolve_MX_record(self):
        r = get("/resolve", params={"domain": "gmail.com", "type": "MX"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["record_type"], "MX")
        print(f"  gmail.com MX → {d.get('ip')}")

    # ── Input validation ──────────────────────────────────────────────────────

    def test_06_missing_domain(self):
        r = get("/resolve")
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())

    def test_07_invalid_domain_chars(self):
        r = get("/resolve", params={"domain": "bad domain!", "type": "A"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())

    def test_08_invalid_type(self):
        r = get("/resolve", params={"domain": "example.com", "type": "XYZZY"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("error", r.json())

    def test_09_nonexistent_domain(self):
        r = get("/resolve", params={"domain": "thisdomainreallydoesnotexist12345.invalid"})
        self.assertIn(r.status_code, [404, 200])   # may return error dict with 404
        d = r.json()
        if r.status_code == 404:
            self.assertIn("error", d)

    # ── Cache endpoints ───────────────────────────────────────────────────────

    def test_10_cache_get(self):
        get("/resolve", params={"domain": "github.com", "type": "A"})   # put something in
        r = get("/cache")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("stats",   d)
        self.assertIn("entries", d)
        self.assertIn("size",    d["stats"])
        print(f"  Cache size: {d['stats']['size']}")

    def test_11_cache_clear(self):
        r = delete("/cache")
        self.assertEqual(r.status_code, 200)
        self.assertIn("message", r.json())

        # After clear, next resolve must be a miss
        r2 = get("/resolve", params={"domain": "github.com", "type": "A"})
        d2 = r2.json()
        self.assertFalse(d2.get("cached"), "after clear, should be a miss")

    # ── Metrics ───────────────────────────────────────────────────────────────

    def test_12_metrics(self):
        get("/resolve", params={"domain": "wikipedia.org", "type": "A"})
        r = get("/metrics")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("total", d)
        self.assertGreater(d["total"], 0)
        print(f"  Metrics: total={d['total']}, avg={d.get('avg_latency_ms')} ms, "
              f"hit_rate={d.get('cache_hit_rate')} %")

    # ── Benchmark ─────────────────────────────────────────────────────────────

    def test_13_benchmark(self):
        r = post("/benchmark", json={"domains": ["google.com", "example.com"], "type": "A"})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("results", d)
        self.assertEqual(len(d["results"]), 2)
        for row in d["results"]:
            self.assertIn("domain",       row)
            self.assertIn("local_cold_ms", row)
            self.assertIn("google_ms",    row)
            self.assertIn("cloudflare_ms",row)
        print(f"  Benchmark results: {[(r['domain'], r.get('local_cold_ms')) for r in d['results']]}")

    # ── Cache efficiency (PRD success metric: ~70% reduction) ─────────────────

    def test_14_cache_efficiency(self):
        """PRD §11: resolve the same domain 10× and verify ≥70% cached."""
        delete("/cache")   # start fresh

        domains = ["example.com"] * 10
        cached_hits = 0
        for domain in domains:
            r = get("/resolve", params={"domain": domain, "type": "A"})
            if r.ok and r.json().get("cached"):
                cached_hits += 1

        hit_rate = cached_hits / len(domains) * 100
        self.assertGreaterEqual(hit_rate, 70,
            f"Cache hit rate {hit_rate:.1f}% should be ≥70%")
        print(f"  Cache efficiency: {hit_rate:.1f}% over {len(domains)} requests")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Check if API is reachable first
    try:
        requests.get(API + "/health", timeout=3)
    except requests.ConnectionError:
        print(f"\n❌  API not reachable at {API}")
        print("   Start it with:  python api/server.py\n")
        sys.exit(1)

    print(f"\n🧪  Running DNS API Integration Tests against {API}\n")
    unittest.main(verbosity=2)
