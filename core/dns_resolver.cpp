// ─────────────────────────────────────────────────────────────────────────────
//  dns_resolver.cpp
//  RFC 1035-compliant Recursive DNS Resolver — Full Implementation
//
//  Compile (Windows / MinGW-64):
//    g++ -std=c++17 -O2 -Wall dns_resolver.cpp -o dns_resolver.exe -lws2_32
//  Compile (Linux / macOS):
//    g++ -std=c++17 -O2 -Wall dns_resolver.cpp -o dns_resolver
//
//  Usage:
//    dns_resolver <domain> [A|AAAA|NS|MX|CNAME|TXT]
//
//  Output: JSON to stdout.
// ─────────────────────────────────────────────────────────────────────────────

// ── Platform socket headers ───────────────────────────────────────────────────
#ifdef _WIN32
  #ifndef WIN32_LEAN_AND_MEAN
    #define WIN32_LEAN_AND_MEAN
  #endif
  #include <winsock2.h>
  #include <ws2tcpip.h>
  // Note: link with -lws2_32 on the compiler command line.
  typedef SOCKET socket_t;
  #define CLOSE_SOCK(s)  closesocket(s)
  #define SOCK_INVALID   INVALID_SOCKET
  #define SOCK_ERR       SOCKET_ERROR
  #define SOCK_ERR_CODE  WSAGetLastError()
#else
  #include <sys/socket.h>
  #include <netinet/in.h>
  #include <arpa/inet.h>
  #include <unistd.h>
  #include <sys/select.h>
  #include <errno.h>
  typedef int socket_t;
  #define CLOSE_SOCK(s)  ::close(s)
  #define SOCK_INVALID   (-1)
  #define SOCK_ERR       (-1)
  #define SOCK_ERR_CODE  errno
#endif

#include "dns_resolver.h"

#include <iostream>
#include <sstream>
#include <iomanip>
#include <cstring>
#include <cstdio>
#include <cassert>
#include <random>
#include <algorithm>
#include <chrono>

namespace dns {

// ─────────────────────────────────────────────────────────────────────────────
//  Root server IPs  (13 root name servers, RFC 7958)
// ─────────────────────────────────────────────────────────────────────────────
static const char* ROOT_SERVERS[] = {
    "198.41.0.4",      // a.root-servers.net
    "199.9.14.201",    // b.root-servers.net
    "192.33.4.12",     // c.root-servers.net
    "199.7.91.13",     // d.root-servers.net
    "192.203.230.10",  // e.root-servers.net
    "192.5.5.241",     // f.root-servers.net
    "192.112.36.4",    // g.root-servers.net
    "198.97.190.53",   // h.root-servers.net
    "192.36.148.17",   // i.root-servers.net
    "192.58.128.30",   // j.root-servers.net
    "193.0.14.129",    // k.root-servers.net
    "199.7.83.42",     // l.root-servers.net
    "202.12.27.33"     // m.root-servers.net
};
static constexpr int NUM_ROOT_SERVERS = 13;

// ─────────────────────────────────────────────────────────────────────────────
//  Platform init / cleanup
// ─────────────────────────────────────────────────────────────────────────────
void net_init() {
#ifdef _WIN32
    WSADATA wsa{};
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0)
        throw std::runtime_error("WSAStartup failed");
#endif
}

void net_cleanup() {
#ifdef _WIN32
    WSACleanup();
#endif
}

// ─────────────────────────────────────────────────────────────────────────────
//  Internal binary helpers
// ─────────────────────────────────────────────────────────────────────────────
static inline uint16_t rd16(const uint8_t* p) {
    return static_cast<uint16_t>((p[0] << 8) | p[1]);
}
static inline uint32_t rd32(const uint8_t* p) {
    return (static_cast<uint32_t>(p[0]) << 24) |
           (static_cast<uint32_t>(p[1]) << 16) |
           (static_cast<uint32_t>(p[2]) <<  8) |
            static_cast<uint32_t>(p[3]);
}
static inline void wr16(std::vector<uint8_t>& b, uint16_t v) {
    b.push_back(static_cast<uint8_t>(v >> 8));
    b.push_back(static_cast<uint8_t>(v));
}

static uint16_t random_id() {
    static std::mt19937 rng(
        static_cast<unsigned>(
            std::chrono::steady_clock::now().time_since_epoch().count()));
    static std::uniform_int_distribution<uint16_t> dist(1, 65535);
    return dist(rng);
}

// ─────────────────────────────────────────────────────────────────────────────
//  Utility
// ─────────────────────────────────────────────────────────────────────────────
std::string type_to_str(uint16_t t) {
    switch (t) {
        case TYPE_A:     return "A";
        case TYPE_NS:    return "NS";
        case TYPE_CNAME: return "CNAME";
        case TYPE_SOA:   return "SOA";
        case TYPE_PTR:   return "PTR";
        case TYPE_MX:    return "MX";
        case TYPE_TXT:   return "TXT";
        case TYPE_AAAA:  return "AAAA";
        default:         return "TYPE" + std::to_string(t);
    }
}

// JSON-escape a string (handles quotes and backslashes).
static std::string json_str(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 2);
    out += '"';
    for (char c : s) {
        if      (c == '"')  out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else                out += c;
    }
    out += '"';
    return out;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Name encoding  (RFC 1035 §3.1)
// ─────────────────────────────────────────────────────────────────────────────
std::vector<uint8_t> encode_name(const std::string& domain) {
    std::vector<uint8_t> out;
    std::string d = domain;
    if (!d.empty() && d.back() == '.') d.pop_back();   // strip trailing dot

    std::string label;
    std::istringstream ss(d);
    while (std::getline(ss, label, '.')) {
        if (label.empty()) continue;
        if (label.size() > 63)
            throw std::runtime_error("DNS label too long: " + label);
        out.push_back(static_cast<uint8_t>(label.size()));
        for (char c : label) out.push_back(static_cast<uint8_t>(c));
    }
    out.push_back(0x00);   // root label / terminator
    return out;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Packet builder  (RFC 1035 §4)
// ─────────────────────────────────────────────────────────────────────────────
std::vector<uint8_t> build_query(const std::string& domain,
                                  uint16_t qtype, uint16_t id, bool rd) {
    if (id == 0) id = random_id();

    std::vector<uint8_t> pkt;
    pkt.reserve(64);

    // Header (12 bytes)
    wr16(pkt, id);                         // Transaction ID
    wr16(pkt, rd ? FLAG_RD : 0);           // Flags
    wr16(pkt, 1);                          // QDCOUNT = 1
    wr16(pkt, 0);                          // ANCOUNT = 0
    wr16(pkt, 0);                          // NSCOUNT = 0
    wr16(pkt, 0);                          // ARCOUNT = 0

    // Question section
    auto qname = encode_name(domain);
    pkt.insert(pkt.end(), qname.begin(), qname.end());
    wr16(pkt, qtype);                      // QTYPE
    wr16(pkt, CLASS_IN);                   // QCLASS

    return pkt;
}

// ─────────────────────────────────────────────────────────────────────────────
//  Name decoder  (RFC 1035 §4.1.4 — with pointer compression)
// ─────────────────────────────────────────────────────────────────────────────
static std::string decode_name(const std::vector<uint8_t>& pkt, size_t& pos) {
    std::string name;
    bool   jumped    = false;
    size_t saved_pos = 0;
    int    jumps     = 0;

    while (pos < pkt.size()) {
        uint8_t len = pkt[pos];

        if ((len & 0xC0) == 0xC0) {
            // Compression pointer
            if (pos + 1 >= pkt.size())
                throw std::runtime_error("DNS: truncated compression pointer");
            uint16_t offset = static_cast<uint16_t>((len & 0x3F) << 8) | pkt[pos + 1];
            if (!jumped) { saved_pos = pos + 2; jumped = true; }
            pos = offset;
            if (++jumps > MAX_JUMPS)
                throw std::runtime_error("DNS: compression pointer loop");
        } else if (len == 0) {
            if (!jumped) ++pos;
            else         pos = saved_pos;
            break;
        } else {
            ++pos;
            if (pos + len > pkt.size())
                throw std::runtime_error("DNS: label out of bounds");
            if (!name.empty()) name += '.';
            name.append(reinterpret_cast<const char*>(&pkt[pos]), len);
            pos += len;
        }
    }
    return name;
}

// ─────────────────────────────────────────────────────────────────────────────
//  RDATA parser
// ─────────────────────────────────────────────────────────────────────────────
static std::string parse_rdata(const std::vector<uint8_t>& pkt,
                                size_t rdata_start, uint16_t rdlen,
                                uint16_t rtype) {
    if (rdata_start + rdlen > pkt.size())
        throw std::runtime_error("DNS: RDATA extends past end of packet");

    size_t pos = rdata_start;

    switch (rtype) {

    case TYPE_A: {
        if (rdlen != 4) throw std::runtime_error("DNS: A record bad RDLENGTH");
        char buf[16];
        std::snprintf(buf, sizeof(buf), "%u.%u.%u.%u",
            pkt[pos], pkt[pos+1], pkt[pos+2], pkt[pos+3]);
        return buf;
    }

    case TYPE_AAAA: {
        if (rdlen != 16) throw std::runtime_error("DNS: AAAA record bad RDLENGTH");
        char buf[40];
        std::snprintf(buf, sizeof(buf),
            "%04x:%04x:%04x:%04x:%04x:%04x:%04x:%04x",
            rd16(&pkt[pos+ 0]), rd16(&pkt[pos+ 2]),
            rd16(&pkt[pos+ 4]), rd16(&pkt[pos+ 6]),
            rd16(&pkt[pos+ 8]), rd16(&pkt[pos+10]),
            rd16(&pkt[pos+12]), rd16(&pkt[pos+14]));
        return buf;
    }

    case TYPE_NS:
    case TYPE_CNAME:
    case TYPE_PTR:
        return decode_name(pkt, pos);

    case TYPE_MX: {
        uint16_t pref = rd16(&pkt[pos]); pos += 2;
        return std::to_string(pref) + " " + decode_name(pkt, pos);
    }

    case TYPE_TXT: {
        std::string txt;
        size_t end = rdata_start + rdlen;
        while (pos < end) {
            uint8_t slen = pkt[pos++];
            if (pos + slen > end) break;
            txt.append(reinterpret_cast<const char*>(&pkt[pos]), slen);
            pos += slen;
        }
        return txt;
    }

    case TYPE_SOA: {
        std::string mname = decode_name(pkt, pos);
        std::string rname = decode_name(pkt, pos);
        if (pos + 20 > pkt.size()) return mname + " " + rname;
        uint32_t serial  = rd32(&pkt[pos]); pos += 4;
        uint32_t refresh = rd32(&pkt[pos]); pos += 4;
        /* retry  */ rd32(&pkt[pos]); pos += 4;
        /* expire */ rd32(&pkt[pos]); pos += 4;
        uint32_t minimum = rd32(&pkt[pos]); pos += 4;
        return mname + " " + rname +
               " serial=" + std::to_string(serial) +
               " refresh=" + std::to_string(refresh) +
               " minimum=" + std::to_string(minimum);
    }

    default: {
        // Unknown type — hex-encode first 32 bytes of RDATA
        std::ostringstream oss;
        oss << "0x";
        for (size_t i = 0; i < std::min<size_t>(rdlen, 32); ++i)
            oss << std::hex << std::setw(2) << std::setfill('0')
                << static_cast<int>(pkt[rdata_start + i]);
        return oss.str();
    }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
//  Response parser  (RFC 1035 §4.1)
// ─────────────────────────────────────────────────────────────────────────────
static Record parse_record(const std::vector<uint8_t>& pkt, size_t& pos) {
    Record rec;
    rec.name = decode_name(pkt, pos);
    if (pos + 10 > pkt.size())
        throw std::runtime_error("DNS: record header truncated");
    rec.type = rd16(&pkt[pos]); pos += 2;
    rec.cls  = rd16(&pkt[pos]); pos += 2;
    rec.ttl  = rd32(&pkt[pos]); pos += 4;
    uint16_t rdlen = rd16(&pkt[pos]); pos += 2;
    rec.data = parse_rdata(pkt, pos, rdlen, rec.type);
    pos += rdlen;
    return rec;
}

Response parse_response(const std::vector<uint8_t>& data) {
    if (data.size() < 12)
        throw std::runtime_error("DNS: packet too short (< 12 bytes)");

    Response resp;
    resp.id    = rd16(&data[0]);
    resp.flags = rd16(&data[2]);
    resp.rcode = static_cast<uint8_t>(resp.flags & RCODE_MASK);
    resp.truncated     = (resp.flags & FLAG_TC) != 0;
    resp.authoritative = (resp.flags & FLAG_AA) != 0;

    uint16_t qdcount = rd16(&data[4]);
    uint16_t ancount = rd16(&data[6]);
    uint16_t nscount = rd16(&data[8]);
    uint16_t arcount = rd16(&data[10]);

    size_t pos = 12;

    // Skip question section
    for (int i = 0; i < qdcount; ++i) {
        decode_name(data, pos);   // QNAME
        pos += 4;                 // QTYPE + QCLASS
    }

    // Answer section
    for (int i = 0; i < ancount; ++i)
        resp.answers.push_back(parse_record(data, pos));

    // Authority section
    for (int i = 0; i < nscount; ++i)
        resp.authorities.push_back(parse_record(data, pos));

    // Additional section
    for (int i = 0; i < arcount; ++i)
        resp.additionals.push_back(parse_record(data, pos));

    // Compute min TTL across all answers (used as cache TTL).
    resp.min_ttl = 300;
    if (!resp.answers.empty()) {
        resp.min_ttl = resp.answers[0].ttl;
        for (const auto& a : resp.answers)
            resp.min_ttl = std::min(resp.min_ttl, a.ttl);
    }

    return resp;
}

// ─────────────────────────────────────────────────────────────────────────────
//  UDP transport  (RFC 1035 §4.2.1)
// ─────────────────────────────────────────────────────────────────────────────
SendResult send_udp(const std::vector<uint8_t>& query,
                    const std::string& server_ip,
                    uint16_t port, double timeout_secs) {
    SendResult result;

    socket_t sock = ::socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == SOCK_INVALID) return result;

    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(port);
    addr.sin_addr.s_addr = inet_addr(server_ip.c_str());

    // Send the query
    int sent = ::sendto(sock,
        reinterpret_cast<const char*>(query.data()),
        static_cast<int>(query.size()), 0,
        reinterpret_cast<sockaddr*>(&addr), sizeof(addr));

    if (sent == SOCK_ERR) { CLOSE_SOCK(sock); return result; }

    // Wait for response with select() timeout
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(sock, &fds);
    timeval tv{};
    tv.tv_sec  = static_cast<long>(timeout_secs);
    tv.tv_usec = static_cast<long>((timeout_secs - tv.tv_sec) * 1e6);

    int sel = ::select(static_cast<int>(sock) + 1, &fds, nullptr, nullptr, &tv);
    if (sel <= 0) { CLOSE_SOCK(sock); return result; }   // timeout or error

    // Receive (buffer up to 4096 — EDNS can exceed 512)
    static constexpr int RECV_BUF = 4096;
    std::vector<uint8_t> buf(RECV_BUF);
    int received = ::recvfrom(sock,
        reinterpret_cast<char*>(buf.data()),
        RECV_BUF, 0, nullptr, nullptr);

    CLOSE_SOCK(sock);

    if (received <= 0) return result;

    buf.resize(received);
    result.data       = std::move(buf);
    result.ok         = true;
    result.truncated  = (rd16(&result.data[2]) & FLAG_TC) != 0;
    return result;
}

// ─────────────────────────────────────────────────────────────────────────────
//  TCP transport  (RFC 1035 §4.2.2 — 2-byte length prefix)
// ─────────────────────────────────────────────────────────────────────────────

// Helper: read exactly n bytes from a TCP socket.
static bool tcp_recv_exact(socket_t sock, uint8_t* buf, int n) {
    int received = 0;
    while (received < n) {
        int r = ::recv(sock,
            reinterpret_cast<char*>(buf + received), n - received, 0);
        if (r <= 0) return false;
        received += r;
    }
    return true;
}

SendResult send_tcp(const std::vector<uint8_t>& query,
                    const std::string& server_ip,
                    uint16_t port, double timeout_secs) {
    SendResult result;

    socket_t sock = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == SOCK_INVALID) return result;

    // Set send/receive timeouts
#ifdef _WIN32
    DWORD tv_ms = static_cast<DWORD>(timeout_secs * 1000);
    ::setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO,
        reinterpret_cast<const char*>(&tv_ms), sizeof(tv_ms));
    ::setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO,
        reinterpret_cast<const char*>(&tv_ms), sizeof(tv_ms));
#else
    timeval tv{};
    tv.tv_sec  = static_cast<long>(timeout_secs);
    tv.tv_usec = 0;
    ::setsockopt(sock, SOL_SOCKET, SO_RCVTIMEO,
        reinterpret_cast<const char*>(&tv), sizeof(tv));
    ::setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO,
        reinterpret_cast<const char*>(&tv), sizeof(tv));
#endif

    sockaddr_in addr{};
    addr.sin_family      = AF_INET;
    addr.sin_port        = htons(port);
    addr.sin_addr.s_addr = inet_addr(server_ip.c_str());

    if (::connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
        CLOSE_SOCK(sock); return result;
    }

    // Prefix the query with a 2-byte big-endian length  (RFC 1035 §4.2.2)
    uint16_t qlen = htons(static_cast<uint16_t>(query.size()));
    ::send(sock, reinterpret_cast<const char*>(&qlen), 2, 0);
    ::send(sock, reinterpret_cast<const char*>(query.data()),
           static_cast<int>(query.size()), 0);

    // Read 2-byte response length
    uint8_t len_buf[2];
    if (!tcp_recv_exact(sock, len_buf, 2)) { CLOSE_SOCK(sock); return result; }
    uint16_t resp_len = static_cast<uint16_t>((len_buf[0] << 8) | len_buf[1]);

    // Read full response
    std::vector<uint8_t> buf(resp_len);
    if (!tcp_recv_exact(sock, buf.data(), resp_len)) {
        CLOSE_SOCK(sock); return result;
    }

    CLOSE_SOCK(sock);
    result.data     = std::move(buf);
    result.ok       = true;
    result.used_tcp = true;
    return result;
}

// Convenience: UDP first; if TC bit set, retry via TCP.
SendResult send_query(const std::vector<uint8_t>& query,
                      const std::string& server_ip, uint16_t port) {
    auto r = send_udp(query, server_ip, port);
    if (r.ok && r.truncated) {
        auto tr = send_tcp(query, server_ip, port);
        if (tr.ok) { tr.truncated = false; return tr; }
    }
    return r;
}

// ─────────────────────────────────────────────────────────────────────────────
//  LRU + TTL Cache implementation
// ─────────────────────────────────────────────────────────────────────────────
Cache::Cache(size_t max_entries) : max_(max_entries) {}

bool Cache::get(const std::string& key, Response& out) {
    std::lock_guard<std::mutex> lk(mtx_);
    auto it = idx_.find(key);
    if (it == idx_.end()) { ++misses_; return false; }

    auto& entry = it->second->second;
    auto  age   = std::chrono::steady_clock::now() - entry.stored_at;
    auto  age_s = std::chrono::duration_cast<std::chrono::seconds>(age).count();

    if (static_cast<uint32_t>(age_s) >= entry.ttl) {
        // Expired — evict
        lru_.erase(it->second);
        idx_.erase(it);
        ++misses_;
        return false;
    }

    // Move to front (most recently used)
    lru_.splice(lru_.begin(), lru_, it->second);
    ++hits_;
    out = entry.resp;
    return true;
}

void Cache::put(const std::string& key, const Response& res) {
    std::lock_guard<std::mutex> lk(mtx_);
    auto it = idx_.find(key);
    if (it != idx_.end()) {
        lru_.erase(it->second);
        idx_.erase(it);
    }
    if (lru_.size() >= max_) {
        // Evict least recently used
        auto last = std::prev(lru_.end());
        idx_.erase(last->first);
        lru_.pop_back();
    }
    Entry e;
    e.resp      = res;
    e.stored_at = std::chrono::steady_clock::now();
    e.ttl       = (res.min_ttl > 0) ? res.min_ttl : 60;
    lru_.push_front({key, std::move(e)});
    idx_[key] = lru_.begin();
}

void Cache::clear() {
    std::lock_guard<std::mutex> lk(mtx_);
    lru_.clear();
    idx_.clear();
    hits_ = misses_ = 0;
}

Cache::Stats Cache::stats() const {
    std::lock_guard<std::mutex> lk(mtx_);
    return { lru_.size(), hits_, misses_ };
}

// ─────────────────────────────────────────────────────────────────────────────
//  Recursive Resolver implementation
// ─────────────────────────────────────────────────────────────────────────────
Resolver::Resolver(Cache* cache) : cache_(cache) {}

// walk() — traverses the delegation chain from ns_ip down until an answer
//           (or authoritative NXDOMAIN) is found.
std::string Resolver::walk(const std::string& domain, uint16_t qtype,
                            const std::string& ns_ip,
                            std::vector<std::string>& path,
                            bool& used_tcp, int depth) {
    if (depth > MAX_REFERRALS) return "";

    auto query = build_query(domain, qtype, 0, false);  // RD=false for recursive walk

    path.push_back(ns_ip);
    auto sr = send_query(query, ns_ip);
    if (!sr.ok) return "";
    if (sr.used_tcp) used_tcp = true;

    Response resp;
    try {
        resp = parse_response(sr.data);
    } catch (...) { return ""; }

    // ── Answers ──────────────────────────────────────────────────────────────
    if (!resp.answers.empty()) {
        // Check for CNAME chain
        for (const auto& ans : resp.answers) {
            if (ans.type == TYPE_CNAME && qtype != TYPE_CNAME) {
                // Follow CNAME — restart from roots with the new name
                return walk(ans.data, qtype,
                    ROOT_SERVERS[std::rand() % NUM_ROOT_SERVERS],
                    path, used_tcp, depth + 1);
            }
            if (ans.type == qtype) return ans.data;
        }
        // If answers exist but none match qtype, return data of first answer
        return resp.answers[0].data;
    }

    // ── NXDOMAIN ─────────────────────────────────────────────────────────────
    if (resp.rcode == 3) return "";   // NXDOMAIN

    // ── NS referral (delegation) ──────────────────────────────────────────────
    if (resp.authorities.empty()) return "";

    // Build glue map: NS hostname → IP from additionals
    std::map<std::string, std::string> glue;
    for (const auto& add : resp.additionals)
        if (add.type == TYPE_A) glue[add.name] = add.data;

    // Try each NS in turn
    for (const auto& auth : resp.authorities) {
        if (auth.type != TYPE_NS) continue;
        const std::string& ns_name = auth.data;

        std::string next_ip;
        if (glue.count(ns_name)) {
            next_ip = glue[ns_name];                        // use glue record
        } else {
            next_ip = resolve_ns_name(ns_name, path, used_tcp);  // glue-less
        }

        if (!next_ip.empty()) {
            auto result = walk(domain, qtype, next_ip, path, used_tcp, depth + 1);
            if (!result.empty()) return result;
        }
    }

    return "";
}

// Resolve an NS hostname to an IP by restarting from the root servers.
std::string Resolver::resolve_ns_name(const std::string& ns_name,
                                       std::vector<std::string>& path,
                                       bool& used_tcp) {
    for (int i = 0; i < NUM_ROOT_SERVERS; ++i) {
        auto ip = walk(ns_name, TYPE_A, ROOT_SERVERS[i], path, used_tcp, 0);
        if (!ip.empty()) return ip;
    }
    return "";
}

ResolveResult Resolver::resolve(const std::string& domain, uint16_t qtype) {
    ResolveResult out;
    out.domain    = domain;
    out.qtype_str = type_to_str(qtype);

    auto t0 = std::chrono::steady_clock::now();

    // ── Cache check ───────────────────────────────────────────────────────────
    std::string cache_key = domain + "/" + type_to_str(qtype);
    if (cache_) {
        Response cached_resp;
        if (cache_->get(cache_key, cached_resp)) {
            out.success  = !cached_resp.answers.empty();
            out.cached   = true;
            out.answers  = cached_resp.answers;
            auto t1      = std::chrono::steady_clock::now();
            out.latency_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
            if (!out.success) out.error = "No answer records (cached)";
            return out;
        }
    }

    // ── Recursive resolution ──────────────────────────────────────────────────
    // Pick a random root server
    std::srand(static_cast<unsigned>(
        std::chrono::steady_clock::now().time_since_epoch().count()));
    int root_idx = std::rand() % NUM_ROOT_SERVERS;

    std::vector<std::string> path;
    bool used_tcp = false;
    std::string answer = walk(domain, qtype, ROOT_SERVERS[root_idx],
                               path, used_tcp, 0);

    auto t1        = std::chrono::steady_clock::now();
    out.latency_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    out.resolution_path = path;
    out.used_tcp   = used_tcp;

    if (!answer.empty()) {
        out.success = true;
        Record r;
        r.name = domain;
        r.type = qtype;
        r.data = answer;
        out.answers.push_back(r);

        // Store in cache
        if (cache_) {
            Response resp_to_cache;
            resp_to_cache.answers = out.answers;
            resp_to_cache.min_ttl = 300;
            cache_->put(cache_key, resp_to_cache);
        }
    } else {
        out.error = "Resolution failed — no authoritative answer for " + domain;
    }

    return out;
}

// ─────────────────────────────────────────────────────────────────────────────
//  JSON serialiser
// ─────────────────────────────────────────────────────────────────────────────
std::string result_to_json(const ResolveResult& r) {
    std::ostringstream o;
    o << "{\n";
    o << "  \"success\": "    << (r.success ? "true" : "false") << ",\n";
    o << "  \"domain\": "     << json_str(r.domain)             << ",\n";
    o << "  \"qtype\": "      << json_str(r.qtype_str)          << ",\n";
    o << "  \"cached\": "     << (r.cached ? "true" : "false")  << ",\n";
    o << "  \"used_tcp\": "   << (r.used_tcp ? "true" : "false")<< ",\n";
    o << std::fixed << std::setprecision(3);
    o << "  \"latency_ms\": " << r.latency_ms                   << ",\n";

    // answers array
    o << "  \"answers\": [\n";
    for (size_t i = 0; i < r.answers.size(); ++i) {
        const auto& a = r.answers[i];
        o << "    {\"name\": " << json_str(a.name)
          << ", \"type\": "    << json_str(type_to_str(a.type))
          << ", \"ttl\": "     << a.ttl
          << ", \"data\": "    << json_str(a.data) << "}";
        if (i + 1 < r.answers.size()) o << ",";
        o << "\n";
    }
    o << "  ],\n";

    // resolution_path array
    o << "  \"resolution_path\": [";
    for (size_t i = 0; i < r.resolution_path.size(); ++i) {
        o << json_str(r.resolution_path[i]);
        if (i + 1 < r.resolution_path.size()) o << ", ";
    }
    o << "]";

    if (!r.error.empty())
        o << ",\n  \"error\": " << json_str(r.error);

    o << "\n}\n";
    return o.str();
}

} // namespace dns

// ─────────────────────────────────────────────────────────────────────────────
//  main() — CLI entry point
//  Usage: dns_resolver <domain> [A|AAAA|NS|MX|CNAME|TXT]
// ─────────────────────────────────────────────────────────────────────────────
int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: dns_resolver <domain> [A|AAAA|NS|MX|CNAME|TXT]\n";
        return 1;
    }

    std::string domain   = argv[1];
    std::string type_str = (argc >= 3) ? argv[2] : "A";

    // Map type string to numeric
    std::map<std::string, uint16_t> type_map = {
        {"A",     dns::TYPE_A    },
        {"AAAA",  dns::TYPE_AAAA },
        {"NS",    dns::TYPE_NS   },
        {"MX",    dns::TYPE_MX   },
        {"CNAME", dns::TYPE_CNAME},
        {"TXT",   dns::TYPE_TXT  },
        {"PTR",   dns::TYPE_PTR  },
        {"SOA",   dns::TYPE_SOA  }
    };

    uint16_t qtype = dns::TYPE_A;
    auto it = type_map.find(type_str);
    if (it != type_map.end()) qtype = it->second;

    try {
        dns::net_init();
        dns::Cache  cache(1000);
        dns::Resolver resolver(&cache);

        auto result = resolver.resolve(domain, qtype);
        std::cout << dns::result_to_json(result);
        dns::net_cleanup();
        return result.success ? 0 : 1;
    } catch (const std::exception& e) {
        std::cout << "{\"success\": false, \"error\": "
                  << "\"" << e.what() << "\"}\n";
        dns::net_cleanup();
        return 1;
    }
}
