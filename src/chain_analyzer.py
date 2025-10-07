from datetime import datetime
from typing import List, Dict, Optional
import re

class ChainAnalyzer:
    """
    Analyzes chain of title after raw extraction
    - Parses and validates dates
    - Sorts documents chronologically
    - Compares legal descriptions
    - Updates chain of title references
    """
    
    def __init__(self):
        self.date_formats = [
            "%B %d, %Y",      # March 11, 2025
            "%b %d, %Y",      # Mar 11, 2025
            "%m/%d/%Y",       # 03/11/2025
            "%Y-%m-%d",       # 2025-03-11
            "%m-%d-%Y",       # 03-11-2025
            "%B %d %Y",       # March 11 2025 (no comma)
        ]
    
    def analyze_chain(self, documents: List[Dict]) -> tuple[List[Dict], List[str]]:
        """
        Main analysis function
        Returns: (sorted_documents, warnings)
        """
        warnings = []
        
        if not documents:
            return documents, ["No documents to analyze"]
        
        # Step 1: Parse and validate dates
        docs_with_dates = []
        docs_without_dates = []
        
        for i, doc in enumerate(documents):
            record_date = doc.get('dates', {}).get('recordDate')
            
            # Handle None, null string, or empty string
            if not record_date or record_date == 'None' or record_date.strip() == '':
                warnings.append(f"Document {i+1} ({doc.get('documentType', 'Unknown')}): Missing record date")
                doc['_parsed_record_date'] = None
                docs_without_dates.append(doc)
            else:
                parsed = self._parse_date(record_date)
                
                if not parsed:
                    warnings.append(f"Document {i+1}: Could not parse record date '{record_date}'")
                    doc['_parsed_record_date'] = None
                    docs_without_dates.append(doc)
                else:
                    doc['_parsed_record_date'] = parsed
                    docs_with_dates.append(doc)
        
        # Step 2: Sort documents with valid dates
        sorted_docs_with_dates = sorted(docs_with_dates, key=lambda d: d.get('_parsed_record_date', datetime.min))
        
        # Step 3: Add documents without dates at the end (preserving their original order)
        sorted_docs = sorted_docs_with_dates + docs_without_dates
        
        # Step 4: Validate chronological order (only for docs with dates)
        for i in range(len(sorted_docs_with_dates) - 1):
            date1 = sorted_docs_with_dates[i].get('_parsed_record_date')
            date2 = sorted_docs_with_dates[i+1].get('_parsed_record_date')
            
            if date1 and date2 and date1 > date2:
                warnings.append(f"Date order issue between documents {i+1} and {i+2}")
        
        # Step 5: Compare legal descriptions and update references
        for i, doc in enumerate(sorted_docs):
            current_desc = doc.get('property', {}).get('legalDescription', '')
            
            if not current_desc:
                continue
            
            # Compare to all prior documents
            same_as = None
            for j in range(i):
                prior_doc = sorted_docs[j]
                prior_desc = prior_doc.get('property', {}).get('legalDescription', '')
                
                if self._descriptions_match(current_desc, prior_desc):
                    same_as = j + 1  # Entry number (1-indexed)
                    break
            
            # Update legal description comparison
            ldc = doc.get('legalDescriptionComparison', {})
            if same_as:
                ldc['isSameAsPrior'] = True
                ldc['sameAsEntryNumber'] = same_as
                ldc['differenceSummary'] = f"Same as entry #{same_as}"
            else:
                ldc['isSameAsPrior'] = False
                ldc['sameAsEntryNumber'] = None
                if i > 0:
                    ldc['differenceSummary'] = "Different parcel or first occurrence"
            
            doc['legalDescriptionComparison'] = ldc
        
        # Step 6: Validate "same as" references make sense
        for i, doc in enumerate(sorted_docs):
            ldc = doc.get('legalDescriptionComparison', {})
            if ldc.get('isSameAsPrior'):
                ref_num = ldc.get('sameAsEntryNumber')
                if ref_num and ref_num > i + 1:
                    warnings.append(
                        f"Document {i+1}: References entry #{ref_num} which comes after it"
                    )
        
        # Step 7: Check for gaps in timeline (only between docs with dates)
        gaps = self._find_timeline_gaps(sorted_docs_with_dates)
        warnings.extend(gaps)
        
        # Step 8: Clean up temporary fields
        for doc in sorted_docs:
            if '_parsed_record_date' in doc:
                del doc['_parsed_record_date']
        
        return sorted_docs, warnings
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into datetime object"""
        if not date_str or date_str == 'None':
            return None
        
        date_str = date_str.strip()
        
        for fmt in self.date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None
    
    def _descriptions_match(self, desc1: str, desc2: str) -> bool:
        """
        Compare two legal descriptions to determine if they describe the same parcel
        Uses fuzzy matching to handle minor wording differences
        """
        if not desc1 or not desc2:
            return False
        
        # Normalize for comparison
        d1 = self._normalize_description(desc1)
        d2 = self._normalize_description(desc2)
        
        # Exact match after normalization
        if d1 == d2:
            return True
        
        # Check if one contains the other (for partial matches)
        if len(d1) > 50 and len(d2) > 50:  # Only for substantial descriptions
            if d1 in d2 or d2 in d1:
                return True
        
        # Check for key identifiers match (lot, block, etc.)
        identifiers1 = self._extract_identifiers(desc1)
        identifiers2 = self._extract_identifiers(desc2)
        
        if identifiers1 and identifiers2:
            # If they have the same lot/block/parcel numbers, likely same property
            if identifiers1 == identifiers2:
                return True
        
        # Check similarity ratio (for very similar descriptions)
        similarity = self._similarity_ratio(d1, d2)
        if similarity > 0.85:  # 85% similar
            return True
        
        return False
    
    def _normalize_description(self, desc: str) -> str:
        """Normalize description for comparison"""
        # Lowercase
        desc = desc.lower()
        
        # Remove extra whitespace
        desc = re.sub(r'\s+', ' ', desc)
        
        # Standardize common abbreviations
        replacements = {
            'ft.': 'feet',
            'ft': 'feet',
            'n.': 'north',
            's.': 'south',
            'e.': 'east',
            'w.': 'west',
            'st.': 'street',
            'ave.': 'avenue',
            'rd.': 'road',
            'blvd.': 'boulevard',
        }
        
        for abbr, full in replacements.items():
            desc = desc.replace(abbr, full)
        
        return desc.strip()
    
    def _extract_identifiers(self, desc: str) -> Dict:
        """Extract key identifiers like lot, block, parcel numbers"""
        identifiers = {}
        
        # Look for lot numbers
        lot_match = re.search(r'lot\s*(?:no\.?\s*)?(\d+)', desc, re.IGNORECASE)
        if lot_match:
            identifiers['lot'] = lot_match.group(1)
        
        # Look for block numbers
        block_match = re.search(r'block\s*(?:no\.?\s*)?(\d+)', desc, re.IGNORECASE)
        if block_match:
            identifiers['block'] = block_match.group(1)
        
        # Look for parcel/tax map numbers
        parcel_match = re.search(r'(?:parcel|tax\s*map)\s*(?:no\.?\s*)?([0-9\.\-]+)', desc, re.IGNORECASE)
        if parcel_match:
            identifiers['parcel'] = parcel_match.group(1)
        
        return identifiers
    
    def _similarity_ratio(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings (0-1)"""
        if not s1 or not s2:
            return 0.0
        
        # Simple character-based similarity
        set1 = set(s1)
        set2 = set(s2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def _find_timeline_gaps(self, sorted_docs: List[Dict]) -> List[str]:
        """Find significant gaps in the timeline (only for docs with valid dates)"""
        warnings = []
        
        for i in range(len(sorted_docs) - 1):
            date1 = sorted_docs[i].get('_parsed_record_date')
            date2 = sorted_docs[i+1].get('_parsed_record_date')
            
            # Only check gaps if both dates are valid
            if date1 and date2:
                gap_years = (date2 - date1).days / 365.25
                
                # Warn if gap > 5 years
                if gap_years > 5:
                    warnings.append(
                        f"Large time gap ({int(gap_years)} years) between documents {i+1} and {i+2}"
                    )
        
        return warnings
