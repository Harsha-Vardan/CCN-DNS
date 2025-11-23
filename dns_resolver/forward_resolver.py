from .config import *
from .utils import get_logger
from .packet import build_dns_query
from .parser import parse_dns_response
from .transport_udp import send_udp_query

logger = get_logger(__name__)

class ForwardResolver:
    def __init__(self, forwarder=DEFAULT_FORWARDER):
        self.forwarder = forwarder

    def resolve(self, domain, record_type=TYPE_A):
        """
        Forwards the query to an upstream DNS server.
        """
        logger.info(f"Forwarding query for {domain} to {self.forwarder}")
        
        # Build query with RD=1 (Recursion Desired)
        query = build_dns_query(domain, record_type, recursion_desired=True)
        
        # Send query
        response_data = send_udp_query(query, self.forwarder)
        
        if not response_data:
            logger.error(f"No response from forwarder {self.forwarder}")
            return None
            
        # Parse response
        return parse_dns_response(response_data)
