import streamlit as st
import json
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px

def render_timeline(abstract):
    """Render interactive timeline visualization"""
    
    # Load JSON data
    if abstract.is_edited and abstract.edited_json_data:
        data = json.loads(abstract.edited_json_data)
    else:
        data = json.loads(abstract.json_data)
    
    documents = data.get('documents', [])
    
    if not documents:
        st.warning("No documents to visualize")
        return
    
    st.subheader("Chain of Title Timeline")
    
    # Parse dates and prepare data
    timeline_data = []
    
    for i, doc in enumerate(documents, 1):
        doc_type = doc.get('documentType', 'Unknown')
        dates = doc.get('dates', {})
        record_date_str = dates.get('recordDate', '')
        
        # Try to parse date
        parsed_date = None
        for fmt in ["%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
            try:
                parsed_date = datetime.strptime(record_date_str, fmt)
                break
            except:
                continue
        
        if parsed_date:
            parties = doc.get('parties', {})
            from_party = parties.get('from', [''])[0] if parties.get('from') else 'N/A'
            to_party = parties.get('to', [''])[0] if parties.get('to') else 'N/A'
            
            pages = doc.get('pageLocation', {})
            page_range = f"pp. {pages.get('start', '?')}-{pages.get('end', '?')}"
            
            timeline_data.append({
                'id': i,
                'type': doc_type,
                'date': parsed_date,
                'date_str': record_date_str,
                'from': from_party,
                'to': to_party,
                'pages': page_range,
                'page_start': pages.get('start', 0)
            })
    
    if not timeline_data:
        st.warning("No documents with valid dates found")
        return
    
    # Sort by date
    timeline_data.sort(key=lambda x: x['date'])
    
    # Color mapping
    color_map = {
        'Deed': '#3498db',
        'Mortgage': '#e74c3c',
        'Satisfaction': '#2ecc71',
        'Judgment': '#f39c12',
        'Lien': '#9b59b6',
        'Easement': '#1abc9c'
    }
    
    # Create timeline visualization
    fig = go.Figure()
    
    for item in timeline_data:
        doc_type = item['type']
        color = color_map.get(doc_type, '#95a5a6')
        
        fig.add_trace(go.Scatter(
            x=[item['date']],
            y=[item['id']],
            mode='markers+text',
            marker=dict(size=15, color=color, line=dict(width=2, color='white')),
            text=[f"{item['id']}"],
            textposition="middle center",
            textfont=dict(color='white', size=10),
            name=doc_type,
            hovertemplate=(
                f"<b>Document #{item['id']}</b><br>" +
                f"Type: {doc_type}<br>" +
                f"Date: {item['date_str']}<br>" +
                f"From: {item['from']}<br>" +
                f"To: {item['to']}<br>" +
                f"Pages: {item['pages']}<br>" +
                "<extra></extra>"
            ),
            showlegend=True
        ))
    
    fig.update_layout(
        title="Document Timeline (Click markers for details)",
        xaxis_title="Record Date",
        yaxis_title="Document #",
        height=600,
        hovermode='closest',
        yaxis=dict(
            tickmode='linear',
            tick0=1,
            dtick=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Document list with page references
    st.subheader("Document List")
    
    for item in timeline_data:
        with st.expander(f"#{item['id']} - {item['type']} ({item['date_str']}) - {item['pages']}"):
            st.write(f"**From:** {item['from']}")
            st.write(f"**To:** {item['to']}")
            st.write(f"**Record Date:** {item['date_str']}")
            st.write(f"**Pages:** {item['pages']}")
            
            # Link to edit
            if st.button(f"Edit Document #{item['id']}", key=f"edit_btn_{item['id']}"):
                st.session_state.view_mode = 'edit'
                st.rerun()
