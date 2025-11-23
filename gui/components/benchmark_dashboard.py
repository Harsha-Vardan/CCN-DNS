import streamlit as st
import pandas as pd

def render_benchmark_dashboard(resolver):
    st.header("Performance Benchmark")
    
    if st.button("Run Benchmark"):
        with st.spinner("Running benchmark..."):
            # Simple benchmark: Resolve a few domains
            domains = ["google.com", "facebook.com", "amazon.com", "example.com"]
            results = []
            
            for d in domains:
                res = resolver.resolve(d, mode='auto')
                results.append({
                    "Domain": d,
                    "Duration (ms)": f"{res['duration']:.2f}",
                    "Mode": res['mode'],
                    "Source": res['source']
                })
                
            st.table(pd.DataFrame(results))
            
    st.subheader("Historical Metrics")
    avg_latency = resolver.metrics.get_average_latency()
    total_queries = resolver.metrics.get_query_count()
    
    col1, col2 = st.columns(2)
    col1.metric("Avg Latency", f"{avg_latency:.2f} ms")
    col2.metric("Total Queries", total_queries)
