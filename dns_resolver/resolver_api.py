import time
from .config import *
from .utils import get_logger
from .recursive_resolver import RecursiveResolver
from .forward_resolver import ForwardResolver
from .transport_doh import send_doh_query
from .parser import parse_dns_response
from .packet import build_dns_query
from .cache import DNSCache
from .metrics import Metrics
from .dnssec import get_dnssec_info

logger = get_logger(__name__)

class ResolverAPI:
    def __init__(self):
        self.recursive_resolver = RecursiveResolver()
        self.forward_resolver = ForwardResolver()
        self.cache = DNSCache()
        self.metrics = Metrics()

    def resolve(self, domain, record_type=TYPE_A, mode='auto'):
        """
        Resolves a domain name using the specified mode.
        
        Args:
            domain (str): The domain name.
            record_type (int): The record type.
            mode (str): 'auto', 'recursive', 'forward', 'doh'.
            
        Returns:
            dict: The resolution result.
        """
        start_time = time.time()
        
        # Check cache first
        cached_response = self.cache.get((domain, record_type))
        if cached_response:
            return {
                'source': 'cache',
                'data': cached_response,
                'duration': (time.time() - start_time) * 1000,
                'mode': mode
            }
            
        result = None
        used_mode = mode
        
        if mode == 'auto':
            # Try Recursive -> Forward -> DoH
            try:
                result = self.recursive_resolver.resolve(domain, record_type)
                used_mode = 'recursive'
            except Exception as e:
                logger.error(f"Recursive resolution failed: {e}")
                
            if not result:
                try:
                    result = self.forward_resolver.resolve(domain, record_type)
                    used_mode = 'forward'
                except Exception as e:
                    logger.error(f"Forward resolution failed: {e}")
                    
            if not result:
                try:
                    query = build_dns_query(domain, record_type)
                    resp_data = send_doh_query(query)
                    if resp_data:
                        result = parse_dns_response(resp_data)
                        used_mode = 'doh'
                except Exception as e:
                    logger.error(f"DoH resolution failed: {e}")
                    
        elif mode == 'recursive':
            result = self.recursive_resolver.resolve(domain, record_type)
        elif mode == 'forward':
            result = self.forward_resolver.resolve(domain, record_type)
        elif mode == 'doh':
            query = build_dns_query(domain, record_type)
            resp_data = send_doh_query(query)
            if resp_data:
                result = parse_dns_response(resp_data)
                
        duration = (time.time() - start_time) * 1000
        
        if result:
            # Cache the result
            self.cache.put((domain, record_type), result)
            
            # Add DNSSEC info
            result['dnssec'] = get_dnssec_info(result)
            
            self.metrics.record_query(domain, used_mode, duration, 'success')
            return {
                'source': 'network',
                'data': result,
                'duration': duration,
                'mode': used_mode
            }
        else:
            self.metrics.record_query(domain, used_mode, duration, 'failure')
            return {
                'source': 'network',
                'error': 'Resolution failed',
                'duration': duration,
                'mode': used_mode
            }
