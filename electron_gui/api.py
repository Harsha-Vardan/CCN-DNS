import sys
import os
import json
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add project root to path to import dns_resolver
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dns_resolver.resolver_api import ResolverAPI
from dns_resolver.packet import build_dns_query
from dns_resolver.utils import hex_dump
from dns_resolver.config import *

app = Flask(__name__)
CORS(app)  # Enable CORS for Electron

resolver = ResolverAPI()

@app.route('/resolve', methods=['POST'])
def resolve():
    data = request.json
    domain = data.get('domain', 'google.com')
    record_type_str = data.get('type', 'A')
    mode = data.get('mode', 'auto')
    
    type_map = {
        "A": TYPE_A, "AAAA": TYPE_AAAA, "NS": TYPE_NS, 
        "CNAME": TYPE_CNAME, "MX": TYPE_MX, "TXT": TYPE_TXT, 
        "PTR": TYPE_PTR, "SOA": TYPE_SOA
    }
    record_type = type_map.get(record_type_str, TYPE_A)
    
    try:
        # Debug: Print stats before resolve
        stats = resolver.cache.get_stats()
        print(f"Before Resolve - Hits: {stats.get('hits', '?')}, Misses: {stats.get('misses', '?')}")
        
        result = resolver.resolve(domain, record_type, mode)
        
        # Debug: Print stats after resolve
        stats = resolver.cache.get_stats()
        print(f"After Resolve - Hits: {stats.get('hits', '?')}, Misses: {stats.get('misses', '?')}")
        
        return jsonify(result)
    except Exception as e:
        print(f"Error resolving: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/cache', methods=['GET'])
def get_cache():
    cache_data = []
    current_time = time.time()
    
    # Access the internal cache storage
    # Key is (domain, type), Value is (record, timestamp)
    for key, value in resolver.cache.get_all():
        domain, rtype = key
        record, timestamp = value
        
        ttl = record.get('ttl', 300)
        age = current_time - timestamp
        remaining_ttl = max(0, ttl - age)
        
        cache_data.append({
            'domain': domain,
            'type': rtype,
            'ttl': int(remaining_ttl),
            'status': 'Valid' if remaining_ttl > 0 else 'Expired'
        })
        
    return jsonify({
        'stats': resolver.cache.get_stats(),
        'entries': cache_data
    })

@app.route('/cache', methods=['DELETE'])
def clear_cache():
    resolver.cache.clear()
    return jsonify({'message': 'Cache cleared successfully'})

@app.route('/packet', methods=['POST'])
def generate_packet():
    data = request.json
    domain = data.get('domain', 'example.com')
    rtype_str = data.get('type', 'A')
    
    type_map = {
        "A": TYPE_A, "AAAA": TYPE_AAAA, "NS": TYPE_NS, "MX": TYPE_MX
    }
    rtype = type_map.get(rtype_str, TYPE_A)
    
    try:
        packet = build_dns_query(domain, rtype)
        dump = hex_dump(packet)
        return jsonify({'hex_dump': dump})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

from dns_resolver.transport_udp import send_udp_query

@app.route('/benchmark', methods=['POST'])
def run_benchmark():
    # Get unique (domain, type) pairs from cache
    # Filter out expired entries to avoid cache misses during benchmark
    valid_cached_items = []
    current_time = time.time()
    
    # We need to iterate a copy because accessing cache might mutate it (if we used get)
    # But here we are accessing the dict directly.
    for key, value in resolver.cache.get_all():
        record, timestamp = value
        ttl = record.get('ttl', 300)
        # Add 5 second safety buffer to ensure it doesn't expire during benchmark
        if current_time - timestamp < (ttl - 5):
            valid_cached_items.append(key)
            
    if not valid_cached_items:
        return jsonify({'results': [], 'message': 'Cache is empty or all items expired. Perform lookups!'})
        
    results = []
    
    # Reverse map for display
    type_to_str = {v: k for k, v in {
        "A": TYPE_A, "AAAA": TYPE_AAAA, "NS": TYPE_NS, 
        "CNAME": TYPE_CNAME, "MX": TYPE_MX, "TXT": TYPE_TXT, 
        "PTR": TYPE_PTR, "SOA": TYPE_SOA
    }.items()}
    
    for domain, rtype in valid_cached_items:
        type_str = type_to_str.get(rtype, str(rtype))
        display_name = f"{domain} ({type_str})"
        row = {'domain': display_name}
        
        # 1. Local Resolver
        start = time.time()
        try:
            # Use the EXACT type from cache to guarantee a hit
            res = resolver.resolve(domain, rtype, mode='auto')
            
            if 'error' in res:
                row['local'] = f"Err: {res['error']}"
            else:
                row['local'] = (time.time() - start) * 1000
        except Exception as e:
            row['local'] = f"Exc: {str(e)}"
            
        # Prepare packet for external queries
        try:
            packet = build_dns_query(domain, rtype)
            
            # 2. Google DNS (8.8.8.8)
            start = time.time()
            resp = send_udp_query(packet, '8.8.8.8', timeout=2.0)
            if resp:
                row['google'] = (time.time() - start) * 1000
            else:
                row['google'] = -1
                
            # 3. Cloudflare DNS (1.1.1.1)
            start = time.time()
            resp = send_udp_query(packet, '1.1.1.1', timeout=2.0)
            if resp:
                row['cloudflare'] = (time.time() - start) * 1000
            else:
                row['cloudflare'] = -1
                
        except Exception as e:
            print(f"Benchmark error for {domain}: {e}")
            row['google'] = -1
            row['cloudflare'] = -1
            
        results.append(row)
        
    return jsonify({'results': results})

if __name__ == '__main__':
    app.run(port=5000)
