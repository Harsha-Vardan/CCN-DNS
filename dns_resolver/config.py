
# Root Server Hints (A Records)
ROOT_SERVERS = {
    'a.root-servers.net': '198.41.0.4',
    'b.root-servers.net': '199.9.14.201',
    'c.root-servers.net': '192.33.4.12',
    'd.root-servers.net': '199.7.91.13',
    'e.root-servers.net': '192.203.230.10',
    'f.root-servers.net': '192.5.5.241',
    'g.root-servers.net': '192.112.36.4',
    'h.root-servers.net': '198.97.190.53',
    'i.root-servers.net': '192.36.148.17',
    'j.root-servers.net': '192.58.128.30',
    'k.root-servers.net': '193.0.14.129',
    'l.root-servers.net': '199.7.83.42',
    'm.root-servers.net': '202.12.27.33'
}

# Default Forwarder (Google DNS)
DEFAULT_FORWARDER = '8.8.8.8'

# DoH Providers
DOH_PROVIDERS = {
    'google': 'https://dns.google/dns-query',
    'cloudflare': 'https://cloudflare-dns.com/dns-query'
}

# Timeouts and Retries
TIMEOUT = 3.0  # seconds
MAX_RETRIES = 3

# Cache Configuration
CACHE_SIZE = 1000
DEFAULT_TTL = 300  # seconds
CACHE_BACKEND = 'mongodb'  # Options: 'memory', 'mongodb', 'postgresql'

# MongoDB Configuration
MONGO_URI = 'mongodb://localhost:27017/'
MONGO_DB_NAME = 'dns_resolver'

# PostgreSQL Configuration
POSTGRES_URI = 'postgresql://user:password@localhost:5432/dns_resolver'

# DNS Record Types
TYPE_A = 1
TYPE_NS = 2
TYPE_CNAME = 5
TYPE_SOA = 6
TYPE_PTR = 12
TYPE_MX = 15
TYPE_TXT = 16
TYPE_AAAA = 28

# DNS Classes
CLASS_IN = 1

# DNS Flags
QR_QUERY = 0
QR_RESPONSE = 1
OPCODE_QUERY = 0
AA_FLAG = 0x0400
TC_FLAG = 0x0200
RD_FLAG = 0x0100
RA_FLAG = 0x0080
RCODE_NOERROR = 0
RCODE_NXDOMAIN = 3
