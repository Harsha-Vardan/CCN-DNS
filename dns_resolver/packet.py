import struct
import random
from .config import *

def build_dns_query(domain, record_type=TYPE_A, recursion_desired=True):
    """
    Builds a standard DNS query packet.
    
    Args:
        domain (str): The domain name to query.
        record_type (int): The DNS record type (default A).
        recursion_desired (bool): Whether to set the RD flag.
        
    Returns:
        bytes: The raw DNS query packet.
    """
    # 1. Transaction ID (16 bits)
    transaction_id = random.randint(0, 65535)
    
    # 2. Flags (16 bits)
    # QR=0 (Query), Opcode=0 (Standard), AA=0, TC=0, RD=1/0, RA=0, Z=0, RCODE=0
    flags = 0
    if recursion_desired:
        flags |= RD_FLAG
        
    # 3. Counts
    qdcount = 1  # One question
    ancount = 0
    nscount = 0
    arcount = 0
    
    header = struct.pack('!HHHHHH', transaction_id, flags, qdcount, ancount, nscount, arcount)
    
    # 4. Question Section
    qname = encode_qname(domain)
    qtype = record_type
    qclass = CLASS_IN
    
    question = qname + struct.pack('!HH', qtype, qclass)
    
    return header + question

def encode_qname(domain):
    """
    Encodes a domain name into DNS wire format (e.g., "google.com" -> \x06google\x03com\x00).
    """
    parts = domain.split('.')
    encoded = b''
    for part in parts:
        if not part: continue
        encoded += struct.pack('B', len(part)) + part.encode('utf-8')
    encoded += b'\x00'  # Terminating zero
    return encoded

def decode_flags(flags):
    """
    Decodes the 16-bit flags field into a dictionary.
    """
    return {
        'QR': (flags >> 15) & 1,
        'Opcode': (flags >> 11) & 0xF,
        'AA': (flags >> 10) & 1,
        'TC': (flags >> 9) & 1,
        'RD': (flags >> 8) & 1,
        'RA': (flags >> 7) & 1,
        'Z': (flags >> 4) & 0x7,
        'RCODE': flags & 0xF
    }
