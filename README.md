# 🚀 Advanced DNS Resolver & Intelligent Caching System

A full-featured, Python-based DNS resolution system that implements **Recursive**, **Forwarding**, and **DNS-over-HTTPS (DoH)** resolution modes. It features a robust **TTL + LRU Cache**, **DNSSEC awareness**, and a modern **Streamlit GUI** for real-time visualization of DNS lookups, packet inspection, and resolution paths.

---

## 🌟 Features

### 🔹 Core Resolution Modes
- **Recursive Resolver**: Performs full recursion starting from Root Servers (`.`) -> TLD -> Authoritative Servers.
- **Forward Resolver**: Forwards queries to upstream DNS providers (e.g., Google `8.8.8.8`).
- **DoH Resolver**: Securely resolves queries via HTTPS (DNS-over-HTTPS) using providers like Google or Cloudflare.
- **AUTO Mode**: Intelligent fallback mechanism (Recursive → Forward → DoH) to guarantee resolution.

### 🔹 Advanced Capabilities
- **Intelligent Caching**: Implements Least Recently Used (LRU) eviction with Time-To-Live (TTL) enforcement.
- **DNSSEC Awareness**: Detects and flags signed zones (RRSIG) and delegation signers (DS).
- **Packet Inspection**: View raw DNS packet structures (Header, Question, Answer sections) in hex and parsed formats.
- **Resolution Visualizer**: Graphically visualize the path taken by a recursive query.
- **Local DNS Server**: Includes a UDP server running on port `5353` that can be queried via `dig` or `nslookup`.

### 🔹 GUI & Analytics
- **Interactive Dashboard**: Built with Streamlit for easy interaction.
- **Performance Metrics**: Track average latency, cache hit/miss ratios, and query modes.
- **Cache Explorer**: View currently cached records and their remaining TTL.

---

## 🛠️ Installation

### Prerequisites
- Python 3.9+
- `pip`
- Node.js and `npm` (for Electron GUI)

### Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/Harsha-Vardan/CCN-DNS.git
   cd CCN-DNS
   ```

2. Install dependencies:
   ```bash
   pip install streamlit requests graphviz pandas
   ```
   ```
   *(Note: `graphviz` also requires the Graphviz system binary to be installed and in your PATH for the visualization to work)*

3. Install Electron GUI dependencies:
   ```bash
   cd electron_gui
   npm install
   cd ..
   ```
   *(This restores the `node_modules` folder required for the GUI)*

---

## 🚀 Usage

### 1. Run the GUI Application
Launch the interactive dashboard to perform lookups and visualize data.
```bash
streamlit run gui/app_streamlit.py
```
Open your browser to the URL shown (usually `http://localhost:8501`).



### 2. Run the Electron GUI
Launch the desktop application.
```bash
cd electron_gui
npm start
```

### 3. Run the Local DNS Server
(Optional) Start the local UDP server to accept standard DNS queries.
```bash
# You may need to run this script directly or adapt it to run as a standalone service
python -m dns_resolver.server_local_dns
```
Query it using `dig`:
```bash
dig @127.0.0.1 -p 5353 google.com
```

### 4. Run Tests
Verify the integrity of the system by running the unit test suite.
```bash
python -m unittest discover tests
```

---

## 📂 Project Structure

```
dns_project/
├── dns_resolver/           # Core Logic
│   ├── packet.py           # DNS Packet Construction
│   ├── parser.py           # Response Parsing
│   ├── recursive_resolver.py # Recursive Logic
│   ├── forward_resolver.py # Forwarding Logic
│   ├── transport_doh.py    # DoH Transport
│   ├── cache.py            # LRU + TTL Cache
│   ├── dnssec.py           # DNSSEC Detection
│   └── ...
├── gui/                    # Streamlit Interface
│   ├── app_streamlit.py    # Main App Entry
│   └── components/         # UI Components
├── tests/                  # Unit Tests
└── main_cli.py             # CLI Entry Point (Optional)
```

---

## 📊 Architecture

The system uses a layered architecture:
1. **GUI Layer**: Streamlit interface for user interaction.
2. **API Layer**: Unified `ResolverAPI` that manages modes and fallback logic.
3. **Resolution Layer**: Specialized resolvers (Recursive, Forward, DoH).
4. **Cache Layer**: Intercepts requests to serve cached data instantly.
5. **Transport Layer**: Handles raw UDP sockets and HTTPS requests.

---

## 🔮 Future Improvements
- Full DNSSEC validation (cryptographic signature verification).
- DNS-over-TLS (DoT) support.
- GeoIP mapping for resolved IP addresses.

---

**Author**: Harsha Vardan
