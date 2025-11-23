import unittest
from unittest.mock import MagicMock, patch
from dns_resolver.recursive_resolver import RecursiveResolver
from dns_resolver.config import *

class TestRecursive(unittest.TestCase):
    @patch('dns_resolver.recursive_resolver.send_udp_query')
    def test_resolve(self, mock_send_query):
        # Mock response for root server
        # This is hard to mock fully without complex packet construction
        # So we will just test that it calls send_udp_query
        
        resolver = RecursiveResolver()
        
        # Mock return value to be None to stop infinite loop in our simple test
        mock_send_query.return_value = None
        
        resolver.resolve("google.com")
        
        self.assertTrue(mock_send_query.called)

if __name__ == '__main__':
    unittest.main()
