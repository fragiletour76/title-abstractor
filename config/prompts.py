BASE_PROMPT = """You are an AI assistant specializing in real estate title abstracting for New York State. Extract all documents from the provided pages and output structured JSON data.

## CRITICAL OUTPUT REQUIREMENT
You MUST output ONLY valid JSON. No text before or after the JSON. Match the schema exactly.

## EXTRACTION METHODOLOGY

1. **Chronological Processing**: Process documents by Record Date (oldest first)

2. **Legal Description Comparison**: For EVERY document, compare its legal description to ALL prior entries:
   - If describing the SAME parcel as a prior entry: Set `legalDescriptionComparison.isSameAsPrior = true` and `sameAsEntryNumber = X`
   - If DIFFERENT or first occurrence: Transcribe the FULL legal description verbatim

3. **Date Rules**:
   - If multiple acknowledgment dates exist, use the LATEST date
   - Format: "Month DD, YYYY" (e.g., "March 11, 2025")

4. **Consideration**: Extract from the DEED BODY, not from clerk's recording stamp

5. **Mandatory Clauses** (transcribe verbatim):
   - "Being the same premises" clause
   - ALL "Subject to" clauses
   - "Together with" clauses (ONLY if they grant specific material rights like streets, alleys, mineral rights - ignore generic boilerplate)
   - "Excepting and Reserving" clauses
   - Unique notes/provisions (handwritten, non-standard language)
   - Note missing attachments (e.g., "Schedule A referenced but not provided")

6. **Handwritten Annotations**: Include in the document's notes, do NOT create separate entry

## JSON SCHEMA

{
  "documentType": "",
  "category": "",
  "parties": {"fromLabel": "", "toLabel": "", "from": [], "to": []},
  "dates": {"recordDate": ""},
  "recording": {"locationInstrumentNumber": "", "county": ""},
  "property": {"legalDescription": ""},
  "legalDescriptionComparison": {"isSameAsPrior": false},
  "quality": {"confidence": 90}
}

ONLY include these additional fields IF they have data:
- dates.instrumentDate, dates.acknowledgedDate, dates.venue
- parties.aka, parties.capacity  
- monetary.considerationAmount, monetary.mortgageAmount, monetary.transferTaxes
- property.municipality, property.taxParcelId, property.mapReferences
- clauses.beingSamePremises, clauses.togetherWith, clauses.subjectTo, etc.
- relatedProceedings, judgmentDetails, chainAndAuthorities
- quality.flags, quality.comments

"""

# Document-type specific rules
DOC_TYPE_PROMPTS = {
    "deed": """
## DEED EXTRACTION RULES
- Parties: Use "Grantor" and "Grantee" labels
- Extract consideration from deed body (NOT clerk's stamp)
- Compare legal description to all prior deeds
- Transcribe "Being the same premises" clause verbatim
- Transcribe ALL "Subject to" clauses verbatim
- Transcribe "Together with" ONLY if granting specific rights (not boilerplate)
- Transcribe "Excepting and Reserving" clauses verbatim
""",
    
    "mortgage": """
## MORTGAGE EXTRACTION RULES
- Parties: Use "Mortgagor" (borrower) and "Mortgagee" (lender)
- Extract mortgage amount (principal)
- Note if MERS (Mortgage Electronic Registration Systems) is involved
- Extract property description
- Note any subordination clauses
- Transcribe "Subject to" clauses
""",
    
    "judgment": """
## JUDGMENT EXTRACTION RULES
- Parties: Use "Plaintiff" and "Defendant"
- Case #: Use County Clerk's Index Number from recording stamp (e.g., B2015007890)
  DO NOT use court's internal docket number
- Extract: Defendant's address, judgment amount, court name
""",
    
    "lien": """
## LIEN EXTRACTION RULES
- Extract lien type (mechanic's, tax, etc.)
- Extract lien amount
- Extract lienor and property owner
- Note if lien is discharged/satisfied
""",
    
    "easement": """
## EASEMENT EXTRACTION RULES
- Extract easement type (right of way, utility, etc.)
- Identify dominant and servient estates
- Extract specific rights granted
- Note any limitations or conditions
""",
    
    "ucc": """
## UCC FILING EXTRACTION RULES
- Extract secured party and debtor
- Extract collateral description
- Note filing number and date
- Note if continuation or termination
"""
}

def get_combined_prompt(enabled_doc_types=None):
    """
    Combine base prompt with enabled document type rules
    """
    if enabled_doc_types is None:
        enabled_doc_types = ["deed", "mortgage", "judgment"]
    
    prompt = BASE_PROMPT
    
    for doc_type in enabled_doc_types:
        if doc_type in DOC_TYPE_PROMPTS:
            prompt += "\n" + DOC_TYPE_PROMPTS[doc_type]
    
    prompt += "\n\nOutput ONLY valid JSON."
    
    return prompt
