import sys
import urllib.request
import urllib.parse
import json
import time

API_URL = "http://127.0.0.1:5000/resolve"

def print_banner():
    print("\033[96m" + "="*50)
    print("  CCN-DNS Command Line Interface")
    print("  Recursive Resolver & Path Visualizer")
    print("="*50 + "\033[0m")

def resolve_domain(domain, qtype="A"):
    # Build URL with query params
    params = urllib.parse.urlencode({'domain': domain, 'type': qtype})
    url = f"{API_URL}?{params}"

    try:
        req = urllib.request.urlopen(url, timeout=35)
        data = json.loads(req.read())
        return data
    except urllib.error.URLError as e:
        print(f"\033[91m[ERROR] Failed to connect to CCN-DNS API: {e.reason}\033[0m")
        print("Make sure the API server is running (python api/server.py)")
        sys.exit(1)
    except urllib.error.HTTPError as e:
        error_msg = json.loads(e.read()).get("error", "Unknown API Error")
        print(f"\033[91m[ERROR] Resolution failed: {error_msg}\033[0m")
        sys.exit(1)
    except Exception as e:
        print(f"\033[91m[ERROR] Unexpected error: {e}\033[0m")
        sys.exit(1)

def print_results(data):
    # Extract info
    domain = data.get("domain", "")
    ip = data.get("ip", "—")
    latency = data.get("latency_ms", 0)
    is_cached = data.get("cached", False)
    path = data.get("resolution_path", [])
    note = data.get("note", "")

    # Formatting colors
    C_GN = "\033[92m" # Green
    C_CY = "\033[96m" # Cyan
    C_YL = "\033[93m" # Yellow
    C_MG = "\033[95m" # Magenta
    C_R  = "\033[0m"  # Reset

    status = f"{C_GN}[CACHED]{C_R}" if is_cached else f"{C_CY}[NETWORK]{C_R}"
    if note:
         status += f"  ({note})"

    print(f"\n{C_GN}[OK] Resolution Successful{C_R}")
    print(f"  - Domain:  {domain}")
    print(f"  - IP:      {C_GN}{ip}{C_R}")
    print(f"  - Latency: {C_YL}{latency} ms{C_R}")
    print(f"  - Status:  {status}")

    if path:
        print(f"\n{C_MG}[PATH] Resolution Path:{C_R}")
        if len(path) == 1:
             print(f"    Your Computer -> {path[0]} -> {ip}")
        else:
             formatted_path = " -> ".join(path)
             print(f"    {formatted_path} -> {ip}")
    
    print("\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: python cli.py <domain> [record_type]")
        print("Example: python cli.py google.com")
        print("Example: python cli.py github.com MX")
        sys.exit(1)

    domain = sys.argv[1]
    qtype = sys.argv[2].upper() if len(sys.argv) > 2 else "A"

    print_banner()
    print(f"Querying CCN-DNS API for {domain} (Type: {qtype})...\n")
    
    start_time = time.time()
    
    # Do the resolution
    result = resolve_domain(domain, qtype)
    
    # Print the pretty results
    print_results(result)

if __name__ == "__main__":
    main()
