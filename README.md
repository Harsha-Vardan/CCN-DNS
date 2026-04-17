# 🌐 DNS Resolution Service

**RFC 1035-compliant Recursive DNS Resolver**  
*C++ Engine · Python REST API · Real-time Web Dashboard*

> **Status:** ✅ Fully operational — 10/10 domains verified (instagram.com, facebook.com, wikipedia.org, google.com, youtube.com, twitter.com, amazon.com, reddit.com, netflix.com, github.com)

---

## 🏗 Architecture

```
Client (Browser / curl)
        ↓  HTTP
  api/server.py  ──────  Flask REST API  (Python)
        │                  ├── Python-side LRU + TTL cache   (sub-ms repeat hits)
        │                  ├── Fallback resolver → 8.8.8.8   (when C++ walk fails)
        │                  └── Metrics / Benchmark engine
        ↓  subprocess (JSON over stdout)
  core/dns_resolver.exe ── C++ Resolver Engine
        ├── Loop-detection (visited server set per chain)
        ├── CNAME chain following (current NS → root fallback)
        ├── Glue-less NS resolution (isolated path vector)
        ├── LRU + TTL Cache (1 000 entries)
        └── Recursive Walk: Root → TLD → Authoritative
                ↓  UDP (2 s/hop) / TCP fallback (TC bit)
        13 Root Servers → TLD NS → Authoritative NS
                ↓
        JSON response back to client
```

---

## 📁 Project Structure

```
CCN-DNS/
├── core/
│   ├── dns_resolver.h         # C++ header — structs, classes, constants
│   └── dns_resolver.cpp       # Full RFC 1035 implementation
├── api/
│   └── server.py              # Flask REST API + Python fallback resolver
├── web/
│   ├── index.html             # Interactive web dashboard
│   ├── style.css              # Dark glassmorphism UI
│   └── app.js                 # Frontend logic (tabs, charts, packet inspector)
├── build.bat                  # Windows  — compile C++ binary (MinGW g++)
├── build.sh                   # Linux/macOS — compile C++ binary
├── run.bat                    # Windows  — start all services in one click
├── requirements.txt           # Python pip dependencies
├── project_stack.log          # Technology stack & development log
└── README.md
```

> **Not tracked in git:** `tests/` (smoke-tests), `core/*.exe` (binary), `DEVNOTES.md` (internal notes)

---

## ⚡ Quick Start

### Step 1 — Compile the C++ Resolver

**Windows** (requires [MSYS2](https://www.msys2.org/) + MinGW g++):
```bat
# Install MinGW if needed:
#   pacman -S mingw-w64-ucrt-x86_64-gcc
build.bat
```

**Linux / macOS:**
```bash
chmod +x build.sh && ./build.sh
```

The binary is written to `core/dns_resolver.exe` (Windows) or `core/dns_resolver` (Linux/macOS).

### Step 2 — Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 3 — Start the API Server
```bash
python api/server.py
```
Flask listens on **http://127.0.0.1:5000** and auto-opens the dashboard.

> **All-in-one Windows launcher:** `run.bat` does steps 1–3 automatically.

---

## 🔌 REST API Reference

### `GET /resolve`
Perform recursive DNS resolution.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `domain`  | ✅ yes   | —       | Domain name to resolve |
| `type`    | ✗ no    | `A`     | Record type: `A` `AAAA` `NS` `MX` `CNAME` `TXT` `PTR` `SOA` |

**Success response (200):**
```json
{
  "domain":          "instagram.com",
  "ip":              "57.144.52.34",
  "record_type":     "A",
  "cached":          false,
  "latency_ms":      598.18,
  "used_tcp":        false,
  "answers":         [{"name":"instagram.com","type":"A","ttl":300,"data":"57.144.52.34"}],
  "resolution_path": ["198.41.0.4","192.12.94.30","185.159.196.2"]
}
```

**Fallback response** (when C++ recursive walk times out — still 200):
```json
{
  "domain":          "instagram.com",
  "ip":              "57.144.52.34",
  "record_type":     "A",
  "cached":          false,
  "latency_ms":      312.5,
  "resolution_path": ["198.41.0.4", "8.8.8.8"],
  "note":            "resolved via 8.8.8.8 fallback (recursive walk incomplete)"
}
```

**Error response (400 / 503):**
```json
{ "error": "domain contains invalid characters" }
```

---

### `GET /cache`
Returns current cache state and statistics.

```json
{
  "stats":   { "size": 42, "capacity": 1000, "hits": 105, "misses": 42, "hit_rate": 71.4 },
  "entries": [{ "domain": "google.com", "type": "A", "ip": "142.250.182.46", "remaining_ttl": 287, "status": "valid" }]
}
```

### `DELETE /cache` — Clears all cached records.

### `GET /metrics`
Rolling 1000-query history: total, success rate, avg/min/max latency, cache hit rate, TCP fallback count.

### `POST /benchmark`
Compares local resolver (cold + warm) against Google `8.8.8.8` and Cloudflare `1.1.1.1`.
```json
{ "domains": ["google.com", "instagram.com"], "type": "A" }
```

### `GET /health`
Verifies the C++ binary is compiled and present.

---

## ⚙️ C++ Resolver — CLI Usage

```bash
core/dns_resolver.exe <domain> [A|AAAA|NS|MX|CNAME|TXT|PTR|SOA]

# Examples:
core/dns_resolver.exe instagram.com A
core/dns_resolver.exe gmail.com MX
core/dns_resolver.exe cloudflare.com NS
```

Output is JSON to `stdout`:
```json
{
  "success": true,
  "domain":  "instagram.com",
  "qtype":   "A",
  "cached":  false,
  "used_tcp": false,
  "latency_ms": 598.120,
  "answers":  [{"name":"instagram.com","type":"A","ttl":300,"data":"57.144.52.34"}],
  "resolution_path": ["198.41.0.4","192.12.94.30","185.159.196.2"]
}
```

---

## 🔧 Implementation Details

### C++ DNS Engine (`core/dns_resolver.cpp`)

| Feature | Detail |
|---------|--------|
| Packet builder | RFC 1035 §4 binary format, length-prefix QNAME encoding |
| Packet parser | Full wire-format parser with §4.1.4 pointer compression |
| UDP transport | `select()` 2 s/hop timeout, 4096-byte receive buffer |
| TCP fallback | 2-byte length-prefix framing (RFC 1035 §4.2.2), triggered on TC bit |
| Loop detection | Skips any server IP already visited in the current resolution chain |
| CNAME following | Tries same authoritative NS first, then falls back to 3 random roots |
| Glue-less NS | Isolated `path` vector per NS lookup — prevents false loop positives |
| Recursive walk | Root → TLD → NS referrals with glue-record extraction |
| Cache | Thread-safe LRU eviction + TTL expiry, 1 000 entries default |

### Python API Layer (`api/server.py`)

| Feature | Detail |
|---------|--------|
| Python cache | Second LRU+TTL cache for sub-millisecond repeat hits |
| Fallback resolver | `fallback_resolve()` — raw UDP to 8.8.8.8 with full pointer decompression |
| Subprocess timeout | 30 s (up from 15 s) to handle deep CNAME chains |
| Validation | Domain length ≤ 253, character whitelist, type whitelist |
| Metrics | Rolling 1 000-query deque with latency stats |
| Benchmark | Cold + warm local timing vs public resolvers |
| Threading | `threaded=True` for concurrent request handling |

---

## ✅ Verified Domain Results (2026-04-18)

| Domain | IP | Latency | Method |
|--------|----|---------|--------|
| instagram.com | 57.144.52.34 | 598 ms | Recursive |
| facebook.com | 57.144.52.1 | 434 ms | Recursive |
| wikipedia.org | 103.102.166.224 | 610 ms | Recursive |
| google.com | 142.250.205.142 | 270 ms | Recursive |
| youtube.com | 142.250.77.142 | 205 ms | Recursive |
| twitter.com | 172.66.0.227 | 2107 ms | Recursive |
| amazon.com | 98.82.161.185 | 667 ms | Recursive |
| reddit.com | 151.101.1.140 | 1176 ms | Recursive |
| netflix.com | 18.200.8.190 | 408 ms | Recursive |
| github.com | 20.207.73.82 | 1115 ms | Recursive |

---

## 🔮 Future Enhancements

- Full AAAA / IPv6 resolution path
- DNSSEC cryptographic validation
- DNS-over-TLS (DoT) / DNS-over-HTTPS (DoH)
- Parallel NS resolution for lower latency
- Redis distributed cache
- Docker containerisation
- Rate limiting middleware

---

**Stack:** C++17 · Python 3 / Flask · HTML5 / CSS3 / Vanilla JS  
**Protocol:** RFC 1035 · RFC 1034 · UDP + TCP port 53  
**Branch:** `feature/dns-dashboard`
