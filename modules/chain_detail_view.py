import streamlit as st
import json
from datetime import datetime


def render_chain_detail_view(abstract):
    """
    Render detailed chain view with related documents (mortgages, satisfactions, etc.)
    nested under their corresponding deeds.
    """
    # Load JSON data
    if abstract.is_edited and abstract.edited_json_data:
        data = json.loads(abstract.edited_json_data)
    else:
        data = json.loads(abstract.json_data)
    
    documents = data.get('documents', [])
    
    if not documents:
        st.warning("No documents to display")
        return
    
    st.subheader("📋 Detailed Chain with Related Documents")
    st.caption("All documents including mortgages, satisfactions, and other encumbrances")
    
    # Separate documents by type
    deeds = []
    mortgages = []
    satisfactions = []
    other_docs = []
    
    for i, doc in enumerate(documents):
        doc['_index'] = i + 1  # Add document number
        doc_type = doc.get('documentType', '').lower()
        
        if 'deed' in doc_type:
            deeds.append(doc)
        elif 'mortgage' in doc_type:
            mortgages.append(doc)
        elif 'satisfaction' in doc_type or 'discharge' in doc_type:
            satisfactions.append(doc)
        else:
            other_docs.append(doc)
    
    # Match related documents to deeds
    deed_relationships = _build_relationships(deeds, mortgages, satisfactions, other_docs)
    
    # Display summary
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Deeds", len(deeds))
    with col2:
        active_mortgages = sum(1 for m in mortgages if not _is_satisfied(m, satisfactions))
        st.metric("Active Mortgages", active_mortgages, delta="🔴" if active_mortgages > 0 else "✅")
    with col3:
        st.metric("Satisfactions", len(satisfactions))
    with col4:
        st.metric("Other Docs", len(other_docs))
    
    st.divider()
    
    # Display each deed with its related documents
    for deed in deeds:
        _render_deed_with_related(deed, deed_relationships.get(deed['_index'], {}), satisfactions)


def _build_relationships(deeds, mortgages, satisfactions, other_docs):
    """
    Build relationships between deeds and related documents.
    Returns dict: {deed_index: {mortgages: [], satisfactions: [], other: []}}
    """
    relationships = {}
    
    for deed in deeds:
        deed_idx = deed['_index']
        relationships[deed_idx] = {
            'mortgages': [],
            'other': []
        }
        
        deed_grantees = set(_normalize_names(deed.get('parties', {}).get('to', [])))
        deed_date = _parse_date(deed.get('dates', {}).get('recordDate'))
        
        # Find related mortgages
        for mortgage in mortgages:
            # Match by mortgagor = deed grantee
            mortgagors = set(_normalize_names(mortgage.get('parties', {}).get('from', [])))
            mtg_date = _parse_date(mortgage.get('dates', {}).get('recordDate'))
            
            # Check if mortgagor matches deed grantee and mortgage is after deed
            if mortgagors & deed_grantees:
                if not deed_date or not mtg_date or mtg_date >= deed_date:
                    relationships[deed_idx]['mortgages'].append(mortgage)
        
        # Find other related documents (judgments, liens, etc.)
        for other in other_docs:
            other_parties = set(_normalize_names(other.get('parties', {}).get('from', [])))
            other_parties.update(_normalize_names(other.get('parties', {}).get('to', [])))
            
            if deed_grantees & other_parties:
                relationships[deed_idx]['other'].append(other)
    
    return relationships


def _render_deed_with_related(deed, related, all_satisfactions):
    """Render a single deed with its related documents"""
    deed_idx = deed['_index']
    doc_type = deed.get('documentType', 'Deed')
    
    # Get deed info
    parties = deed.get('parties', {})
    from_parties = parties.get('from', [])
    to_parties = parties.get('to', [])
    dates = deed.get('dates', {})
    record_date = dates.get('recordDate', 'Unknown')
    recording = deed.get('recording', {})
    rec_number = recording.get('locationInstrumentNumber', 'Not recorded')
    pages = deed.get('pageLocation', {})
    page_range = f"{pages.get('start', '?')}-{pages.get('end', '?')}"
    
    # Count related documents
    related_count = len(related.get('mortgages', [])) + len(related.get('other', []))
    related_indicator = f" ({related_count} related)" if related_count > 0 else ""
    
    with st.expander(f"📄 Document #{deed_idx} - {doc_type} - {record_date} (Pages {page_range}){related_indicator}", expanded=False):
        # Deed details
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**From:**")
            for party in from_parties:
                st.write(f"• {party}")
        with col2:
            st.markdown("**To:**")
            for party in to_parties:
                st.write(f"• {party}")
        
        st.markdown(f"**Recording:** {rec_number}")
        
        # Property description
        legal_desc = deed.get('property', {}).get('legalDescription', '')
        if legal_desc:
            with st.expander("📝 Legal Description", expanded=False):
                st.text(legal_desc[:500] + ("..." if len(legal_desc) > 500 else ""))
        
        # Related mortgages
        if related.get('mortgages'):
            st.divider()
            st.markdown("### 🔗 Related Mortgages")
            
            for mortgage in related['mortgages']:
                _render_mortgage(mortgage, all_satisfactions)
        
        # Other related documents
        if related.get('other'):
            st.divider()
            st.markdown("### 🔗 Other Related Documents")
            
            for doc in related['other']:
                _render_other_document(doc)


def _render_mortgage(mortgage, all_satisfactions):
    """Render a mortgage with its satisfaction status"""
    mtg_idx = mortgage['_index']
    mtg_parties = mortgage.get('parties', {})
    mtg_dates = mortgage.get('dates', {})
    mtg_recording = mortgage.get('recording', {})
    mtg_amount = mortgage.get('monetary', {}).get('mortgageAmount', 'Unknown')
    
    # Check if satisfied
    satisfaction = _find_satisfaction(mortgage, all_satisfactions)
    
    if satisfaction:
        status_icon = "✅"
        status_text = "SATISFIED"
        status_color = "green"
        sat_date = satisfaction.get('dates', {}).get('recordDate', 'Unknown date')
        status_detail = f"Discharged: {sat_date}"
    else:
        status_icon = "🔴"
        status_text = "ACTIVE"
        status_color = "red"
        status_detail = "Not satisfied"
    
    # Display mortgage
    with st.container():
        st.markdown(f"**{status_icon} Mortgage #{mtg_idx}** - {status_text}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Amount:** ${mtg_amount}")
        with col2:
            st.write(f"**Date:** {mtg_dates.get('recordDate', 'Unknown')}")
        with col3:
            st.write(f"**Recording:** {mtg_recording.get('locationInstrumentNumber', 'N/A')}")
        
        st.write(f"**Mortgagor:** {', '.join(mtg_parties.get('from', ['Unknown']))}")
        st.write(f"**Mortgagee:** {', '.join(mtg_parties.get('to', ['Unknown']))}")
        st.write(f"**Status:** :{status_color}[{status_detail}]")
        
        # Show satisfaction details if exists
        if satisfaction:
            sat_recording = satisfaction.get('recording', {}).get('locationInstrumentNumber', 'N/A')
            st.caption(f"Satisfaction recorded: {sat_recording}")


def _render_other_document(doc):
    """Render other document types (judgments, liens, etc.)"""
    doc_idx = doc['_index']
    doc_type = doc.get('documentType', 'Document')
    doc_dates = doc.get('dates', {})
    doc_parties = doc.get('parties', {})
    
    with st.container():
        st.markdown(f"**📎 {doc_type} #{doc_idx}**")
        st.write(f"**Date:** {doc_dates.get('recordDate', 'Unknown')}")
        
        if doc_parties.get('from'):
            st.write(f"**From:** {', '.join(doc_parties.get('from', []))}")
        if doc_parties.get('to'):
            st.write(f"**To:** {', '.join(doc_parties.get('to', []))}")


def _is_satisfied(mortgage, all_satisfactions):
    """Check if a mortgage has a corresponding satisfaction"""
    return _find_satisfaction(mortgage, all_satisfactions) is not None


def _find_satisfaction(mortgage, all_satisfactions):
    """Find satisfaction document for a given mortgage"""
    mtg_recording = mortgage.get('recording', {}).get('locationInstrumentNumber', '').strip().upper()
    mtg_parties_to = set(_normalize_names(mortgage.get('parties', {}).get('to', [])))
    mtg_date = _parse_date(mortgage.get('dates', {}).get('recordDate'))
    
    for satisfaction in all_satisfactions:
        # Match by recording reference in satisfaction notes
        sat_notes = satisfaction.get('notes', '') or ''
        if mtg_recording and mtg_recording in sat_notes.upper():
            return satisfaction
        
        # Match by parties (satisfaction from = mortgage to)
        sat_from = set(_normalize_names(satisfaction.get('parties', {}).get('from', [])))
        if mtg_parties_to & sat_from:
            # Check date - satisfaction should be after mortgage
            sat_date = _parse_date(satisfaction.get('dates', {}).get('recordDate'))
            if sat_date and mtg_date and sat_date >= mtg_date:
                return satisfaction
    
    return None


def _normalize_names(names):
    """Normalize party names for comparison"""
    if not names:
        return []
    
    normalized = []
    for name in names:
        if name:
            # Remove common suffixes, normalize case and whitespace
            clean = name.upper().strip()
            clean = clean.replace(',', '').replace('.', '')
            clean = ' '.join(clean.split())
            normalized.append(clean)
    
    return normalized


def _parse_date(date_str):
    """Parse date string to datetime object"""
    if not date_str:
        return None
    
    # Try common formats
    formats = [
        "%B %d, %Y",
        "%b %d, %Y", 
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%B %d %Y",
        "%b %d %Y"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    
    return None
