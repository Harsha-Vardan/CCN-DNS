import random
from .config import *
from .utils import get_logger, is_valid_ip
from .packet import build_dns_query
from .parser import parse_dns_response
from .transport_udp import send_udp_query

logger = get_logger(__name__)

class RecursiveResolver:
    def __init__(self):
        self.root_servers = ROOT_SERVERS

    def resolve(self, domain, record_type=TYPE_A):
        """
        Performs a full recursive resolution for the given domain.
        """
        logger.info(f"Starting recursive resolution for {domain} ({record_type})")
        
        # Start with a random root server
        current_ns_ip = random.choice(list(self.root_servers.values()))
        
        while True:
            logger.info(f"Querying {current_ns_ip} for {domain}")
            
            # Build query
            query = build_dns_query(domain, record_type, recursion_desired=False)
            
            # Send query
            response_data = send_udp_query(query, current_ns_ip)
            
            if not response_data:
                logger.error(f"No response from {current_ns_ip}")
                return None
                
            # Parse response
            response = parse_dns_response(response_data)
            
            # Check for answers
            if response['answers']:
                logger.info(f"Found answer for {domain}")
                return response
                
            # Check for referrals (Authority section)
            if response['authorities']:
                ns_list = []
                glue_records = {}
                
                # Extract NS records and glue records
                for auth in response['authorities']:
                    if auth['type'] == TYPE_NS:
                        ns_list.append(auth['data'])
                        
                for add in response['additionals']:
                    if add['type'] == TYPE_A:
                        glue_records[add['name']] = add['data']
                        
                # Find a valid NS IP
                found_next_ns = False
                for ns in ns_list:
                    if ns in glue_records:
                        current_ns_ip = glue_records[ns]
                        found_next_ns = True
                        break
                    else:
                        # Need to resolve the NS name itself!
                        # This is where it gets tricky (recursion within recursion)
                        # For simplicity in this MVP, we might skip this or implement a simple lookup
                        # But for a true recursive resolver, we should resolve the NS name.
                        # Let's try to resolve the NS name if no glue record is found.
                        logger.info(f"No glue record for {ns}, attempting to resolve NS IP")
                        ns_ip_response = self.resolve(ns, TYPE_A)
                        if ns_ip_response and ns_ip_response['answers']:
                             for ans in ns_ip_response['answers']:
                                 if ans['type'] == TYPE_A:
                                     current_ns_ip = ans['data']
                                     found_next_ns = True
                                     break
                        if found_next_ns:
                            break

                if found_next_ns:
                    continue
                else:
                    logger.error("Could not find next nameserver IP")
                    return None
            else:
                logger.warning("No answers and no authorities found")
                return None
