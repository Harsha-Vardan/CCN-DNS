# 🌐 DNS Resolution Service

**RFC 1035-compliant Recursive DNS Resolver**  
*C++ Engine · Python REST API · Real-time Web Dashboard*

---

## 🏗 Architecture  (PRD §8)

```
Client (Browser / curl)
        ↓  HTTP
  api/server.py  ──────  Flask REST API  (Python)
        ↓  subprocess (JSON over stdout)
  core/dns_resolver  ─── C++ Resolver Engine
        ├── LRU + TTL Cache
        └── Recursive Resolution
                ↓  UDP / TCP  (port 53)
        Root → TLD → Authoritative DNS Servers
                ↓
        Response parsed & cached
                ↓
  JSON response back to client
```

---

## 📁 Project Structure

```
CCN-DNS/
├── core/
│   ├── dns_resolver.h         # C++ header — structs, classes, API
│   └── dns_resolver.cpp       # Full implementation (RFC 1035 §4)
├── api/
│   └── server.py              # Flask REST API layer
├── web/
│   ├── index.html             # Interactive web dashboard
│   ├── style.css              # Dark glassmorphism UI
│   └── app.js                 # Frontend logic
├── tests/
│   └── test_api.py            # Integration test suite
├── build.bat                  # Windows  — compile C++ binary
├── build.sh                   # Linux/macOS — compile C++ binary
├── run.bat                    # Windows  — start all services
├── requirements.txt           # Python pip deps
└── README.md
```

---

## ⚡ Quick Start

### Step 1 — Compile the C++ Resolver

**Windows** (requires [MSYS2](https://www.msys2.org/) + MinGW g++):
```bat
# Install MinGW if needed:
#   pacman -S mingw-w64-ucrt-x86_64-gcc
build.bat
```

**Linux / macOS**:
```bash
chmod +x build.sh
./build.sh
```

The binary is written to `core/dns_resolver.exe` (Windows) or `core/dns_resolver` (Linux/macOS).

---

### Step 2 — Install Python Dependencies
```bash
pip install -r requirements.txt
```

---

### Step 3 — Start the API Server
```bash
python api/server.py
```
Flask listens on **http://127.0.0.1:5000**.

---

### Step 4 — Open the Web Dashboard
Open `web/index.html` in your browser (or just double-click it).

> **All-in-one Windows launcher:** `run.bat` does steps 1–4 automatically.

---

## 🔌 REST API Reference

### `GET /resolve`
Perform DNS resolution.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `domain`  | ✅ yes   | —       | Domain name to resolve |
| `type`    | ✗ no    | `A`     | Record type: `A`, `AAAA`, `NS`, `MX`, `CNAME`, `TXT`, `PTR`, `SOA` |

**Success response** (200):
```json
{
  "domain":          "example.com",
  "ip":              "93.184.216.34",
  "record_type":     "A",
  "cached":          false,
  "latency_ms":      217.4,
  "used_tcp":        false,
  "answers":         [{"name":"example.com","type":"A","ttl":86400,"data":"93.184.216.34"}],
  "resolution_path": ["198.41.0.4","192.12.94.30","199.43.135.53"]
}
```

**Error response** (400 / 404 / 503):
```json
{ "error": "Resolution failed — no authoritative answer for example.invalid" }
```

---

### `GET /cache`
Returns current cache state and statistics.

```json
{
  "stats":   { "size": 42, "capacity": 1000, "hits": 105, "misses": 42, "hit_rate": 71.4 },
  "entries": [ { "domain": "google.com", "type": "A", "ip": "142.250.182.46", "remaining_ttl": 287, "status": "valid" } ]
}
```

### `DELETE /cache`
Clears all cached records.

### `GET /metrics`
Returns query statistics: total queries, success rate, average latency, cache hit rate, TCP fallback count, recent query history.

### `POST /benchmark`
Compares the local resolver against Google (8.8.8.8) and Cloudflare (1.1.1.1).

**Request body:**
```json
{ "domains": ["google.com", "example.com"], "type": "A" }
```

### `GET /health`
Service health check — verifies the C++ binary is compiled and present.

---

## ⚙️ C++ Resolver — Command Line

```bash
# Usage:
core/dns_resolver.exe <domain> [A|AAAA|NS|MX|CNAME|TXT]

# Examples:
core/dns_resolver.exe google.com A
core/dns_resolver.exe gmail.com MX
core/dns_resolver.exe cloudflare.com NS

# Output (JSON to stdout):
{
  "success": true,
  "domain": "google.com",
  "qtype": "A",
  "cached": false,
  "used_tcp": false,
  "latency_ms": 213.500,
  "answers": [{"name":"google.com","type":"A","ttl":300,"data":"142.250.182.46"}],
  "resolution_path": ["198.41.0.4","192.12.94.30","216.239.34.10"]
}
```

---

## 🧪 Running Tests

```bash
# Start the API first, then:
pip install pytest requests
python -m pytest tests/ -v
```

Tests cover:
- ✅ Health check
- ✅ A, NS, MX resolution
- ✅ Cache hit (second request must be cached)
- ✅ Input validation (missing domain, bad chars, invalid type)
- ✅ NXDOMAIN handling
- ✅ Cache clear + re-resolution
- ✅ Metrics correctness
- ✅ Benchmark endpoint
- ✅ **PRD §11 cache efficiency** — ≥70% hit rate over repeated queries

---

## 🔧 Key Implementation Details

### C++ DNS Engine (`core/dns_resolver.cpp`)

| Feature | Detail |
|---------|--------|
| Packet builder | RFC 1035 §4 binary format, length-prefix QNAME encoding |
| Packet parser | Full wire-format parsing with §4.1.4 pointer compression |
| UDP transport | `select()` timeout, up to 4096-byte receive buffer |
| TCP fallback | 2-byte length-prefix framing (RFC 1035 §4.2.2), activated when TC bit is set |
| Recursive walk | Root → TLD → NS referrals with glue record extraction |
| CNAME following | Automatically follows CNAME chains up to 10 deep |
| Cache | Thread-safe LRU eviction + TTL expiry (1000 entry default) |
| JSON output | Compact, manually serialised (no runtime dependency) |

### Python API Layer (`api/server.py`)

| Feature | Detail |
|---------|--------|
| Cache | Second Python-side LRU+TTL cache for sub-millisecond repeat hits |
| Validation | Domain length/character checking, record type whitelist |
| Metrics | Rolling 1000-query history with latency stats |
| Benchmark | Cold + warm local timing vs public resolvers |
| Threading | Flask `threaded=True` — handles concurrent requests |

---

## 🔮 Future Enhancements (PRD §13)

- AAAA / IPv6 full support
- DNSSEC validation (cryptographic signature verification)
- DNS-over-TLS (DoT)
- Parallel NS resolution for lower latency
- Distributed Redis cache
- Docker containerisation
- Rate limiting middleware

---

**Stack:** C++ (networking engine) · Python / Flask (API layer) · HTML/CSS/JS (dashboard)  
**Protocol:** RFC 1035, RFC 1034 · UDP + TCP port 53
