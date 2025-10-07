from typing import List, Dict, Tuple
from src.legal_description_parser import LegalDescriptionParser

class RelationshipDetector:
    """
    Analyze relationships between all documents
    Build chains based on legal description comparisons
    """
    
    def __init__(self):
        self.parser = LegalDescriptionParser()
    
    def analyze_all_documents(self, documents: List[Dict]) -> Dict:
        """
        Compare all documents to each other
        Returns relationship matrix and chain groupings
        """
        # Step 1: Parse all legal descriptions
        parsed_descriptions = {}
        for i, doc in enumerate(documents):
            doc_id = i + 1
            legal_desc = doc.get('property', {}).get('legalDescription', '')
            parsed_descriptions[doc_id] = {
                'parsed': self.parser.parse(legal_desc),
                'doc': doc,
                'doc_id': doc_id
            }
        
        # Step 2: Build relationship matrix
        relationships = []
        for doc_a_id, data_a in parsed_descriptions.items():
            for doc_b_id, data_b in parsed_descriptions.items():
                if doc_a_id >= doc_b_id:
                    continue  # Skip self and already compared pairs
                
                relationship = self.parser.compare(
                    data_a['parsed'],
                    data_b['parsed']
                )
                
                relationships.append({
                    'doc_a': doc_a_id,
                    'doc_b': doc_b_id,
                    'relationship': relationship,
                    'parsed_a': data_a['parsed'],
                    'parsed_b': data_b['parsed']
                })
        
        # Step 3: Build chains
        chains = self._build_chains(parsed_descriptions, relationships)
        
        return {
            'relationships': relationships,
            'chains': chains,
            'parsed_descriptions': parsed_descriptions
        }
    
    def _build_chains(self, parsed_descriptions: Dict, relationships: List[Dict]) -> List[Dict]:
        """
        Group documents into chains based on relationships
        """
        # Group documents by SAME or SUBSET relationships
        chain_groups = {}
        processed = set()
        
        # Start with documents that have SAME relationships
        for rel in relationships:
            if rel['relationship'] == 'SAME':
                doc_a = rel['doc_a']
                doc_b = rel['doc_b']
                
                # Find which chain they belong to
                chain_id = None
                for cid, members in chain_groups.items():
                    if doc_a in members or doc_b in members:
                        chain_id = cid
                        break
                
                if chain_id:
                    chain_groups[chain_id].add(doc_a)
                    chain_groups[chain_id].add(doc_b)
                else:
                    # Create new chain
                    chain_id = f"chain_{len(chain_groups) + 1}"
                    chain_groups[chain_id] = {doc_a, doc_b}
                
                processed.add(doc_a)
                processed.add(doc_b)
        
        # Handle SUBSET/SUPERSET relationships (property splits)
        parent_child_relationships = []
        for rel in relationships:
            if rel['relationship'] in ['SUBSET', 'SUPERSET']:
                parent_child_relationships.append(rel)
        
        # Documents not in any chain get their own chain
        for doc_id in parsed_descriptions.keys():
            if doc_id not in processed:
                # Check if it's a deed
                doc_type = parsed_descriptions[doc_id]['doc'].get('documentType', '').lower()
                if 'deed' in doc_type:
                    chain_id = f"chain_{len(chain_groups) + 1}"
                    chain_groups[chain_id] = {doc_id}
        
        # Convert to chain objects
        chains = []
        for chain_id, doc_ids in chain_groups.items():
            # Get property description from first doc
            first_doc_id = min(doc_ids)
            parsed = parsed_descriptions[first_doc_id]['parsed']
            
            # Build property description
            property_desc = self._build_property_description(parsed)
            
            # Get first owner (grantor of earliest deed)
            first_owner = self._get_first_owner(doc_ids, parsed_descriptions)
            
            # Get earliest date for sorting
            earliest_date = self._get_earliest_date(doc_ids, parsed_descriptions)
            
            chains.append({
                'chain_id': chain_id,
                'document_ids': sorted(list(doc_ids)),
                'property_description': property_desc,
                'first_owner': first_owner,
                'earliest_date': earliest_date,
                'parent': None,  # Will be set in split detection
                'children': []
            })
        
        # Detect parent-child relationships (splits)
        chains = self._detect_splits(chains, parent_child_relationships, parsed_descriptions)
        
        # Sort chains by earliest date (oldest first)
        chains.sort(key=lambda c: c['earliest_date'])
        
        return chains
    
    def _build_property_description(self, parsed: Dict) -> str:
        """Build concise, human-readable property description from parsed data"""
        parts = []
        
        # Priority: Lot numbers first
        if parsed.get('lot_numbers'):
            lots = parsed['lot_numbers']
            if len(lots) == 1:
                parts.append(f"Lot {lots[0]}")
            elif len(lots) <= 3:
                parts.append(f"Lots {', '.join(map(str, lots))}")
            else:
                parts.append(f"Lots {lots[0]}-{lots[-1]} and others")
        
        # Then subdivision
        if parsed.get('subdivision'):
            sub = parsed['subdivision']
            # Clean up subdivision name
            sub = sub.replace('"', '').replace("'", "")
            parts.append(sub)
        
        # Then block if present
        if parsed.get('block_numbers'):
            blocks = parsed['block_numbers']
            if len(blocks) == 1:
                parts.append(f"Block {blocks[0]}")
        
        # Street address as fallback
        if not parts and parsed.get('street_address'):
            parts.append(parsed['street_address'])
        
        # Tax ID as last resort
        if not parts and parsed.get('tax_parcel_id'):
            parts.append(f"Tax Parcel {parsed['tax_parcel_id']}")
        
        return ', '.join(parts) if parts else "Property description unavailable"
    
    def _get_first_owner(self, doc_ids: set, parsed_descriptions: Dict) -> str:
        """Get the first owner (grantor of earliest deed) in the chain"""
        # Sort by record date
        docs_with_dates = []
        for doc_id in doc_ids:
            doc = parsed_descriptions[doc_id]['doc']
            date_str = doc.get('dates', {}).get('recordDate', '')
            docs_with_dates.append((doc_id, date_str, doc))
        
        # Sort by date (convert to comparable format)
        docs_with_dates.sort(key=lambda x: self._date_sort_key(x[1]))
        
        if docs_with_dates:
            first_doc = docs_with_dates[0][2]
            from_parties = first_doc.get('parties', {}).get('from', [])
            if from_parties:
                return from_parties[0] if isinstance(from_parties, list) else str(from_parties)
        
        return "Unknown"
    
    def _get_earliest_date(self, doc_ids: set, parsed_descriptions: Dict) -> str:
        """Get the earliest record date in the chain for sorting"""
        dates = []
        for doc_id in doc_ids:
            doc = parsed_descriptions[doc_id]['doc']
            date_str = doc.get('dates', {}).get('recordDate', '')
            if date_str:
                dates.append(date_str)
        
        if dates:
            dates.sort(key=self._date_sort_key)
            return dates[0]
        
        return "Unknown"
    
    def _date_sort_key(self, date_str: str) -> tuple:
        """Convert date string to sortable tuple"""
        import re
        from datetime import datetime
        
        if not date_str or date_str == "Unknown":
            return (9999, 12, 31)  # Sort unknowns to end
        
        # Try parsing "Month DD, YYYY" format
        try:
            dt = datetime.strptime(date_str, "%B %d, %Y")
            return (dt.year, dt.month, dt.day)
        except:
            pass
        
        # Try other common formats
        for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%B %d %Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return (dt.year, dt.month, dt.day)
            except:
                continue
        
        # If all else fails, try to extract year
        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if year_match:
            year = int(year_match.group(0))
            return (year, 1, 1)
        
        return (9999, 12, 31)
    
    def _detect_splits(self, chains: List[Dict], parent_child_rels: List[Dict], parsed_descriptions: Dict) -> List[Dict]:
        """
        Detect parent-child relationships (property splits)
        Mark chains that are splits from larger parcels
        """
        # For each SUBSET relationship, mark the subset as a child
        for rel in parent_child_rels:
            if rel['relationship'] == 'SUBSET':
                # doc_a is subset of doc_b
                subset_doc = rel['doc_a']
                superset_doc = rel['doc_b']
            elif rel['relationship'] == 'SUPERSET':
                # doc_a is superset of doc_b
                subset_doc = rel['doc_b']
                superset_doc = rel['doc_a']
            else:
                continue
            
            # Find which chains these belong to
            subset_chain = None
            superset_chain = None
            
            for chain in chains:
                if subset_doc in chain['document_ids']:
                    subset_chain = chain
                if superset_doc in chain['document_ids']:
                    superset_chain = chain
            
            # Mark relationship
            if subset_chain and superset_chain and subset_chain != superset_chain:
                subset_chain['parent'] = superset_chain['chain_id']
                if subset_chain['chain_id'] not in superset_chain['children']:
                    superset_chain['children'].append(subset_chain['chain_id'])
        
        return chains
