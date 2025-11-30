import streamlit as st
from dns_resolver.config import *

def get_type_name(rtype):
    type_map = {
        TYPE_A: "A", TYPE_AAAA: "AAAA", TYPE_NS: "NS", 
        TYPE_CNAME: "CNAME", TYPE_MX: "MX", TYPE_TXT: "TXT", 
        TYPE_PTR: "PTR", TYPE_SOA: "SOA"
    }
    return type_map.get(rtype, str(rtype))

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
                # Display Answers with Links
                if 'answers' in result['data'] and result['data']['answers']:
                    st.subheader("Answers")
                    for answer in result['data']['answers']:
                        with st.container():
                            c1, c2, c3, c4 = st.columns([3, 1, 4, 2])
                            with c1:
                                st.markdown(f"**{answer['name']}**")
                            with c2:
                                st.markdown(f"`{get_type_name(answer['type'])}`")
                            with c3:
                                data_val = answer['data']
                                if isinstance(data_val, dict):
                                    st.write(data_val)
                                else:
                                    st.code(str(data_val), language=None)
                            with c4:
                                # Create a link to the domain
                                target = answer['name']
                                if answer['type'] == TYPE_PTR:
                                    target = answer['data']
                                
                                url = f"http://{target}"
                                st.link_button("🌐 Visit Site", url)
                            st.divider()

                with st.expander("Raw Details"):
                    st.json(result['data'])
                
                if 'dnssec' in result['data']:
                    dnssec = result['data']['dnssec']
                    if dnssec['has_rrsig']:
                        st.info("🔒 DNSSEC: RRSIG found (Signed Zone)")
                    if dnssec['has_ds']:
                        st.info("🔗 DNSSEC: DS record found (Delegation Signer)")
        else:
            st.error("Resolution failed")
