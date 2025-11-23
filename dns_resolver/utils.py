import logging
import socket
import struct

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    """Returns a logger instance with the given name."""
    return logging.getLogger(name)

def is_valid_ip(ip):
    """Checks if the given string is a valid IPv4 address."""
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False

def is_valid_domain(domain):
    """Checks if the given string is a valid domain name."""
    if len(domain) > 255:
        return False
    if domain[-1] == ".":
        domain = domain[:-1]
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.")
    return all(c in allowed for c in domain)

def hex_dump(data):
    """Returns a hex dump of the given binary data."""
    return " ".join("{:02x}".format(c) for c in data)
