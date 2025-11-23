import streamlit as st
from dns_resolver.config import *

def render_lookup_panel(resolver):
    st.header("DNS Lookup")
    
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        domain = st.text_input("Domain Name", "google.com")
        
    with col2:
        record_type_str = st.selectbox("Record Type", ["A", "AAAA", "NS", "CNAME", "MX", "TXT", "PTR", "SOA"])
        record_type_map = {
            "A": TYPE_A, "AAAA": TYPE_AAAA, "NS": TYPE_NS, 
            "CNAME": TYPE_CNAME, "MX": TYPE_MX, "TXT": TYPE_TXT, 
            "PTR": TYPE_PTR, "SOA": TYPE_SOA
        }
        record_type = record_type_map[record_type_str]
        
    with col3:
        mode = st.selectbox("Mode", ["auto", "recursive", "forward", "doh"])
        
    if st.button("Resolve", type="primary"):
        with st.spinner("Resolving..."):
            result = resolver.resolve(domain, record_type, mode)
            
        if result:
            st.success(f"Resolved in {result['duration']:.2f} ms using {result['mode']} mode")
            
            if 'error' in result:
                st.error(result['error'])
            else:
                st.json(result['data'])
                
                if 'dnssec' in result['data']:
                    dnssec = result['data']['dnssec']
                    if dnssec['has_rrsig']:
                        st.info("🔒 DNSSEC: RRSIG found (Signed Zone)")
                    if dnssec['has_ds']:
                        st.info("🔗 DNSSEC: DS record found (Delegation Signer)")
        else:
            st.error("Resolution failed")
