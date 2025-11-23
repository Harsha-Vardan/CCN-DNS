import streamlit as st
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dns_resolver.resolver_api import ResolverAPI
from gui.components.lookup_panel import render_lookup_panel
from gui.components.path_visualizer import render_path_visualizer
from gui.components.cache_viewer import render_cache_viewer
from gui.components.packet_viewer import render_packet_viewer
from gui.components.benchmark_dashboard import render_benchmark_dashboard

# Initialize Resolver
if 'resolver' not in st.session_state:
    st.session_state.resolver = ResolverAPI()

st.set_page_config(page_title="Advanced DNS Resolver", layout="wide")

st.title("🌐 Advanced DNS Resolver & Visualizer")

tabs = st.tabs(["🔍 Lookup", "🗺️ Path", "📦 Cache", "📡 Packet", "📊 Benchmark"])

with tabs[0]:
    render_lookup_panel(st.session_state.resolver)

with tabs[1]:
    render_path_visualizer(st.session_state.resolver)

with tabs[2]:
    render_cache_viewer(st.session_state.resolver)

with tabs[3]:
    render_packet_viewer()

with tabs[4]:
    render_benchmark_dashboard(st.session_state.resolver)

st.sidebar.info("Advanced DNS Resolver v1.0")
st.sidebar.markdown("---")
st.sidebar.markdown("**Features:**")
st.sidebar.markdown("- Recursive / Forward / DoH")
st.sidebar.markdown("- DNSSEC Awareness")
st.sidebar.markdown("- TTL + LRU Cache")
st.sidebar.markdown("- Packet Inspection")
