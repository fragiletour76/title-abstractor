import streamlit as st
import json
from src.renderer import render_markdown

def render_edit_interface(abstract, db):
    """Render the edit interface for an abstract"""
    
    if 'working_json' not in st.session_state or not st.session_state.working_json:
        st.error("No working data loaded")
        return
    
    documents = st.session_state.working_json.get('documents', [])
    
    if not documents:
        st.warning("No documents found in this abstract")
        return
    
    st.info(f"Editing {len(documents)} documents")
    
    # Edit each document
    for i, doc in enumerate(documents):
        with st.expander(f"Document {i+1}: {doc.get('documentType', 'Unknown')}", expanded=False):
            
            # Document order
            col1, col2 = st.columns([1, 5])
            with col1:
                new_order = st.number_input(
                    "Order #",
                    min_value=1,
                    max_value=len(documents),
                    value=i + 1,
                    step=1,
                    key=f"order_{i}"
                )
            
            with col2:
                doc['documentType'] = st.text_input(
                    "Document Type",
                    value=doc.get('documentType', ''),
                    key=f"doctype_{i}"
                )
            
            # Parties
            st.subheader("Parties")
            parties = doc.get('parties', {})
            col1, col2 = st.columns(2)
            
            with col1:
                parties['fromLabel'] = st.text_input(
                    "From Label",
                    value=parties.get('fromLabel', ''),
                    key=f"fromlabel_{i}"
                )
                from_names = parties.get('from', [])
                from_text = "; ".join(from_names) if isinstance(from_names, list) else str(from_names)
                new_from = st.text_area(
                    "From Parties",
                    value=from_text,
                    height=100,
                    key=f"from_{i}"
                )
                parties['from'] = [n.strip() for n in new_from.split(';') if n.strip()]
            
            with col2:
                parties['toLabel'] = st.text_input(
                    "To Label",
                    value=parties.get('toLabel', ''),
                    key=f"tolabel_{i}"
                )
                to_names = parties.get('to', [])
                to_text = "; ".join(to_names) if isinstance(to_names, list) else str(to_names)
                new_to = st.text_area(
                    "To Parties",
                    value=to_text,
                    height=100,
                    key=f"to_{i}"
                )
                parties['to'] = [n.strip() for n in new_to.split(';') if n.strip()]
            
            doc['parties'] = parties
            
            # Dates
            st.subheader("Dates")
            dates = doc.get('dates', {})
            col1, col2, col3 = st.columns(3)
            with col1:
                dates['instrumentDate'] = st.text_input(
                    "Instrument Date",
                    value=dates.get('instrumentDate', ''),
                    key=f"instdate_{i}"
                )
            with col2:
                dates['acknowledgedDate'] = st.text_input(
                    "Acknowledged Date",
                    value=dates.get('acknowledgedDate', ''),
                    key=f"ackdate_{i}"
                )
            with col3:
                dates['recordDate'] = st.text_input(
                    "Record Date",
                    value=dates.get('recordDate', ''),
                    key=f"recdate_{i}"
                )
            doc['dates'] = dates
            
            # Recording
            st.subheader("Recording")
            recording = doc.get('recording', {})
            col1, col2 = st.columns(2)
            with col1:
                recording['locationInstrumentNumber'] = st.text_input(
                    "Location/Instrument #",
                    value=recording.get('locationInstrumentNumber', ''),
                    key=f"loc_{i}"
                )
            with col2:
                recording['county'] = st.text_input(
                    "County",
                    value=recording.get('county', ''),
                    key=f"county_{i}"
                )
            doc['recording'] = recording
            
            # Page Location (read-only display)
            if doc.get('pageLocation'):
                pages_info = doc['pageLocation']
                st.caption(f"📄 Found on pages {pages_info.get('start', '?')}-{pages_info.get('end', '?')}")
            
            # Notes field for all text content
            st.subheader("Notes & Legal Description")
            prop = doc.get('property', {})
            current_notes = prop.get('legalDescription', '')
            
            edited_notes = st.text_area(
                "All text content",
                value=current_notes,
                height=300,
                key=f"notes_{i}"
            )
            prop['legalDescription'] = edited_notes
            doc['property'] = prop
    
    # Save button
    st.divider()
    if st.button("💾 Save Changes", type="primary", use_container_width=True):
        # Regenerate markdown
        new_markdown = render_markdown(st.session_state.working_json)
        
        # Save to database
        success = db.update_abstract(
            st.session_state.current_abstract_id,
            st.session_state.working_json,
            new_markdown,
            user="editor"
        )
        
        if success:
            st.success("✅ Changes saved!")
            st.session_state.view_mode = 'view'
            st.rerun()
        else:
            st.error("❌ Failed to save changes")
