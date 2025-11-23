import streamlit as st
import graphviz

def render_path_visualizer(resolver):
    st.header("Resolution Path Visualizer")
    
    st.info("This visualization shows the theoretical path for a recursive lookup.")
    
    graph = graphviz.Digraph()
    graph.attr(rankdir='LR')
    
    graph.node('Client', 'Client', shape='box', style='filled', fillcolor='lightblue')
    graph.node('Root', 'Root Server (.)', shape='ellipse')
    graph.node('TLD', 'TLD Server (.com)', shape='ellipse')
    graph.node('Auth', 'Auth Server (google.com)', shape='ellipse')
    
    graph.edge('Client', 'Root', label='1. Query .')
    graph.edge('Root', 'Client', label='2. Refer to .com')
    graph.edge('Client', 'TLD', label='3. Query .com')
    graph.edge('TLD', 'Client', label='4. Refer to google.com')
    graph.edge('Client', 'Auth', label='5. Query google.com')
    graph.edge('Auth', 'Client', label='6. Answer')
    
    st.graphviz_chart(graph)
