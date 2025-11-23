import requests
import base64
from .config import *
from .utils import get_logger

logger = get_logger(__name__)

def send_doh_query(query_packet, provider_url=DOH_PROVIDERS['google'], timeout=TIMEOUT):
    """
    Sends a DNS query via DoH (DNS over HTTPS).
    
    Args:
        query_packet (bytes): The raw DNS query packet.
        provider_url (str): The DoH provider URL.
        timeout (float): The request timeout in seconds.
        
    Returns:
        bytes: The raw DNS response packet, or None if failed.
    """
    headers = {
        'Content-Type': 'application/dns-message',
        'Accept': 'application/dns-message'
    }
    
    try:
        response = requests.post(
            provider_url,
            data=query_packet,
            headers=headers,
            timeout=timeout
        )
        
        if response.status_code == 200:
            return response.content
        else:
            logger.error(f"DoH query failed with status code {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"DoH query error: {e}")
        return None
