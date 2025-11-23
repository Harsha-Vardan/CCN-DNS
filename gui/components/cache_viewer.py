import streamlit as st
import pandas as pd
import time

def render_cache_viewer(resolver):
    st.header("Cache Explorer")
    
    stats = resolver.cache.get_stats()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Cache Hits", stats['hits'])
    col2.metric("Cache Misses", stats['misses'])
    col3.metric("Current Size", f"{stats['size']} / {stats['capacity']}")
    
    if stats['size'] > 0:
        st.subheader("Cached Records")
        
        cache_data = []
        current_time = time.time()
        
        for key, (record, timestamp) in resolver.cache.cache.items():
            domain, rtype = key
            ttl = record.get('ttl', 300)
            age = current_time - timestamp
            remaining_ttl = max(0, ttl - age)
            
            cache_data.append({
                "Domain": domain,
                "Type": rtype,
                "TTL Remaining": f"{remaining_ttl:.1f}s",
                "Data": str(record.get('data'))[:50] + "..."
            })
            
        df = pd.DataFrame(cache_data)
        st.dataframe(df)
    else:
        st.info("Cache is empty.")
