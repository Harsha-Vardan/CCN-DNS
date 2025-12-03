import time
import sys
import os
from dns_resolver.resolver_api import ResolverAPI
from dns_resolver.transport_udp import send_udp_query
from dns_resolver.packet import build_dns_query
from dns_resolver.config import CACHE_BACKEND

def benchmark_domain(domain, resolver):
    print(f"\nBenchmarking {domain}...")
    
    # 1. Cold Cache (Local)
    # Ensure it's not in cache
    resolver.cache.clear()
    start = time.time()
    resolver.resolve(domain)
    cold_time = (time.time() - start) * 1000
    print(f"  Local (Cold):      {cold_time:.2f} ms")

    # 2. Warm Cache (Local)
    start = time.time()
    resolver.resolve(domain)
    warm_time = (time.time() - start) * 1000
    print(f"  Local (Warm):      {warm_time:.2f} ms")

    # Prepare packet for public DNS
    packet = build_dns_query(domain, 1) # A record

    # 3. Google DNS
    start = time.time()
    send_udp_query(packet, '8.8.8.8', timeout=2.0)
    google_time = (time.time() - start) * 1000
    print(f"  Google (8.8.8.8):  {google_time:.2f} ms")

    # 4. Cloudflare DNS
    start = time.time()
    send_udp_query(packet, '1.1.1.1', timeout=2.0)
    cf_time = (time.time() - start) * 1000
    print(f"  Cloudflare (1.1.1.1): {cf_time:.2f} ms")

    return warm_time, google_time, cf_time

def main():
    print(f"Starting Benchmark (Backend: {CACHE_BACKEND})...")
    resolver = ResolverAPI()
    
    domains = ['google.com', 'example.com', 'wikipedia.org']
    
    for domain in domains:
        benchmark_domain(domain, resolver)

if __name__ == "__main__":
    main()
