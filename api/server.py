"""
api/server.py  —  DNS Resolution Service  —  REST API Layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Architecture (PRD §8):
  HTTP Client
      ↓
  This Flask server  (Python – API layer)
      ↓ subprocess
  core/dns_resolver.exe  (C++ – recursive resolution engine)
      ↓ UDP / TCP
  External DNS hierarchy

Endpoints:
  GET  /resolve?domain=<domain>[&type=A]   → PRD-compliant JSON response
  GET  /cache                              → current in-process cache state
  DELETE /cache                            → clear cache
  GET  /metrics                            → query statistics
  POST /benchmark                          → compare local vs Google vs Cloudflare
  GET  /health                             → health check

Run:
  python api/server.py
"""

import os
import sys
import json
import time
import subprocess
import threading
import socket
import struct
from collections import OrderedDict, deque
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# ─────────────────────────────────────────────────────────────────────────────
#  Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Paths
_HERE       = os.path.dirname(os.path.abspath(__file__))
_ROOT       = os.path.dirname(_HERE)
_WEB_DIR    = os.path.join(_ROOT, "web")
_BINARY_WIN = os.path.join(_ROOT, "core", "dns_resolver.exe")
_BINARY_NIX = os.path.join(_ROOT, "core", "dns_resolver")

BINARY_PATH = _BINARY_WIN if os.path.exists(_BINARY_WIN) else _BINARY_NIX

CACHE_CAPACITY  = 1000
DEFAULT_TTL     = 300    # seconds
API_PORT        = 5000
RESOLVER_TIMEOUT = 15    # seconds to wait for the C++ process

# ─────────────────────────────────────────────────────────────────────────────
#  In-process Python-side LRU + TTL cache
#  (supplements the C++ resolver's own cache so repeated HTTP hits are O(1))
# ─────────────────────────────────────────────────────────────────────────────

class DNSCache:
    """Thread-safe LRU + TTL cache backed by an OrderedDict."""

    def __init__(self, capacity: int = CACHE_CAPACITY):
        self._cap    = capacity
        self._store  = OrderedDict()   # key → (value, stored_at, ttl)
        self._hits   = 0
        self._misses = 0
        self._lock   = threading.Lock()

    # ── public API ────────────────────────────────────────────────────────────

    def get(self, key: str):
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            value, stored_at, ttl = self._store[key]
            age = time.time() - stored_at
            if age >= ttl:
                del self._store[key]
                self._misses += 1
                return None
            self._store.move_to_end(key)
            self._hits += 1
            return value

    def put(self, key: str, value, ttl: int = DEFAULT_TTL):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = (value, time.time(), ttl)
            if len(self._store) > self._cap:
                self._store.popitem(last=False)   # evict oldest

    def clear(self):
        with self._lock:
            self._store.clear()
            self._hits = self._misses = 0

    def all_entries(self):
        with self._lock:
            now = time.time()
            out = []
            for k, (v, stored_at, ttl) in list(self._store.items()):
                remaining = max(0, ttl - (now - stored_at))
                out.append({
                    "key":           k,
                    "domain":        v.get("domain", ""),
                    "type":          v.get("qtype",  "A"),
                    "ip":            v.get("ip",     ""),
                    "remaining_ttl": int(remaining),
                    "status":        "valid" if remaining > 0 else "expired",
                })
            return out

    def stats(self):
        with self._lock:
            return {
                "size":     len(self._store),
                "capacity": self._cap,
                "hits":     self._hits,
                "misses":   self._misses,
                "hit_rate": (
                    round(self._hits / (self._hits + self._misses) * 100, 1)
                    if (self._hits + self._misses) > 0 else 0.0
                ),
            }


# ─────────────────────────────────────────────────────────────────────────────
#  Metrics tracker
# ─────────────────────────────────────────────────────────────────────────────

class Metrics:
    def __init__(self, maxlen: int = 1000):
        self._history = deque(maxlen=maxlen)
        self._lock    = threading.Lock()

    def record(self, domain: str, qtype: str, latency_ms: float,
               success: bool, cached: bool, used_tcp: bool):
        with self._lock:
            self._history.append({
                "ts":         time.time(),
                "domain":     domain,
                "qtype":      qtype,
                "latency_ms": latency_ms,
                "success":    success,
                "cached":     cached,
                "used_tcp":   used_tcp,
            })

    def summary(self):
        with self._lock:
            h = list(self._history)
        if not h:
            return {"total": 0}
        total   = len(h)
        cached  = sum(1 for e in h if e["cached"])
        success = sum(1 for e in h if e["success"])
        tcp     = sum(1 for e in h if e["used_tcp"])
        lats    = [e["latency_ms"] for e in h]
        return {
            "total":            total,
            "success":          success,
            "failures":         total - success,
            "cached_hits":      cached,
            "cache_hit_rate":   round(cached / total * 100, 1),
            "tcp_fallbacks":    tcp,
            "avg_latency_ms":   round(sum(lats) / len(lats), 2),
            "min_latency_ms":   round(min(lats), 2),
            "max_latency_ms":   round(max(lats), 2),
            "recent_queries":   h[-20:],
        }


# ─────────────────────────────────────────────────────────────────────────────
#  C++ resolver bridge
# ─────────────────────────────────────────────────────────────────────────────

def run_cpp_resolver(domain: str, qtype: str = "A") -> dict:
    """
    Calls the compiled C++ binary and returns its parsed JSON output.
    Raises RuntimeError if the binary is missing or returns an error.
    """
    if not os.path.isfile(BINARY_PATH):
        raise RuntimeError(
            f"C++ binary not found at {BINARY_PATH}. "
            "Run build.bat (Windows) or build.sh (Linux/macOS) first."
        )

    cmd = [BINARY_PATH, domain, qtype]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=RESOLVER_TIMEOUT
        )
        stdout = proc.stdout.strip()
        if not stdout:
            raise RuntimeError(f"C++ resolver produced no output (stderr: {proc.stderr.strip()})")
        return json.loads(stdout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"C++ resolver timed out after {RESOLVER_TIMEOUT}s")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"C++ resolver returned invalid JSON: {e}")


def send_udp_query(domain: str, server_ip: str, qtype_id: int = 1) -> float:
    """
    Quick UDP query helper for benchmark comparisons.
    Returns round-trip time in ms, or -1.0 on failure.
    """
    try:
        # Build a minimal DNS query for the domain
        tid = 0xABCD
        flags = 0x0100   # RD=1
        qname = b''.join(bytes([len(l)]) + l.encode() for l in domain.split('.')) + b'\x00'
        pkt   = struct.pack('!HHHHHH', tid, flags, 1, 0, 0, 0) + qname + struct.pack('!HH', qtype_id, 1)

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0)
        t0 = time.perf_counter()
        sock.sendto(pkt, (server_ip, 53))
        sock.recvfrom(4096)
        rtt = (time.perf_counter() - t0) * 1000
        sock.close()
        return round(rtt, 2)
    except Exception:
        return -1.0


# ─────────────────────────────────────────────────────────────────────────────
#  Flask application
# ─────────────────────────────────────────────────────────────────────────────

app     = Flask(__name__, static_folder=_WEB_DIR, static_url_path="/static")
CORS(app)

cache   = DNSCache()
metrics = Metrics()

VALID_TYPES = {"A", "AAAA", "NS", "MX", "CNAME", "TXT", "PTR", "SOA"}

# ── Serve web UI at root ───────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return send_from_directory(_WEB_DIR, "index.html")

@app.route("/<path:filename>")
def static_web(filename):
    return send_from_directory(_WEB_DIR, filename)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_domain(domain: str) -> str | None:
    """Returns an error string if domain is invalid, else None."""
    if not domain:
        return "domain parameter is required"
    if len(domain) > 253:
        return "domain name too long (max 253 characters)"
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.")
    if not all(c in allowed for c in domain):
        return "domain contains invalid characters"
    return None


# ── /resolve ──────────────────────────────────────────────────────────────────

@app.route("/resolve", methods=["GET"])
def resolve():
    """
    GET /resolve?domain=<domain>[&type=A]

    PRD §5.4 compliant response:
    {
      "domain":     "example.com",
      "ip":         "93.184.216.34",
      "cached":     true,
      "latency_ms": 1.2,
      "record_type":"A",
      "answers":    [...],
      "resolution_path": [...],
      "used_tcp":   false
    }
    """
    domain = request.args.get("domain", "").strip().lower()
    qtype  = request.args.get("type", "A").upper()

    # ── Input validation ──────────────────────────────────────────────────────
    err = _validate_domain(domain)
    if err:
        return jsonify({"error": err}), 400

    if qtype not in VALID_TYPES:
        return jsonify({"error": f"Unsupported record type: {qtype}. "
                                  f"Valid types: {', '.join(sorted(VALID_TYPES))}"}), 400

    cache_key = f"{domain}/{qtype}"

    # ── Cache check ───────────────────────────────────────────────────────────
    t0     = time.perf_counter()
    cached = cache.get(cache_key)
    if cached is not None:
        cached["cached"]     = True
        cached["latency_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        metrics.record(domain, qtype, cached["latency_ms"], True, True, False)
        return jsonify(cached)

    # ── Call C++ resolver ─────────────────────────────────────────────────────
    try:
        cpp_result = run_cpp_resolver(domain, qtype)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503

    latency_ms = round((time.perf_counter() - t0) * 1000, 3)

    if not cpp_result.get("success"):
        return jsonify({
            "error":      cpp_result.get("error", "Resolution failed"),
            "domain":     domain,
            "latency_ms": latency_ms,
        }), 404

    # Extract the primary IP from the first A/AAAA answer
    ip = ""
    for ans in cpp_result.get("answers", []):
        if ans.get("type") == qtype:
            ip = ans.get("data", "")
            break
    if not ip and cpp_result.get("answers"):
        ip = cpp_result["answers"][0].get("data", "")

    # Build PRD-compliant response
    ttl = 300
    for ans in cpp_result.get("answers", []):
        if ans.get("ttl", 0) > 0:
            ttl = ans["ttl"]
            break

    response_body = {
        "domain":          domain,
        "ip":              ip,
        "record_type":     qtype,
        "cached":          False,
        "latency_ms":      latency_ms,
        "answers":         cpp_result.get("answers", []),
        "resolution_path": cpp_result.get("resolution_path", []),
        "used_tcp":        cpp_result.get("used_tcp", False),
    }

    # Store in Python-side cache
    cache.put(cache_key, dict(response_body), ttl=ttl)

    metrics.record(domain, qtype,
                   latency_ms,
                   True,
                   False,
                   cpp_result.get("used_tcp", False))

    return jsonify(response_body)


# ── /cache ─────────────────────────────────────────────────────────────────────

@app.route("/cache", methods=["GET"])
def get_cache():
    return jsonify({
        "stats":   cache.stats(),
        "entries": cache.all_entries(),
    })


@app.route("/cache", methods=["DELETE"])
def clear_cache():
    cache.clear()
    return jsonify({"message": "Cache cleared successfully."})


# ── /metrics ───────────────────────────────────────────────────────────────────

@app.route("/metrics", methods=["GET"])
def get_metrics():
    return jsonify(metrics.summary())


# ── /benchmark ─────────────────────────────────────────────────────────────────

@app.route("/benchmark", methods=["POST"])
def run_benchmark():
    """
    POST /benchmark
    Body: { "domains": ["google.com", "example.com"], "type": "A" }
    Compares: Local resolver vs Google (8.8.8.8) vs Cloudflare (1.1.1.1)
    """
    body    = request.get_json(silent=True) or {}
    domains = body.get("domains", ["google.com", "example.com", "wikipedia.org"])
    qtype   = body.get("type", "A").upper()

    if not isinstance(domains, list) or len(domains) > 20:
        return jsonify({"error": "domains must be a list with at most 20 entries"}), 400

    results = []
    for domain in domains:
        row = {"domain": domain, "type": qtype}

        # 1. Local resolver (cold cache) — clear first to force resolution
        cache.clear()
        t0 = time.perf_counter()
        try:
            cpp_result = run_cpp_resolver(domain, qtype)
            row["local_cold_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            row["local_success"] = cpp_result.get("success", False)
        except RuntimeError as e:
            row["local_cold_ms"] = None
            row["local_success"] = False
            row["local_error"]   = str(e)

        # 2. Local resolver (warm cache)
        t0 = time.perf_counter()
        cached_hit = cache.get(f"{domain}/{qtype}")
        if cached_hit:
            row["local_warm_ms"] = round((time.perf_counter() - t0) * 1000, 3)
        else:
            row["local_warm_ms"] = None

        # 3. Google DNS (8.8.8.8)
        type_id_map = {"A": 1, "AAAA": 28, "NS": 2, "MX": 15}
        type_id = type_id_map.get(qtype, 1)
        row["google_ms"]     = send_udp_query(domain, "8.8.8.8", type_id)
        row["cloudflare_ms"] = send_udp_query(domain, "1.1.1.1", type_id)

        results.append(row)

    return jsonify({"results": results})


# ── /health ────────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    binary_ok = os.path.isfile(BINARY_PATH)
    return jsonify({
        "status":     "ok" if binary_ok else "degraded",
        "binary":     BINARY_PATH,
        "binary_ok":  binary_ok,
        "cache_size": cache.stats()["size"],
    }), 200 if binary_ok else 503


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  DNS Resolution Service — REST API")
    print("=" * 60)
    print(f"  C++ binary : {BINARY_PATH}")
    print(f"  Binary OK  : {os.path.isfile(BINARY_PATH)}")
    print(f"  Listening  : http://127.0.0.1:{API_PORT}")
    print(f"  Dashboard  : http://127.0.0.1:{API_PORT}/")
    print("=" * 60)

    if not os.path.isfile(BINARY_PATH):
        print("\n⚠  WARNING: C++ binary not found!")
        print("  Run `build.bat` first to compile the resolver.\n")

    import webbrowser
    import threading
    threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{API_PORT}/")).start()

    app.run(host="0.0.0.0", port=API_PORT, debug=False, threaded=True)
