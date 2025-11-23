import unittest
from unittest.mock import MagicMock, patch
from dns_resolver.transport_doh import send_doh_query

class TestDoH(unittest.TestCase):
    @patch('requests.post')
    def test_doh_query(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'some_data'
        mock_post.return_value = mock_response
        
        result = send_doh_query(b'query_packet')
        
        self.assertEqual(result, b'some_data')
        self.assertTrue(mock_post.called)

if __name__ == '__main__':
    unittest.main()
