import struct
import io
import socket
from .config import *
from .utils import get_logger

logger = get_logger(__name__)

def parse_dns_response(data):
    """
    Parses a raw DNS response packet.
    
    Args:
        data (bytes): The raw DNS response data.
        
    Returns:
        dict: A dictionary containing the parsed response.
    """
    reader = io.BytesIO(data)
    
    # 1. Header
    header_data = reader.read(12)
    if len(header_data) < 12:
        raise ValueError("Packet too short")
        
    id, flags, qdcount, ancount, nscount, arcount = struct.unpack('!HHHHHH', header_data)
    
    parsed_flags = {
        'QR': (flags >> 15) & 1,
        'AA': (flags >> 10) & 1,
        'RA': (flags >> 7) & 1,
        'RCODE': flags & 0xF
    }
    
    result = {
        'id': id,
        'flags': parsed_flags,
        'questions': [],
        'answers': [],
        'authorities': [],
        'additionals': []
    }
    
    # 2. Question Section
    for _ in range(qdcount):
        qname = read_name(reader, data)
        qtype, qclass = struct.unpack('!HH', reader.read(4))
        result['questions'].append({'name': qname, 'type': qtype, 'class': qclass})
        
    # 3. Answer Section
    for _ in range(ancount):
        result['answers'].append(parse_record(reader, data))
        
    # 4. Authority Section
    for _ in range(nscount):
        result['authorities'].append(parse_record(reader, data))
        
    # 5. Additional Section
    for _ in range(arcount):
        result['additionals'].append(parse_record(reader, data))
        
    # Calculate effective TTL (min of all answers)
    if result['answers']:
        min_ttl = min(r['ttl'] for r in result['answers'])
        result['ttl'] = min_ttl
    else:
        result['ttl'] = 300 # Default if no answers
        
    return result

def read_name(reader, data):
    """
    Reads a domain name from the stream, handling compression pointers.
    """
    parts = []
    while True:
        length_byte = reader.read(1)
        if not length_byte:
            break
        length = ord(length_byte)
        
        if length == 0:
            break
            
        if length & 0xC0 == 0xC0:  # Compression pointer
            pointer_byte = reader.read(1)
            if not pointer_byte:
                break
            offset = ((length & 0x3F) << 8) | ord(pointer_byte)
            
            # Save current position
            current_pos = reader.tell()
            
            # Jump to pointer
            reader.seek(offset)
            parts.append(read_name(reader, data))
            
            # Restore position
            reader.seek(current_pos)
            break
        else:
            parts.append(reader.read(length).decode('utf-8', errors='ignore'))
            
    return '.'.join(parts)

def parse_record(reader, data):
    """
    Parses a single resource record.
    """
    name = read_name(reader, data)
    rtype, rclass, ttl, rdlength = struct.unpack('!HHIH', reader.read(10))
    
    rdata_raw = reader.read(rdlength)
    rdata = parse_rdata(rtype, rdata_raw, data, reader.tell() - rdlength)
    
    return {
        'name': name,
        'type': rtype,
        'class': rclass,
        'ttl': ttl,
        'data': rdata
    }

def parse_rdata(rtype, rdata_raw, full_packet, offset):
    """
    Parses the RDATA field based on record type.
    """
    if rtype == TYPE_A:
        return socket.inet_ntoa(rdata_raw)
    elif rtype == TYPE_AAAA:
        return socket.inet_ntop(socket.AF_INET6, rdata_raw)
    elif rtype in (TYPE_NS, TYPE_CNAME, TYPE_PTR):
        # These contain names, which might be compressed relative to the full packet
        # We need a reader at the correct offset
        sub_reader = io.BytesIO(full_packet)
        sub_reader.seek(offset)
        return read_name(sub_reader, full_packet)
    elif rtype == TYPE_MX:
        preference = struct.unpack('!H', rdata_raw[:2])[0]
        sub_reader = io.BytesIO(full_packet)
        sub_reader.seek(offset + 2)
        exchange = read_name(sub_reader, full_packet)
        return {'preference': preference, 'exchange': exchange}
    elif rtype == TYPE_TXT:
        # TXT records are length-prefixed strings
        txt_len = rdata_raw[0]
        return rdata_raw[1:1+txt_len].decode('utf-8', errors='ignore')
    elif rtype == TYPE_SOA:
        sub_reader = io.BytesIO(full_packet)
        sub_reader.seek(offset)
        mname = read_name(sub_reader, full_packet)
        rname = read_name(sub_reader, full_packet)
        serial, refresh, retry, expire, minimum = struct.unpack('!IIIII', sub_reader.read(20))
        return {
            'mname': mname,
            'rname': rname,
            'serial': serial,
            'refresh': refresh,
            'retry': retry,
            'expire': expire,
            'minimum': minimum
        }
    else:
        return rdata_raw
