import streamlit as st
import json
import graphviz

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
    st.caption("This chart shows how ownership transferred for the primary parcel")
    
    # Identify the main chain (documents with same legal description)
    main_chain = _identify_main_chain(documents)
    related_docs = _identify_related_documents(documents, main_chain)
    
    # Create flowchart
    dot = graphviz.Digraph(comment='Chain of Title')
    dot.attr(rankdir='TB')  # Top to bottom
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial')
    
    # Add main chain nodes
    prev_node = None
    for i, doc in enumerate(main_chain):
        node_id = f"doc_{doc['id']}"
        
        # Node styling based on document type
        if doc['type'] == 'Deed':
            color = '#e3f2fd'  # Light blue
        elif doc['type'] == 'Mortgage':
            color = '#ffebee'  # Light red
        else:
            color = '#f5f5f5'  # Light gray
        
        # Node label
        label = _create_node_label(doc)
        
        dot.node(node_id, label, fillcolor=color)
        
        # Connect to previous node
        if prev_node:
            dot.edge(prev_node, node_id, label=doc['type'])
        
        prev_node = node_id
        
        # Add related documents (mortgages, liens) as side branches
        related = related_docs.get(doc['id'], [])
        for j, related_doc in enumerate(related):
            related_id = f"related_{doc['id']}_{j}"
            related_label = _create_node_label(related_doc, compact=True)
            
            if related_doc['type'] == 'Mortgage':
                dot.node(related_id, related_label, fillcolor='#ffcdd2', shape='note')
                dot.edge(node_id, related_id, label='Mortgage', style='dashed')
            elif 'Satisfaction' in related_doc['type']:
                dot.node(related_id, related_label, fillcolor='#c8e6c9', shape='note')
                dot.edge(node_id, related_id, label='Satisfied', style='dashed', color='green')
            else:
                dot.node(related_id, related_label, fillcolor='#fff9c4', shape='note')
                dot.edge(node_id, related_id, label=related_doc['type'], style='dashed')
    
    # Render
    st.graphviz_chart(dot)
    
    # Legend
    with st.expander("📖 Chart Legend"):
        st.markdown("""
        - **Blue boxes**: Property transfers (Deeds)
        - **Red notes**: Mortgages (liens on property)
        - **Green notes**: Satisfied/discharged documents
        - **Yellow notes**: Other related documents
        - **Solid arrows**: Ownership transfer
        - **Dashed arrows**: Related documents
        """)
    
    # Document details
    st.divider()
    st.subheader("Chain Details")
    
    for i, doc in enumerate(main_chain, 1):
        with st.expander(f"{i}. {doc['type']} - {doc['date']} (Pages {doc['pages']})"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**From:** {doc['from']}")
                st.write(f"**To:** {doc['to']}")
            with col2:
                st.write(f"**Date:** {doc['date']}")
                st.write(f"**Pages:** {doc['pages']}")
            
            # Show related documents
            related = related_docs.get(doc['id'], [])
            if related:
                st.write("**Related Documents:**")
                for rel in related:
                    st.write(f"  - {rel['type']} ({rel['date']})")

def _identify_main_chain(documents):
    """
    Identify the main chain of title (primary parcel transfers)
    Returns list of documents in chronological order
    """
    # Find documents that are deeds and form a chain
    deeds = []
    
    for i, doc in enumerate(documents, 1):
        doc_type = doc.get('documentType', '')
        
        if 'deed' in doc_type.lower() and 'satisfaction' not in doc_type.lower():
            parties = doc.get('parties', {})
            dates = doc.get('dates', {})
            pages = doc.get('pageLocation', {})
            
            from_party = parties.get('from', [''])[0] if parties.get('from') else 'N/A'
            to_party = parties.get('to', [''])[0] if parties.get('to') else 'N/A'
            
            deeds.append({
                'id': i,
                'type': doc_type,
                'from': from_party,
                'to': to_party,
                'date': dates.get('recordDate', 'N/A'),
                'pages': f"{pages.get('start', '?')}-{pages.get('end', '?')}",
                'full_doc': doc
            })
    
    return deeds

def _identify_related_documents(documents, main_chain):
    """
    Identify mortgages, liens, satisfactions related to each deed in main chain
    Returns dict mapping deed_id to list of related documents
    """
    related = {}
    main_chain_ids = {d['id'] for d in main_chain}
    
    for i, doc in enumerate(documents, 1):
        if i in main_chain_ids:
            continue  # Skip main chain documents
        
        doc_type = doc.get('documentType', '')
        parties = doc.get('parties', {})
        dates = doc.get('dates', {})
        pages = doc.get('pageLocation', {})
        
        from_party = parties.get('from', [''])[0] if parties.get('from') else 'N/A'
        to_party = parties.get('to', [''])[0] if parties.get('to') else 'N/A'
        
        # Try to match to a deed in main chain by parties or date proximity
        for deed in main_chain:
            # Simple matching: if mortgagor matches deed grantee
            if from_party == deed['to'] or to_party == deed['to']:
                if deed['id'] not in related:
                    related[deed['id']] = []
                
                related[deed['id']].append({
                    'id': i,
                    'type': doc_type,
                    'from': from_party,
                    'to': to_party,
                    'date': dates.get('recordDate', 'N/A'),
                    'pages': f"{pages.get('start', '?')}-{pages.get('end', '?')}"
                })
                break
    
    return related

def _create_node_label(doc, compact=False):
    """Create label text for a node"""
    if compact:
        return f"{doc['type']}\n{doc['date']}"
    else:
        return f"{doc['type']}\n{doc['from']}\n    ↓\n{doc['to']}\n{doc['date']}\npp. {doc['pages']}"
