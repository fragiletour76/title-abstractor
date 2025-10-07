import re
from typing import Dict, List, Optional

class LegalDescriptionParser:
    """
    Parse legal descriptions to extract structured identifiers
    Priority: metes_bounds > deed_reference > tax_id > lots > address > subdivision
    """
    
    def parse(self, description: str) -> Dict:
        """
        Extract all identifiable components from legal description
        """
        if not description or description.strip() == "":
            return self._empty_result()
        
        desc = description.strip()
        
        return {
            "metes_bounds": self._extract_metes_bounds(desc),
            "deed_reference": self._extract_deed_reference(desc),
            "tax_parcel_id": self._extract_tax_parcel(desc),
            "lot_numbers": self._extract_lot_numbers(desc),
            "block_numbers": self._extract_block_numbers(desc),
            "street_address": self._extract_street_address(desc),
            "subdivision": self._extract_subdivision(desc),
            "map_reference": self._extract_map_reference(desc),
            "raw_text": desc
        }
    
    def _extract_metes_bounds(self, desc: str) -> Optional[Dict]:
        """
        Detect metes and bounds descriptions
        Pattern: "BEGINNING at...", "thence...", bearings, distances
        """
        # Common metes & bounds indicators
        indicators = [
            r'\bBEGINNING\b',
            r'\bCOMMENCING\b',
            r'\bthence\b',
            r'North \d+°',
            r'South \d+°',
            r'East \d+°',
            r'West \d+°',
            r'\d+\s*feet',
            r'\d+\s*chains'
        ]
        
        matches = sum(1 for pattern in indicators if re.search(pattern, desc, re.IGNORECASE))
        
        if matches >= 3:  # If 3+ indicators present, likely metes & bounds
            # Extract starting point
            start_match = re.search(r'(BEGINNING|COMMENCING)\s+at\s+([^;.]+)', desc, re.IGNORECASE)
            starting_point = start_match.group(2) if start_match else None
            
            return {
                "present": True,
                "starting_point": starting_point,
                "full_description": desc
            }
        
        return None
    
    def _extract_deed_reference(self, desc: str) -> Optional[Dict]:
        """
        Extract "being same premises" or "as recorded in" references
        Examples:
        - "Being same premises as Book 1234, Page 567"
        - "as recorded in Liber 456 of Deeds at Page 789"
        """
        patterns = [
            r'[Bb]eing\s+(?:the\s+)?same\s+premises.*?[Bb]ook\s+(\d+).*?[Pp]age\s+(\d+)',
            r'[Bb]eing\s+(?:the\s+)?same\s+premises.*?[Ll]iber\s+(\d+).*?[Pp]age\s+(\d+)',
            r'[Rr]ecorded\s+in.*?[Bb]ook\s+(\d+).*?[Pp]age\s+(\d+)',
            r'[Rr]ecorded\s+in.*?[Ll]iber\s+(\d+).*?[Pp]age\s+(\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, desc)
            if match:
                return {
                    "book": match.group(1),
                    "page": match.group(2),
                    "full_reference": match.group(0)
                }
        
        return None
    
    def _extract_tax_parcel(self, desc: str) -> Optional[str]:
        """
        Extract tax parcel ID
        Common formats: 123.45-6-7, 123-45-6, 12-34-567
        """
        patterns = [
            r'\b(\d{2,3}[\.-]\d{2}[\.-]\d{1,3}[\.-]\d{1,3})\b',  # 123.45-6-7
            r'\b(\d{2,3}[\.-]\d{2}[\.-]\d{1,3})\b',              # 123-45-6
            r'[Tt]ax\s+[Pp]arcel\s*:?\s*([0-9\.-]+)',            # Tax Parcel: 123-45-6
        ]
        
        for pattern in patterns:
            match = re.search(pattern, desc)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_lot_numbers(self, desc: str) -> List[int]:
        """
        Extract lot numbers
        Examples: "Lot 152", "Lots 10, 11 and 12", "Lot One Hundred Fifty-Two (152)"
        Excludes: measurements like "lot 20.06 feet", "lot 21.05 feet"
        """
        lots = []
        
        # Pattern 1: "Lot 152" or "Lot Number 152"
        # But NOT "lot 20.06 feet" or "lot 21 feet"
        # Only match when number immediately follows Lot/Number
        pattern1 = r'\bLots?\s+(?:Number\s+)?(\d{1,4})(?!\d)(?!\s*\.\d)(?!\s*(?:feet|foot|ft))'
        matches = re.finditer(pattern1, desc, re.IGNORECASE)
        for match in matches:
            lot_num = int(match.group(1))
            # Only accept typical lot numbers (1-9999)
            if 1 <= lot_num < 10000:
                lots.append(lot_num)
        
        # Pattern 2: "Lots 10, 11 and 12" (comma-separated list)
        # More strict - must have "Lots" (plural) followed by comma-separated numbers
        pattern2 = r'\bLots\s+((?:\d+\s*(?:,|and|&)\s*)+\d+)(?!\s*(?:feet|foot|ft))'
        matches = re.finditer(pattern2, desc, re.IGNORECASE)
        for match in matches:
            # Extract all numbers from the match
            numbers = re.findall(r'\b(\d+)\b', match.group(1))
            for n in numbers:
                lot_num = int(n)
                if 1 <= lot_num < 10000:
                    lots.append(lot_num)
        
        # Pattern 3: Written numbers "Lot One Hundred Fifty-Two (152)"
        # Only extract the number in parentheses
        pattern3 = r'\bLots?\s+[A-Za-z][A-Za-z\s\-]*\((\d+)\)'
        matches = re.finditer(pattern3, desc, re.IGNORECASE)
        for match in matches:
            lot_num = int(match.group(1))
            if 1 <= lot_num < 10000:
                lots.append(lot_num)
        
        return sorted(list(set(lots)))  # Remove duplicates and sort
    
    def _extract_block_numbers(self, desc: str) -> List[int]:
        """
        Extract block numbers
        Examples: "Block 3", "Blocks 5 and 6"
        """
        blocks = []
        
        pattern = r'\bBlocks?\s+(\d+(?:\s*(?:,|and|&)\s*\d+)*)'
        matches = re.finditer(pattern, desc, re.IGNORECASE)
        for match in matches:
            numbers = re.findall(r'\d+', match.group(1))
            blocks.extend([int(n) for n in numbers])
        
        return sorted(list(set(blocks)))
    
    def _extract_street_address(self, desc: str) -> Optional[str]:
        """
        Extract street address
        Examples: "123 Main Street", "456 Oak Avenue"
        """
        # Pattern: number + street name + street type
        pattern = r'\b(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Way|Court|Ct))\b'
        match = re.search(pattern, desc, re.IGNORECASE)
        
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_subdivision(self, desc: str) -> Optional[str]:
        """
        Extract subdivision/development name
        Examples: "Genesee Manor Section D", "Oak Hill Estates"
        """
        # Common patterns
        patterns = [
            r'([A-Z][A-Za-z\s]+(?:Manor|Estates|Heights|Hills|Park|Gardens|Acres|Subdivision)(?:\s+Section\s+["\']?[A-Z0-9]["\']?)?)',
            r'map\s+of\s+(?:the\s+)?([A-Z][A-Za-z\s]+(?:Manor|Estates)(?:\s+Section\s+["\']?[A-Z0-9]["\']?)?)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, desc)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_map_reference(self, desc: str) -> Optional[str]:
        """
        Extract map filing reference
        Example: "filed in County Clerk's Office August 28, 1925"
        """
        pattern = r'filed\s+(?:in\s+)?[^.]*?(?:Clerk|County|Office)[^.]*?(?:\d{4})'
        match = re.search(pattern, desc, re.IGNORECASE)
        
        if match:
            return match.group(0).strip()
        
        return None
    
    def _empty_result(self) -> Dict:
        """Return empty result for blank descriptions"""
        return {
            "metes_bounds": None,
            "deed_reference": None,
            "tax_parcel_id": None,
            "lot_numbers": [],
            "block_numbers": [],
            "street_address": None,
            "subdivision": None,
            "map_reference": None,
            "raw_text": ""
        }
    
    def compare(self, desc_a: Dict, desc_b: Dict) -> str:
        """
        Compare two parsed descriptions
        Returns: SAME, SUBSET, SUPERSET, PARTIAL_OVERLAP, DIFFERENT
        
        Priority order:
        1. Metes & bounds
        2. Deed reference
        3. Tax parcel ID
        4. Lot numbers
        5. Street address
        6. Subdivision
        """
        # Priority 1: Metes & bounds
        if desc_a.get('metes_bounds') and desc_b.get('metes_bounds'):
            # If both have metes & bounds, compare starting points
            start_a = desc_a['metes_bounds'].get('starting_point', '')
            start_b = desc_b['metes_bounds'].get('starting_point', '')
            if start_a and start_b and start_a.lower().strip() == start_b.lower().strip():
                return "SAME"
            # If different starting points, consider different
            return "DIFFERENT"
        
        # Priority 2: Deed reference
        ref_a = desc_a.get('deed_reference')
        ref_b = desc_b.get('deed_reference')
        if ref_a and ref_b:
            if ref_a['book'] == ref_b['book'] and ref_a['page'] == ref_b['page']:
                return "SAME"
        
        # Priority 3: Tax parcel ID
        tax_a = desc_a.get('tax_parcel_id')
        tax_b = desc_b.get('tax_parcel_id')
        if tax_a and tax_b:
            if tax_a == tax_b:
                return "SAME"
            else:
                return "DIFFERENT"
        
        # Priority 4: Lot numbers
        lots_a = set(desc_a.get('lot_numbers', []))
        lots_b = set(desc_b.get('lot_numbers', []))
        
        if lots_a and lots_b:
            if lots_a == lots_b:
                return "SAME"
            elif lots_a.issubset(lots_b):
                return "SUBSET"  # A is part of B
            elif lots_a.issuperset(lots_b):
                return "SUPERSET"  # A includes B plus more
            elif lots_a.intersection(lots_b):
                return "PARTIAL_OVERLAP"
            else:
                return "DIFFERENT"
        
        # Priority 5: Street address
        addr_a = desc_a.get('street_address')
        addr_b = desc_b.get('street_address')
        if addr_a and addr_b:
            if addr_a.lower().strip() == addr_b.lower().strip():
                return "SAME"
            else:
                return "DIFFERENT"
        
        # Priority 6: Subdivision
        sub_a = desc_a.get('subdivision')
        sub_b = desc_b.get('subdivision')
        if sub_a and sub_b:
            if sub_a.lower().strip() == sub_b.lower().strip():
                # Same subdivision but no specific lots = uncertain
                return "SAME"
            else:
                return "DIFFERENT"
        
        # If we can't determine, return DIFFERENT (conservative approach)
        return "DIFFERENT"
