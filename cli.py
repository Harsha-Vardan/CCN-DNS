import sys
import argparse
import urllib.request
import urllib.parse
import json
import time

API_URL = "http://127.0.0.1:5000/resolve"

def print_banner():
    print("\033[96m" + "="*50)
    print("  CCN-DNS Command Line Interface")
    print("  Recursive Resolver & Path Visualizer")
    print("="*50 + "\033[0m\n")

def resolve_domain(domain, qtype="A"):
    params = urllib.parse.urlencode({'domain': domain, 'type': qtype})
    url = f"{API_URL}?{params}"

    try:
        req = urllib.request.urlopen(url, timeout=35)
        return json.loads(req.read())
    except urllib.error.URLError as e:
        return {"error": f"Failed to connect to API: {e.reason}", "domain": domain}
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except:
            return {"error": f"HTTP Error {e.code}", "domain": domain}
    except Exception as e:
        return {"error": str(e), "domain": domain}

def print_results(data, show_debug=False):
    if "error" in data:
        print(f"\033[91m[ERROR] Resolution failed for {data.get('domain', 'Unknown')}: {data['error']}\033[0m\n")
        return

    domain = data.get("domain", "")
    ip = data.get("ip", "—")
    latency = data.get("latency_ms", 0)
    is_cached = data.get("cached", False)
    used_tcp = data.get("used_tcp", False)
    path = data.get("resolution_path", [])
    note = data.get("note", "")

    # Colors
    C_GN = "\033[92m"
    C_CY = "\033[96m"
    C_YL = "\033[93m"
    C_MG = "\033[95m"
    C_R  = "\033[0m"

    status = f"{C_GN}[CACHED]{C_R}" if is_cached else f"{C_CY}[NETWORK]{C_R}"
    if note:
         status += f"  ({note})"

    print(f"{C_GN}[OK] Resolution Successful{C_R}")
    print(f"  - Domain:  {domain}")
    print(f"  - IP:      {C_GN}{ip}{C_R}")
    print(f"  - Latency: {C_YL}{latency} ms{C_R}")
    print(f"  - Status:  {status}")

    if show_debug:
        print(f"  - TCP Fallback: {'Yes' if used_tcp else 'No'}")
        answers = data.get("answers", [])
        if answers:
            print(f"  - Answers Details (Total: {len(answers)}):")
            for ans in answers:
                print(f"      [Type: {ans.get('type')}] {ans.get('name')} -> {ans.get('data')} (TTL: {ans.get('ttl')})")

    if path:
        print(f"\n{C_MG}[PATH] Resolution Path:{C_R}")
        if len(path) == 1:
             print(f"    Your Computer -> {path[0]} -> {ip}")
        else:
             formatted_path = " -> ".join(path)
             print(f"    {formatted_path} -> {ip}")
             
    print("-" * 50 + "\n")

def main():
    parser = argparse.ArgumentParser(description="CCN-DNS Terminal Client")
    parser.add_argument("domains", nargs="+", help="One or more domains to resolve")
    parser.add_argument("-t", "--type", default="A", help="DNS Record Type (A, AAAA, MX, NS, etc.)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    parser.add_argument("--debug", action="store_true", help="Show full debug info including all answer records and TCP status")
    
    args = parser.parse_args()

    if not args.json:
        print_banner()

    for idx, domain in enumerate(args.domains):
        if not args.json:
             print(f"Querying CCN-DNS API for {C_YL}{domain}{C_R} (Type: {args.type})...")
             
        result = resolve_domain(domain, args.type)
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print_results(result, show_debug=args.debug)

    if not args.json and len(args.domains) > 1:
        print(f"\033[92mCompleted lookup for {len(args.domains)} domains.\033[0m")

if __name__ == "__main__":
    # Ensure color codes work in windows terminal
    import os
    os.system('color')
    # Make C_YL globally available for main scope message
    C_YL = "\033[93m"
    C_R  = "\033[0m"
    main()
