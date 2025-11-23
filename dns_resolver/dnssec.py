from .config import *

def has_dnssec_records(response):
    """
    Checks if the response contains DNSSEC related records (RRSIG, DS, DNSKEY).
    """
    dnssec_types = {46, 43, 48} # RRSIG, DS, DNSKEY
    
    for section in ['answers', 'authorities', 'additionals']:
        for record in response.get(section, []):
            if record['type'] in dnssec_types:
                return True
    return False

def get_dnssec_info(response):
    """
    Extracts DNSSEC information from the response.
    """
    info = {
        'has_rrsig': False,
        'has_ds': False,
        'has_dnskey': False
    }
    
    for section in ['answers', 'authorities', 'additionals']:
        for record in response.get(section, []):
            if record['type'] == 46: # RRSIG
                info['has_rrsig'] = True
            elif record['type'] == 43: # DS
                info['has_ds'] = True
            elif record['type'] == 48: # DNSKEY
                info['has_dnskey'] = True
                
    return info
