import streamlit as st
from dns_resolver.packet import build_dns_query
from dns_resolver.utils import hex_dump
from dns_resolver.config import *

def render_packet_viewer():
    st.header("Packet Inspector")
    
    domain = st.text_input("Domain for Packet Gen", "example.com")
    rtype = st.selectbox("Type", ["A", "AAAA", "NS", "MX"])
    rtype_map = {"A": TYPE_A, "AAAA": TYPE_AAAA, "NS": TYPE_NS, "MX": TYPE_MX}
    
    if st.button("Generate Packet"):
        packet = build_dns_query(domain, rtype_map[rtype])
        
        st.subheader("Hex Dump")
        st.code(hex_dump(packet))
        
        st.subheader("Packet Structure")
        st.markdown(f"""
        - **Header**: Transaction ID, Flags, Counts
        - **Question**: {domain} ({rtype})
        """)
        
        st.info("This view shows how the raw bytes of a DNS query look on the wire.")
