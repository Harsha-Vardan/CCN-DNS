import unittest
import struct
from dns_resolver.packet import build_dns_query, encode_qname, decode_flags
from dns_resolver.config import *

class TestPacket(unittest.TestCase):
    def test_encode_qname(self):
        self.assertEqual(encode_qname("google.com"), b'\x06google\x03com\x00')
        self.assertEqual(encode_qname("."), b'\x00')

    def test_build_dns_query(self):
        query = build_dns_query("google.com", TYPE_A, recursion_desired=True)
        self.assertTrue(len(query) > 12)
        
        # Check header
        header = query[:12]
        id, flags, qd, an, ns, ar = struct.unpack('!HHHHHH', header)
        self.assertEqual(qd, 1)
        self.assertEqual(flags & RD_FLAG, RD_FLAG)

    def test_decode_flags(self):
        flags = 0x8180 # QR=1, RD=1, RA=1
        decoded = decode_flags(flags)
        self.assertEqual(decoded['QR'], 1)
        self.assertEqual(decoded['RD'], 1)
        self.assertEqual(decoded['RA'], 1)

if __name__ == '__main__':
    unittest.main()
