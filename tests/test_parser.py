import unittest
import struct
from dns_resolver.parser import parse_dns_response
from dns_resolver.config import *

class TestParser(unittest.TestCase):
    def test_parse_response(self):
        # Mock a simple response packet
        # Header: ID=1234, QR=1, ANCOUNT=1
        header = struct.pack('!HHHHHH', 1234, 0x8180, 1, 1, 0, 0)
        
        # Question: google.com A IN
        question = b'\x06google\x03com\x00' + struct.pack('!HH', TYPE_A, CLASS_IN)
        
        # Answer: google.com A IN TTL=300 1.2.3.4
        # Name is a pointer to offset 12 (0xC00C)
        answer = b'\xc0\x0c' + struct.pack('!HHIH', TYPE_A, CLASS_IN, 300, 4) + b'\x01\x02\x03\x04'
        
        data = header + question + answer
        
        parsed = parse_dns_response(data)
        
        self.assertEqual(parsed['id'], 1234)
        self.assertEqual(len(parsed['answers']), 1)
        self.assertEqual(parsed['answers'][0]['name'], 'google.com')
        self.assertEqual(parsed['answers'][0]['data'], '1.2.3.4')

if __name__ == '__main__':
    unittest.main()
