import socket
from .config import *
from .utils import get_logger

logger = get_logger(__name__)

def send_udp_query(query_packet, server_ip, port=53, timeout=TIMEOUT):
    """
    Sends a DNS query via UDP and waits for a response.
    
    Args:
        query_packet (bytes): The raw DNS query packet.
        server_ip (str): The IP address of the DNS server.
        port (int): The port to connect to (default 53).
        timeout (float): The socket timeout in seconds.
        
    Returns:
        bytes: The raw DNS response packet, or None if failed.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    
    try:
        sock.sendto(query_packet, (server_ip, port))
        data, _ = sock.recvfrom(4096)  # Standard DNS packet size limit is 512, but EDNS can be larger
        return data
    except socket.timeout:
        logger.warning(f"Timeout querying {server_ip}")
        return None
    except Exception as e:
        logger.error(f"Error querying {server_ip}: {e}")
        return None
    finally:
        sock.close()
