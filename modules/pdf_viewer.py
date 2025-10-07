import streamlit as st
import json
import base64
import os

def render_pdf_viewer(abstract, db):
    """
    Show PDF alongside abstract data with zoom controls
    """
    st.subheader("PDF & Abstract Side-by-Side")
    
    pdf_path = db.get_pdf_path(abstract.id)
    
    if not pdf_path:
        st.error("PDF file not found. It may have been deleted or not stored.")
        return
    
    # Initialize zoom level in session state
    if 'pdf_zoom' not in st.session_state:
        st.session_state.pdf_zoom = 100
    
    # Two columns: PDF on left, data on right
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.caption("📄 Original PDF")
        
        # Zoom controls
        zoom_col1, zoom_col2, zoom_col3, zoom_col4 = st.columns([1, 1, 1, 2])
        with zoom_col1:
            if st.button("🔍➖", help="Zoom Out"):
                st.session_state.pdf_zoom = max(50, st.session_state.pdf_zoom - 25)
                st.rerun()
        with zoom_col2:
            if st.button("🔍➕", help="Zoom In"):
                st.session_state.pdf_zoom = min(200, st.session_state.pdf_zoom + 25)
                st.rerun()
        with zoom_col3:
            if st.button("🔄", help="Reset Zoom"):
                st.session_state.pdf_zoom = 100
                st.rerun()
        with zoom_col4:
            st.caption(f"Zoom: {st.session_state.pdf_zoom}%")
        
        # Display PDF with zoom
        with open(pdf_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        
        # Use iframe with scaling
        zoom_scale = st.session_state.pdf_zoom / 100
        
        pdf_html = f"""
        <style>
            .pdf-container {{
                width: 100%;
                height: 800px;
                overflow: auto;
                border: 1px solid #ddd;
                border-radius: 5px;
            }}
            .pdf-container iframe {{
                transform: scale({zoom_scale});
                transform-origin: 0 0;
                width: {100/zoom_scale}%;
                height: {800/zoom_scale}px;
            }}
        </style>
        <div class="pdf-container">
            <iframe src="data:application/pdf;base64,{base64_pdf}" 
                    type="application/pdf"
                    style="border: none;">
            </iframe>
        </div>
        """
        
        st.markdown(pdf_html, unsafe_allow_html=True)
    
    with col2:
        st.caption("📋 Extracted Abstract")
        
        # Show rendered markdown with scrolling
        container = st.container(height=800)
        with container:
            if abstract.is_edited and abstract.edited_markdown_output:
                st.markdown(abstract.edited_markdown_output)
            elif abstract.markdown_output:
                st.markdown(abstract.markdown_output)
            else:
                st.warning("No abstract data available")
