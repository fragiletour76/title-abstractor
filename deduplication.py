"""
Deduplication utilities for Pass 1 (inventory) and Pass 2 (extracted documents)
"""
from difflib import SequenceMatcher
import re


def deduplicate_inventory(inventory):
    if not inventory:
        return inventory
    
    unique_docs = []
    seen_signatures = set()
    
    for doc in inventory:
        doc_type = doc.get('type', '').lower().strip()
        pages = doc.get('pages', {})
        start_page = pages.get('start')
        end_page = pages.get('end')
        
        if not start_page or not end_page:
            unique_docs.append(doc)
            continue
        
        exact_signature = f"{doc_type}|{start_page}|{end_page}"
        
        if exact_signature in seen_signatures:
            print(f"  [DEDUP PASS 1] Skipping duplicate: {doc_type} (pages {start_page}-{end_page})")
            continue
        
        is_duplicate = False
        for existing_doc in unique_docs:
            if _is_likely_same_document_inventory(doc, existing_doc):
                print(f"  [DEDUP PASS 1] Skipping likely duplicate: {doc_type} (pages {start_page}-{end_page})")
                is_duplicate = True
                break
        
        if not is_duplicate:
            seen_signatures.add(exact_signature)
            unique_docs.append(doc)
    
    removed_count = len(inventory) - len(unique_docs)
    if removed_count > 0:
        print(f"  [DEDUP PASS 1] Removed {removed_count} duplicate(s) from inventory")
    
    return unique_docs


def _is_likely_same_document_inventory(doc1, doc2):
    type1 = doc1.get('type', '').lower().strip()
    type2 = doc2.get('type', '').lower().strip()
    
    if type1 != type2:
        return False
    
    pages1 = doc1.get('pages', {})
    pages2 = doc2.get('pages', {})
    
    start1, end1 = pages1.get('start'), pages1.get('end')
    start2, end2 = pages2.get('start'), pages2.get('end')
    
    if not all([start1, end1, start2, end2]):
        return False
    
    overlap = not (end1 < start2 or end2 < start1)
    
    if overlap:
        overlap_start = max(start1, start2)
        overlap_end = min(end1, end2)
        overlap_pages = overlap_end - overlap_start + 1
        
        range1_pages = end1 - start1 + 1
        range2_pages = end2 - start2 + 1
        
        overlap_pct1 = overlap_pages / range1_pages if range1_pages > 0 else 0
        overlap_pct2 = overlap_pages / range2_pages if range2_pages > 0 else 0
        
        if overlap_pct1 > 0.5 or overlap_pct2 > 0.5:
            return True
    
    return False


def deduplicate_documents(documents):
    if not documents or len(documents) <= 1:
        return documents
    
    unique_docs = []
    
    for i, doc in enumerate(documents):
        is_duplicate = False
        
        for j, existing_doc in enumerate(unique_docs):
            similarity_score = _calculate_document_similarity(doc, existing_doc)
            
            if similarity_score >= 0.85:
                print(f"  [DEDUP PASS 2] Document {i+1} is {similarity_score*100:.0f}% similar to document {j+1} - merging")
                _merge_documents(existing_doc, doc)
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_docs.append(doc)
    
    removed_count = len(documents) - len(unique_docs)
    if removed_count > 0:
        print(f"  [DEDUP PASS 2] Removed {removed_count} duplicate document(s)")
    
    return unique_docs


def _normalize_string(s):
    """Normalize string for comparison: lowercase, strip, remove extra spaces"""
    if not s:
        return ''
    return ' '.join((s or '').lower().strip().split())


def _calculate_document_similarity(doc1, doc2):
    score = 0.0
    weights = []
    
    recording1_raw = doc1.get('recording', {}).get('locationInstrumentNumber')
    recording2_raw = doc2.get('recording', {}).get('locationInstrumentNumber')
    
    recording1 = _normalize_string(recording1_raw)
    recording2 = _normalize_string(recording2_raw)
    
    if recording1 and recording2:
        if recording1 == recording2:
            score += 0.4
            weights.append(0.4)
        else:
            weights.append(0.4)
    
    type1 = _normalize_string(doc1.get('documentType'))
    type2 = _normalize_string(doc2.get('documentType'))
    
    if type1 and type2:
        if type1 == type2:
            score += 0.2
        elif _normalize_doc_type(type1) == _normalize_doc_type(type2):
            score += 0.15
        weights.append(0.2)
    
    date1_raw = doc1.get('dates', {}).get('recordDate')
    date2_raw = doc2.get('dates', {}).get('recordDate')
    
    date1 = _normalize_string(date1_raw)
    date2 = _normalize_string(date2_raw)
    
    if date1 and date2:
        if date1 == date2:
            score += 0.15
        weights.append(0.15)
    
    parties1_from_raw = doc1.get('parties', {}).get('from', []) or []
    parties1_to_raw = doc1.get('parties', {}).get('to', []) or []
    parties2_from_raw = doc2.get('parties', {}).get('from', []) or []
    parties2_to_raw = doc2.get('parties', {}).get('to', []) or []
    
    parties1_from = set(_normalize_string(p) for p in parties1_from_raw)
    parties1_to = set(_normalize_string(p) for p in parties1_to_raw)
    parties2_from = set(_normalize_string(p) for p in parties2_from_raw)
    parties2_to = set(_normalize_string(p) for p in parties2_to_raw)
    
    if parties1_from and parties2_from and parties1_to and parties2_to:
        from_match = len(parties1_from & parties2_from) / max(len(parties1_from), len(parties2_from))
        to_match = len(parties1_to & parties2_to) / max(len(parties1_to), len(parties2_to))
        parties_score = (from_match + to_match) / 2
        score += 0.15 * parties_score
        weights.append(0.15)
    
    legal1 = (doc1.get('property', {}).get('legalDescription') or '').strip()
    legal2 = (doc2.get('property', {}).get('legalDescription') or '').strip()
    
    if legal1 and legal2:
        ratio = SequenceMatcher(None, legal1[:500], legal2[:500]).ratio()
        score += 0.1 * ratio
        weights.append(0.1)
    
    total_weight = sum(weights)
    if total_weight > 0:
        normalized_score = score / total_weight
    else:
        normalized_score = 0.0
    
    return normalized_score


def _normalize_doc_type(doc_type):
    doc_type = doc_type.lower().strip()
    
    if 'deed' in doc_type:
        return 'deed'
    elif 'mortgage' in doc_type:
        return 'mortgage'
    elif 'satisfaction' in doc_type or 'discharge' in doc_type:
        return 'satisfaction'
    elif 'judgment' in doc_type:
        return 'judgment'
    elif 'lien' in doc_type:
        return 'lien'
    
    return doc_type


def _has_discharge_info(notes):
    """Check if notes contain discharge/satisfaction information"""
    if not notes:
        return False
    
    notes_lower = notes.lower()
    discharge_keywords = [
        'discharged',
        'satisfied',
        'released',
        'paid in full',
        'cancelled',
        'terminated'
    ]
    
    return any(keyword in notes_lower for keyword in discharge_keywords)


def _merge_documents(existing_doc, duplicate_doc):
    """
    Merge duplicate document into existing one.
    Preserves page locations and important notes (especially discharge info).
    """
    # Merge page locations
    existing_pages = existing_doc.get('pageLocation', {})
    duplicate_pages = duplicate_doc.get('pageLocation', {})
    
    if 'allPageLocations' not in existing_doc:
        existing_doc['allPageLocations'] = [existing_pages.copy()]
    
    if duplicate_pages:
        existing_doc['allPageLocations'].append(duplicate_pages)
    
    all_starts = [p.get('start', 999999) for p in existing_doc['allPageLocations'] if p.get('start')]
    all_ends = [p.get('end', 0) for p in existing_doc['allPageLocations'] if p.get('end')]
    
    if all_starts and all_ends:
        existing_doc['pageLocation']['start'] = min(all_starts)
        existing_doc['pageLocation']['end'] = max(all_ends)
        page_ranges = ', '.join([f"{p.get('start')}-{p.get('end')}" for p in existing_doc['allPageLocations']])
        existing_doc['pageLocation']['note'] = f"Document appears on multiple pages: {page_ranges}"
    
    # Merge notes - PRIORITIZE DISCHARGE INFORMATION
    existing_notes = existing_doc.get('notes', '') or ''
    duplicate_notes = duplicate_doc.get('notes', '') or ''
    
    # If duplicate has discharge info but existing doesn't, use duplicate's notes
    if _has_discharge_info(duplicate_notes) and not _has_discharge_info(existing_notes):
        print(f"    → Preserving discharge info from duplicate document")
        existing_doc['notes'] = duplicate_notes
    # If existing has discharge info, keep it
    elif _has_discharge_info(existing_notes):
        pass  # Keep existing
    # If neither has discharge info, combine them if different
    elif duplicate_notes and duplicate_notes != existing_notes:
        if existing_notes:
            existing_doc['notes'] = f"{existing_notes} | {duplicate_notes}"
        else:
            existing_doc['notes'] = duplicate_notes
