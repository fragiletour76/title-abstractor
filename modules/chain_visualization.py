import streamlit as st
import json
import graphviz
from datetime import datetime


def render_chain_visualization(abstract):
    """
    Render chain of title as an org-chart/flowchart
    Shows ownership transfers and related documents (mortgages, liens)
    """
    
    # Load JSON data
    if abstract.is_edited and abstract.edited_json_data:
        data = json.loads(abstract.edited_json_data)
    else:
        data = json.loads(abstract.json_data)
    
    documents = data.get('documents', [])
    
    if not documents:
        st.warning("No documents to visualize")
        return
    
    st.subheader("Chain of Title - Ownership Flow")
    st.caption("Deeds shown in main chain, mortgages/liens as side branches")
    
    # Separate documents by type
    deeds = []
    mortgages = []
    other_docs = []
    
    for i, doc in enumerate(documents):
        doc['_index'] = i + 1
        doc_type = doc.get('documentType', '').lower()
        
        if 'deed' in doc_type and 'satisfaction' not in doc_type:
            deeds.append(doc)
        elif 'mortgage' in doc_type:
            mortgages.append(doc)
        else:
            other_docs.append(doc)
    
    # Match mortgages to deeds
    deed_relationships = _match_mortgages_to_deeds(deeds, mortgages)
    
    # Create flowchart
    dot = graphviz.Digraph(comment='Chain of Title')
    dot.attr(rankdir='TB')  # Top to bottom
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', fontsize='10')
    
    # Add main chain (deeds)
    prev_deed_id = None
    for deed in deeds:
        deed_id = f"deed_{deed['_index']}"
        
        # Create deed node
        label = _create_deed_label(deed)
        dot.node(deed_id, label, fillcolor='#e3f2fd')
        
        # Connect to previous deed
        if prev_deed_id:
            dot.edge(prev_deed_id, deed_id, label='Deed', color='#1976d2', penwidth='2')
        
        # Add related mortgages as side branches
        related_mortgages = deed_relationships.get(deed['_index'], [])
        for j, mortgage in enumerate(related_mortgages):
            mtg_id = f"mtg_{mortgage['_index']}_{deed['_index']}"
            mtg_label = _create_mortgage_label(mortgage)
            
            # Check if satisfied
            is_satisfied = _check_if_satisfied(mortgage)
            if is_satisfied:
                dot.node(mtg_id, mtg_label, fillcolor='#c8e6c9', shape='note')
                dot.edge(deed_id, mtg_id, label='Mortgage (Satisfied)', style='dashed', color='green')
            else:
                dot.node(mtg_id, mtg_label, fillcolor='#ffcdd2', shape='note')
                dot.edge(deed_id, mtg_id, label='Mortgage', style='dashed', color='red')
        
        prev_deed_id = deed_id
    
    # Render
    st.graphviz_chart(dot)
    
    # Legend
    with st.expander("📖 Chart Legend"):
        st.markdown("""
        **Main Chain (Solid Blue Lines):**
        - 🔵 Blue boxes = Property transfers (Deeds)
        - Solid arrows = Ownership flow
        
        **Related Documents (Dashed Lines):**
        - 🔴 Red notes = Active mortgages/liens (not satisfied)
        - 🟢 Green notes = Satisfied/discharged mortgages
        - Dashed arrows = Related to deed but not ownership transfer
        """)


def _match_mortgages_to_deeds(deeds, mortgages):
    """
    Match mortgages to their corresponding deeds.
    Returns dict: {deed_index: [mortgage, mortgage, ...]}
    """
    relationships = {}
    
    for deed in deeds:
        deed_idx = deed['_index']
        relationships[deed_idx] = []
        
        # Get deed grantees (who received the property)
        deed_grantees = set(_normalize_names(deed.get('parties', {}).get('to', [])))
        deed_date = _parse_date(deed.get('dates', {}).get('recordDate'))
        
        # Find mortgages where mortgagor matches deed grantee
        for mortgage in mortgages:
            mortgagors = set(_normalize_names(mortgage.get('parties', {}).get('from', [])))
            mtg_date = _parse_date(mortgage.get('dates', {}).get('recordDate'))
            
            # Check if mortgagor is same as deed grantee
            if mortgagors & deed_grantees:
                # Only attach if mortgage is after or close to deed date
                if not deed_date or not mtg_date or mtg_date >= deed_date:
                    relationships[deed_idx].append(mortgage)
    
    return relationships


def _create_deed_label(deed):
    """Create label text for a deed node"""
    parties = deed.get('parties', {})
    from_party = parties.get('from', ['Unknown'])[0] if parties.get('from') else 'Unknown'
    to_party = parties.get('to', ['Unknown'])[0] if parties.get('to') else 'Unknown'
    
    date = deed.get('dates', {}).get('recordDate', 'Unknown')
    pages = deed.get('pageLocation', {})
    page_range = f"{pages.get('start', '?')}-{pages.get('end', '?')}"
    
    # Truncate long names
    from_party = from_party[:30] + '...' if len(from_party) > 30 else from_party
    to_party = to_party[:30] + '...' if len(to_party) > 30 else to_party
    
    return f"Deed\n{from_party}\n   ↓\n{to_party}\n{date}\npp. {page_range}"


def _create_mortgage_label(mortgage):
    """Create label text for a mortgage node"""
    parties = mortgage.get('parties', {})
    mortgagee = parties.get('to', ['Unknown'])[0] if parties.get('to') else 'Unknown'
    
    date = mortgage.get('dates', {}).get('recordDate', 'Unknown')
    amount = mortgage.get('monetary', {}).get('mortgageAmount', 'Unknown')
    
    # Format amount
    if isinstance(amount, (int, float)):
        amount_str = f"${amount:,.0f}"
    else:
        amount_str = str(amount)
    
    # Truncate long names
    mortgagee = mortgagee[:25] + '...' if len(mortgagee) > 25 else mortgagee
    
    return f"Mortgage\nTo: {mortgagee}\n{amount_str}\n{date}"


def _check_if_satisfied(mortgage):
    """Check if mortgage has discharge/satisfaction info in notes"""
    notes = mortgage.get('notes', '') or ''
    notes_lower = notes.lower()
    
    discharge_keywords = [
        'discharged',
        'satisfied',
        'released',
        'paid in full',
        'cancelled'
    ]
    
    return any(keyword in notes_lower for keyword in discharge_keywords)


def _normalize_names(names):
    """Normalize party names for comparison"""
    if not names:
        return []
    
    normalized = []
    for name in names:
        if name:
            clean = name.upper().strip()
            clean = clean.replace(',', '').replace('.', '')
            clean = ' '.join(clean.split())
            normalized.append(clean)
    
    return normalized


def _parse_date(date_str):
    """Parse date string to datetime object"""
    if not date_str:
        return None
    
    formats = [
        "%B %d, %Y",
        "%b %d, %Y",
        "%m/%d/%Y",
        "%Y-%m-%d"
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            continue
    
    return None
