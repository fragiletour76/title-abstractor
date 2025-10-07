from typing import List, Dict, Set, Optional, Tuple
from datetime import datetime
import re

class ChainBuilder:
    """
    Build complete chain of title with grantor/grantee verification
    Detect broken chains, overlaps, and other issues
    """
    
    def __init__(self):
        self.chains = []
        self.issues = []
    
    def build_chains(self, chains_data: Dict, documents: List[Dict]) -> Dict:
        """
        Take relationship detector output and build verified chains
        
        Args:
            chains_data: Output from RelationshipDetector
            documents: Original list of documents
        
        Returns:
            Complete chain structure with verification and issues
        """
        chains = chains_data['chains']
        relationships = chains_data['relationships']
        parsed_descriptions = chains_data['parsed_descriptions']
        
        # Build enriched chains with full document data
        enriched_chains = self._enrich_chains(chains, documents)
        
        # Verify grantor/grantee connections within each chain
        for chain in enriched_chains:
            self._verify_party_connections(chain)
        
        # Detect overlaps between chains
        self._detect_overlaps(enriched_chains, relationships)
        
        # Detect reunification (split parcels coming back together)
        self._detect_reunification(enriched_chains)
        
        # Build parent/child hierarchy display
        hierarchy = self._build_hierarchy(enriched_chains)
        
        return {
            'chains': enriched_chains,
            'hierarchy': hierarchy,
            'issues': self.issues,
            'summary': self._build_summary(enriched_chains)
        }
    
    def _enrich_chains(self, chains: List[Dict], documents: List[Dict]) -> List[Dict]:
        """Add full document data to each chain"""
        enriched = []
        
        for chain in chains:
            # Get full documents for this chain
            chain_docs = []
            for doc_id in chain['document_ids']:
                doc = documents[doc_id - 1]  # 0-indexed
                chain_docs.append({
                    'doc_id': doc_id,
                    'doc_type': doc.get('documentType', 'Unknown'),
                    'parties': doc.get('parties', {}),
                    'dates': doc.get('dates', {}),
                    'recording': doc.get('recording', {}),
                    'property': doc.get('property', {}),
                    'full_doc': doc
                })
            
            # Sort by date, then by recording location (book/page)
            chain_docs.sort(key=lambda d: (
                self._date_sort_key(d['dates'].get('recordDate', '')),
                self._recording_sort_key(d['recording'].get('locationInstrumentNumber', ''))
            ))
            
            enriched.append({
                **chain,
                'documents': chain_docs,
                'issues': [],
                'verified': False
            })
        
        return enriched
    
    def _verify_party_connections(self, chain: Dict):
        """
        Verify that grantee of doc N becomes grantor of doc N+1
        Flag broken chains
        """
        docs = chain['documents']
        
        # Only verify deeds (not mortgages, judgments, etc.)
        deeds = [d for d in docs if 'deed' in d['doc_type'].lower()]
        
        if len(deeds) < 2:
            chain['verified'] = True
            return
        
        broken = False
        for i in range(len(deeds) - 1):
            current_deed = deeds[i]
            next_deed = deeds[i + 1]
            
            # Skip if these are duplicate deeds
            if self._is_duplicate_deed(current_deed, next_deed):
                continue
            
            # Get parties
            current_to = current_deed['parties'].get('to', [])
            next_from = next_deed['parties'].get('from', [])
            
            if not current_to or not next_from:
                continue
            
            # Normalize names for comparison
            current_grantees = [self._normalize_name(n) for n in current_to]
            next_grantors = [self._normalize_name(n) for n in next_from]
            
            # Check if any grantee matches any grantor
            match_found = False
            for grantee in current_grantees:
                for grantor in next_grantors:
                    if self._names_match(grantee, grantor):
                        match_found = True
                        break
                if match_found:
                    break
            
            if not match_found:
                broken = True
                issue = {
                    'type': 'BROKEN_CHAIN',
                    'severity': 'CRITICAL',
                    'chain_id': chain['chain_id'],
                    'doc_a': current_deed['doc_id'],
                    'doc_b': next_deed['doc_id'],
                    'message': f"Document #{next_deed['doc_id']}: {next_from[0] if next_from else 'Unknown'} conveys property but was never a grantee in this chain. Last valid owner: {current_to[0] if current_to else 'Unknown'} (Doc #{current_deed['doc_id']})"
                }
                chain['issues'].append(issue)
                self.issues.append(issue)
        
        chain['verified'] = not broken
    
    def _is_duplicate_deed(self, deed1: Dict, deed2: Dict) -> bool:
        """Check if two deeds are duplicates (same recording info)"""
        rec1 = deed1.get('recording', {}).get('locationInstrumentNumber', '')
        rec2 = deed2.get('recording', {}).get('locationInstrumentNumber', '')
        
        if rec1 and rec2 and rec1 == rec2:
            return True
        
        # Also check if dates and parties are identical
        date1 = deed1.get('dates', {}).get('recordDate', '')
        date2 = deed2.get('dates', {}).get('recordDate', '')
        
        if date1 == date2:
            from1 = set(self._normalize_name(n) for n in deed1.get('parties', {}).get('from', []))
            from2 = set(self._normalize_name(n) for n in deed2.get('parties', {}).get('from', []))
            to1 = set(self._normalize_name(n) for n in deed1.get('parties', {}).get('to', []))
            to2 = set(self._normalize_name(n) for n in deed2.get('parties', {}).get('to', []))
            
            if from1 == from2 and to1 == to2:
                return True
        
        return False
    
    def _detect_overlaps(self, chains: List[Dict], relationships: List[Dict]):
        """Detect if multiple chains reference overlapping parcels"""
        for rel in relationships:
            if rel['relationship'] == 'PARTIAL_OVERLAP':
                # Find which chains these documents belong to
                doc_a_chain = None
                doc_b_chain = None
                
                for chain in chains:
                    if rel['doc_a'] in chain['document_ids']:
                        doc_a_chain = chain
                    if rel['doc_b'] in chain['document_ids']:
                        doc_b_chain = chain
                
                if doc_a_chain and doc_b_chain and doc_a_chain != doc_b_chain:
                    issue = {
                        'type': 'OVERLAP',
                        'severity': 'CRITICAL',
                        'doc_a': rel['doc_a'],
                        'doc_b': rel['doc_b'],
                        'chain_a': doc_a_chain['chain_id'],
                        'chain_b': doc_b_chain['chain_id'],
                        'message': f"Documents #{rel['doc_a']} and #{rel['doc_b']} have overlapping property descriptions. Potential double conveyance."
                    }
                    self.issues.append(issue)
    
    def _detect_reunification(self, chains: List[Dict]):
        """Detect if split parcels are later reunited"""
        # Look for chains where a later document includes parcels from multiple parent chains
        for chain in chains:
            if not chain.get('children'):
                continue
            
            # Check if any later document combines the children
            parent_lots = set()
            for doc_data in chain['documents']:
                lots = doc_data['property'].get('legalDescription', '')
                # Simple check - this could be enhanced
                
            # This is a complex analysis - mark as TODO for now
            # Would need to track if someone later acquires both child parcels
    
    def _build_hierarchy(self, chains: List[Dict]) -> List[Dict]:
        """Build parent/child hierarchy for display"""
        hierarchy = []
        
        # Find root chains (no parent)
        root_chains = [c for c in chains if not c.get('parent')]
        
        for root in root_chains:
            hierarchy_node = self._build_hierarchy_node(root, chains)
            hierarchy.append(hierarchy_node)
        
        return hierarchy
    
    def _build_hierarchy_node(self, chain: Dict, all_chains: List[Dict]) -> Dict:
        """Recursively build hierarchy tree"""
        node = {
            'chain_id': chain['chain_id'],
            'property': chain['property_description'],
            'first_owner': chain['first_owner'],
            'document_ids': chain['document_ids'],
            'verified': chain.get('verified', False),
            'issues': chain.get('issues', []),
            'children': []
        }
        
        # Add children recursively
        if chain.get('children'):
            for child_id in chain['children']:
                child_chain = next((c for c in all_chains if c['chain_id'] == child_id), None)
                if child_chain:
                    child_node = self._build_hierarchy_node(child_chain, all_chains)
                    node['children'].append(child_node)
        
        return node
    
    def _build_summary(self, chains: List[Dict]) -> Dict:
        """Build summary statistics"""
        total_chains = len(chains)
        verified_chains = sum(1 for c in chains if c.get('verified'))
        total_docs = sum(len(c['document_ids']) for c in chains)
        
        issues_by_severity = {
            'CRITICAL': sum(1 for i in self.issues if i['severity'] == 'CRITICAL'),
            'WARNING': sum(1 for i in self.issues if i['severity'] == 'WARNING'),
            'INFO': sum(1 for i in self.issues if i['severity'] == 'INFO')
        }
        
        return {
            'total_chains': total_chains,
            'verified_chains': verified_chains,
            'total_documents': total_docs,
            'total_issues': len(self.issues),
            'issues_by_severity': issues_by_severity
        }
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison"""
        if not name:
            return ""
        
        # Convert to lowercase
        name = name.lower().strip()
        
        # Remove common suffixes
        suffixes = [' jr.', ' jr', ' sr.', ' sr', ' ii', ' iii', ' iv']
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[:-len(suffix)].strip()
        
        # Normalize corporate entities
        corporate_replacements = [
            ('corporation', 'corp'),
            ('incorporated', 'inc'),
            ('company', 'co'),
            ('limited', 'ltd'),
            ('limited liability company', 'llc'),
            ('l.l.c.', 'llc'),
        ]
        for full, abbr in corporate_replacements:
            name = name.replace(full, abbr)
        
        # Remove all punctuation (periods, commas)
        name = re.sub(r'[,\.\']', '', name)
        
        # Collapse multiple spaces
        name = re.sub(r'\s+', ' ', name)
        
        return name.strip()
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """
        Check if two names match
        Handles variations like:
        - "John Smith" vs "John A. Smith" vs "J. Smith"
        - "CORPORATION" vs "Corp." vs "Corp"
        - "Henry H. Rouse" vs "Henry H Rouse"
        """
        if name1 == name2:
            return True
        
        # Split into parts
        parts1 = name1.split()
        parts2 = name2.split()
        
        if not parts1 or not parts2:
            return False
        
        # For corporate entities, match if core words match
        if any(corp in name1 for corp in ['corp', 'inc', 'llc', 'company', 'co']) or \
           any(corp in name2 for corp in ['corp', 'inc', 'llc', 'company', 'co']):
            # Compare significant words (not corp/inc/llc)
            words1 = [w for w in parts1 if w not in ['corp', 'inc', 'llc', 'co', 'company', 'ltd']]
            words2 = [w for w in parts2 if w not in ['corp', 'inc', 'llc', 'co', 'company', 'ltd']]
            
            # Must have at least 2 matching significant words
            matches = sum(1 for w in words1 if w in words2)
            if matches >= min(2, len(words1), len(words2)):
                return True
        
        # Check if last names match
        if parts1[-1] == parts2[-1]:
            # Last names match - check first names
            if len(parts1) >= 2 and len(parts2) >= 2:
                first1 = parts1[0]
                first2 = parts2[0]
                
                # Full match
                if first1 == first2:
                    return True
                
                # Initial match (J vs John)
                if len(first1) == 1 and first2.startswith(first1):
                    return True
                if len(first2) == 1 and first1.startswith(first2):
                    return True
            
            # If only last name available, consider it a match
            return True
        
        return False
    
    def _date_sort_key(self, date_str: str) -> tuple:
        """Convert date string to sortable tuple"""
        if not date_str or date_str == "Unknown":
            return (9999, 12, 31)
        
        try:
            dt = datetime.strptime(date_str, "%B %d, %Y")
            return (dt.year, dt.month, dt.day)
        except:
            pass
        
        for fmt in ["%m/%d/%Y", "%Y-%m-%d", "%B %d %Y"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return (dt.year, dt.month, dt.day)
            except:
                continue
        
        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if year_match:
            return (int(year_match.group(0)), 1, 1)
        
        return (9999, 12, 31)
    
    def _recording_sort_key(self, recording: str) -> tuple:
        """
        Extract book and page for sorting
        Example: "BOOK1131 PAGE 140" -> (1131, 140)
        """
        if not recording:
            return (99999, 99999)
        
        # Try to extract book and page numbers
        book_match = re.search(r'[Bb][Oo][Oo][Kk]\s*(\d+)', recording)
        page_match = re.search(r'[Pp][Aa][Gg][Ee]\s*(\d+)', recording)
        
        book_num = int(book_match.group(1)) if book_match else 99999
        page_num = int(page_match.group(1)) if page_match else 99999
        
        return (book_num, page_num)
