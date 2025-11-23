import unittest
from unittest.mock import MagicMock, patch
from dns_resolver.forward_resolver import ForwardResolver
from dns_resolver.config import *

class TestForward(unittest.TestCase):
    @patch('dns_resolver.forward_resolver.send_udp_query')
    @patch('dns_resolver.forward_resolver.parse_dns_response')
    def test_resolve(self, mock_parse, mock_send):
        resolver = ForwardResolver()
        
        mock_send.return_value = b'some_data'
        mock_parse.return_value = {'answers': []}
        
        resolver.resolve("google.com")
        
        mock_send.assert_called_with(unittest.mock.ANY, '8.8.8.8')
        self.assertTrue(mock_parse.called)

if __name__ == '__main__':
    unittest.main()
