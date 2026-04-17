#pragma once

// ─────────────────────────────────────────────────────────────────────────────
//  dns_resolver.h
//  RFC 1035-compliant Recursive DNS Resolver — C++ Header
//  Implements: packet build/parse, UDP+TCP transport, LRU+TTL cache,
//              recursive resolution (root → TLD → authoritative)
// ─────────────────────────────────────────────────────────────────────────────

#include <cstdint>
#include <string>
#include <vector>
#include <map>
#include <list>
#include <mutex>
#include <chrono>
#include <stdexcept>

namespace dns {

// ═════════════════════════════════════════════════════════════════════════════
//  Constants  (RFC 1035)
// ═════════════════════════════════════════════════════════════════════════════

// Record types
constexpr uint16_t TYPE_A     =  1;
constexpr uint16_t TYPE_NS    =  2;
constexpr uint16_t TYPE_CNAME =  5;
constexpr uint16_t TYPE_SOA   =  6;
constexpr uint16_t TYPE_PTR   = 12;
constexpr uint16_t TYPE_MX    = 15;
constexpr uint16_t TYPE_TXT   = 16;
constexpr uint16_t TYPE_AAAA  = 28;
constexpr uint16_t CLASS_IN   =  1;

// Header flag bits
constexpr uint16_t FLAG_QR   = 0x8000;   // Query / Response
constexpr uint16_t FLAG_AA   = 0x0400;   // Authoritative Answer
constexpr uint16_t FLAG_TC   = 0x0200;   // Truncated
constexpr uint16_t FLAG_RD   = 0x0100;   // Recursion Desired
constexpr uint16_t FLAG_RA   = 0x0080;   // Recursion Available
constexpr uint16_t RCODE_MASK= 0x000F;

// Protocol limits
constexpr int  MAX_UDP_PAYLOAD = 512;    // RFC 1035 §2.3.4
constexpr int  MAX_JUMPS       = 128;    // compression-pointer loop guard
constexpr int  MAX_REFERRALS   = 30;     // delegation depth guard
constexpr int  MAX_CNAME_DEPTH = 10;

// ═════════════════════════════════════════════════════════════════════════════
//  Data structures
// ═════════════════════════════════════════════════════════════════════════════

// One parsed resource record.
struct Record {
    std::string name;
    uint16_t    type    = 0;
    uint16_t    cls     = CLASS_IN;
    uint32_t    ttl     = 0;
    std::string data;            // human-readable value
};

// Full parsed DNS response.
struct Response {
    uint16_t            id          = 0;
    uint16_t            flags       = 0;
    uint8_t             rcode       = 0;
    bool                truncated   = false;
    bool                authoritative = false;
    std::vector<Record> answers;
    std::vector<Record> authorities;
    std::vector<Record> additionals;
    uint32_t            min_ttl     = 300;   // minimum TTL across all answers
};

// ═════════════════════════════════════════════════════════════════════════════
//  Thread-safe LRU + TTL cache
// ═════════════════════════════════════════════════════════════════════════════

class Cache {
public:
    struct Stats { size_t size, hits, misses; };

    explicit Cache(size_t max_entries = 1000);

    // Returns true and populates `out` on a valid (non-expired) hit.
    bool get(const std::string& key, Response& out);

    // Stores a response; effective TTL = response.min_ttl.
    void put(const std::string& key, const Response& res);

    void  clear();
    Stats stats() const;

private:
    struct Entry {
        Response                              resp;
        std::chrono::steady_clock::time_point stored_at;
        uint32_t                              ttl;
    };
    using List  = std::list<std::pair<std::string, Entry>>;
    using Index = std::map<std::string, List::iterator>;

    mutable std::mutex mtx_;
    size_t             max_;
    List               lru_;
    Index              idx_;
    size_t             hits_   = 0;
    size_t             misses_ = 0;
};

// ═════════════════════════════════════════════════════════════════════════════
//  Packet builder
// ═════════════════════════════════════════════════════════════════════════════

// Builds a raw DNS query packet (RFC 1035 §4).
// id == 0  →  a random 16-bit ID is generated.
// rd       →  set the Recursion Desired bit.
std::vector<uint8_t> build_query(const std::string& domain,
                                  uint16_t           qtype,
                                  uint16_t           id = 0,
                                  bool               rd = false);

// Encodes a dotted domain name to DNS wire format (§3.1).
std::vector<uint8_t> encode_name(const std::string& domain);

// ═════════════════════════════════════════════════════════════════════════════
//  Packet parser
// ═════════════════════════════════════════════════════════════════════════════

// Parses a raw DNS response packet.
// Throws std::runtime_error if the packet is malformed.
Response parse_response(const std::vector<uint8_t>& data);

// ═════════════════════════════════════════════════════════════════════════════
//  Transport  (UDP + TCP)
// ═════════════════════════════════════════════════════════════════════════════

struct SendResult {
    std::vector<uint8_t> data;
    bool ok        = false;
    bool truncated = false;    // TC bit was set → caller must retry via TCP
    bool used_tcp  = false;
};

// Send via UDP.  Returns empty data on timeout / error.
SendResult send_udp(const std::vector<uint8_t>& query,
                    const std::string&           server_ip,
                    uint16_t                     port         = 53,
                    double                       timeout_secs = 3.0);

// Send via TCP with RFC 1035 §4.2.2 two-byte length prefix.
SendResult send_tcp(const std::vector<uint8_t>& query,
                    const std::string&           server_ip,
                    uint16_t                     port         = 53,
                    double                       timeout_secs = 5.0);

// Convenience: UDP first; if TC bit set, retries via TCP automatically.
SendResult send_query(const std::vector<uint8_t>& query,
                      const std::string&           server_ip,
                      uint16_t                     port = 53);

// ═════════════════════════════════════════════════════════════════════════════
//  Recursive resolver
// ═════════════════════════════════════════════════════════════════════════════

struct ResolveResult {
    bool                     success     = false;
    std::string              domain;
    std::string              qtype_str;
    std::vector<Record>      answers;
    std::vector<std::string> resolution_path;   // IPs queried in order
    bool                     cached      = false;
    bool                     used_tcp    = false;
    double                   latency_ms  = 0.0;
    std::string              error;
};

class Resolver {
public:
    // cache may be nullptr — resolver will then skip caching.
    explicit Resolver(Cache* cache = nullptr);

    ResolveResult resolve(const std::string& domain,
                          uint16_t           qtype = TYPE_A);

private:
    Cache* cache_;

    // Walk the delegation chain starting from ns_ip; returns first answer IP
    // found (or empty string on failure).
    std::string walk(const std::string&        domain,
                     uint16_t                   qtype,
                     const std::string&         ns_ip,
                     std::vector<std::string>&  path,
                     bool&                      used_tcp,
                     int                        depth = 0);

    // Resolve an NS name to its IP (used when no glue record is available).
    std::string resolve_ns_name(const std::string&        ns_name,
                                std::vector<std::string>& path,
                                bool&                     used_tcp);
};

// ═════════════════════════════════════════════════════════════════════════════
//  Utilities
// ═════════════════════════════════════════════════════════════════════════════

std::string type_to_str(uint16_t type);
std::string result_to_json(const ResolveResult& r);

// Platform socket initialisation (WSAStartup on Windows, no-op on POSIX).
void net_init();
void net_cleanup();

} // namespace dns
