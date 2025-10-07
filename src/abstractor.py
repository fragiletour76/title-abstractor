import json
import re
import time
from typing import Dict, List
from config.prompts import get_combined_prompt
from src.gemini_client import GeminiClient
from src.pdf_processor import PDFProcessor
from src.file_uploader import FileUploader
from src.chain_analyzer import ChainAnalyzer

class TitleAbstractor:
    def __init__(self, api_key: str):
        self.gemini = GeminiClient(api_key)
        self.uploader = FileUploader(api_key)
        self.pdf_processor = PDFProcessor()
        self.chain_analyzer = ChainAnalyzer()
        
        # Map document types to prompt keys
        self.doc_type_mapping = {
            "deed": "deed",
            "warranty deed": "deed",
            "quitclaim deed": "deed",
            "bargain and sale deed": "deed",
            "mortgage": "mortgage",
            "satisfaction of mortgage": "mortgage",
            "assignment of mortgage": "mortgage",
            "judgment": "judgment",
            "lien": "lien",
            "easement": "easement",
            "ucc": "ucc",
            "ucc filing": "ucc",
            "ucc continuation": "ucc"
        }
        
    def process_pdf(self, pdf_path: str, filename: str) -> Dict:
        start_time = time.time()
        
        print(f"Processing: {filename}")
        
        # Get page count
        images = self.pdf_processor.pdf_to_images(pdf_path)
        page_count = len(images)
        print(f"Document has {page_count} pages")
        
        # Upload file once
        print(f"\n=== Uploading to Files API ===")
        file_info = self.uploader.upload_pdf(pdf_path, filename)
        
        try:
            # PASS 1: Get document inventory
            print(f"\n=== PASS 1: Document Inventory ===")
            inventory = self._get_inventory(file_info, page_count)
            print(f"✓ Found {len(inventory)} documents")
            
            # Display inventory
            for i, doc_info in enumerate(inventory, 1):
                doc_type = doc_info.get('type', 'Unknown')
                pages = doc_info.get('pages', {})
                print(f"  {i}. {doc_type} (pages {pages.get('start', '?')}-{pages.get('end', '?')})")
            
            # PASS 2: Extract details for each document
            print(f"\n=== PASS 2: Detailed Extraction ===")
            all_documents = []
            
            for i, doc_info in enumerate(inventory, 1):
                doc_type = doc_info.get('type', 'Unknown')
                pages = doc_info.get('pages', {})
                print(f"  Document {i}/{len(inventory)}: {doc_type} (pages {pages.get('start', '?')}-{pages.get('end', '?')})...", end=" ")
                
                try:
                    doc_detail = self._extract_document_detail(file_info, doc_info, i)
                    
                    # Add page location to document for future highlighting
                    doc_detail['pageLocation'] = pages
                    
                    all_documents.append(doc_detail)
                    print("✓")
                except Exception as e:
                    print(f"✗ Error: {e}")
                    # Continue processing other documents
                    continue
            
            # Clean up
            self.uploader.delete_file(file_info['name'])
            
            # PASS 3: Chain analysis
            print(f"\n=== PASS 3: Chain of Title Analysis ===")
            sorted_docs, warnings = self.chain_analyzer.analyze_chain(all_documents)
            
            if warnings:
                print(f"\n⚠️  Warnings:")
                for warning in warnings:
                    print(f"  - {warning}")
            else:
                print(f"✓ No issues detected")
            
            # Calculate processing time and savings
            processing_time_seconds = time.time() - start_time
            
            # Count document types
            num_documents = len(sorted_docs)
            num_deeds = sum(1 for d in sorted_docs if 'deed' in d.get('documentType', '').lower())
            num_mortgages = sum(1 for d in sorted_docs if 'mortgage' in d.get('documentType', '').lower())
            
            # Count total characters in legal descriptions
            total_chars = sum(len(d.get('property', {}).get('legalDescription', '')) for d in sorted_docs)
            
            # Manual time estimate
            # 4 min per document + 1 min extra for deeds/mortgages + typing time (50 WPM = 250 chars/min)
            manual_time_minutes = (
                (num_documents * 4) +           # 4 min per document
                (num_deeds * 1) +               # Extra 1 min for deeds
                (num_mortgages * 1) +           # Extra 1 min for mortgages
                (total_chars / 250)             # 50 WPM = 250 chars/min
            )
            
            time_saved_minutes = manual_time_minutes - (processing_time_seconds / 60)
            time_saved_percent = (time_saved_minutes / manual_time_minutes * 100) if manual_time_minutes > 0 else 0
            
            # Cost savings at $23/hour
            hourly_rate = 23
            manual_cost = (manual_time_minutes / 60) * hourly_rate
            ai_cost = (processing_time_seconds / 60 / 60) * hourly_rate
            cost_saved = manual_cost - ai_cost
            
            # Build final result
            final_result = {
                "source": {
                    "fileName": filename,
                    "county": "",
                    "state": "NY"
                },
                "review": {
                    "totalPagesProcessed": page_count,
                    "allPagesReviewed": True,
                    "chainWarnings": warnings,
                    "extractionMethod": "two-pass-hybrid",
                    "documentsExtracted": len(sorted_docs),
                    "timeMetrics": {
                        "aiProcessingSeconds": round(processing_time_seconds, 1),
                        "aiProcessingMinutes": round(processing_time_seconds / 60, 1),
                        "manualEstimateMinutes": round(manual_time_minutes, 1),
                        "timeSavedMinutes": round(time_saved_minutes, 1),
                        "timeSavedPercent": round(time_saved_percent, 1),
                        "hourlyRate": hourly_rate,
                        "manualCost": round(manual_cost, 2),
                        "aiCost": round(ai_cost, 2),
                        "costSaved": round(cost_saved, 2)
                    }
                },
                "documents": sorted_docs
            }
            
            # Save
            with open('final_result.json', 'w') as f:
                json.dump(final_result, f, indent=2)
            
            print(f"\n✓ Final result saved")
            print(f"✓ Total documents: {len(sorted_docs)}")
            print(f"\n⏱️  Time Savings:")
            print(f"  AI Processing: {round(processing_time_seconds / 60, 1)} minutes")
            print(f"  Manual Estimate: {round(manual_time_minutes, 1)} minutes")
            print(f"  Time Saved: {round(time_saved_minutes, 1)} minutes ({round(time_saved_percent, 1)}%)")
            print(f"  Cost Saved: ${round(cost_saved, 2)} (at ${hourly_rate}/hour)")
            
            return final_result
            
        except Exception as e:
            self.uploader.delete_file(file_info['name'])
            raise e
    
    def _get_inventory(self, file_info: Dict, page_count: int) -> List[Dict]:
        """
        Pass 1: Get inventory of all documents with page locations
        """
        prompt = f"""Scan this {page_count}-page title document and create an inventory of ALL documents.

For EACH document, identify:
1. Document type (Deed, Mortgage, Satisfaction, Judgment, UCC, etc.)
2. Parties: from (grantor/mortgagor) and to (grantee/mortgagee)
3. Record date
4. Page numbers where this document starts and ends

Be thorough - list EVERY document in the file.

Output ONLY this JSON structure:
{{
  "inventory": [
    {{
      "id": 1,
      "type": "Deed",
      "from": ["Party Name"],
      "to": ["Party Name"],
      "recordDate": "Month DD, YYYY",
      "pages": {{"start": 5, "end": 7}}
    }}
  ]
}}

Do not include explanatory text. Output ONLY valid JSON."""

        try:
            response_text = self.gemini.process_file(file_info['uri'], prompt, timeout=300)
            
            with open('inventory_response.txt', 'w') as f:
                f.write(response_text)
            
            result = self._extract_json(response_text)
            
            return result.get('inventory', [])
            
        except Exception as e:
            raise Exception(f"Inventory extraction failed: {e}")
    
    def _extract_document_detail(self, file_info: Dict, doc_info: Dict, doc_num: int) -> Dict:
        """
        Pass 2: Extract full details for a specific document
        Uses document-type-specific prompts for focused extraction
        """
        doc_type = doc_info.get('type', 'Document')
        page_start = doc_info.get('pages', {}).get('start', '?')
        page_end = doc_info.get('pages', {}).get('end', '?')
        
        # Get document-type-specific prompt
        prompt_key = self.doc_type_mapping.get(doc_type.lower(), "deed")
        base_instructions = get_combined_prompt([prompt_key])
        
        prompt = f"""{base_instructions}

CRITICAL: Extract ONLY document #{doc_num} from this file.

This is a {doc_type} that appears on pages {page_start}-{page_end}.
IGNORE all other documents in the file.

Extract complete details for this ONE document:
- Full legal description (verbatim)
- All clauses (verbatim): "being same premises", "subject to", "together with", "excepting and reserving"
- Complete party information with all names
- All dates (instrument, acknowledged, recorded)
- Recording information (location/instrument number, county)
- Monetary amounts (consideration, mortgage amount, transfer taxes)
- Property details (tax parcel, municipality)

IMPORTANT: Output valid JSON only. Ensure all strings are properly escaped and all braces/brackets are balanced.
Output a single document object matching the schema. Do not wrap in array.
"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response_text = self.gemini.process_file(file_info['uri'], prompt, timeout=300)
                
                with open(f'document_{doc_num}_response.txt', 'w') as f:
                    f.write(response_text)
                
                result = self._extract_json(response_text)
                
                # Handle both formats: single doc or wrapped in documents array
                if 'documents' in result and result['documents']:
                    return result['documents'][0]
                elif 'documentType' in result:
                    return result
                else:
                    raise ValueError("No document found in response")
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"retry (attempt {attempt + 2}/{max_retries})...", end=" ")
                    time.sleep(5)
                else:
                    # On final failure, return a minimal valid document
                    print(f"⚠️ Failed after {max_retries} attempts, returning minimal document")
                    return {
                        "documentType": doc_type,
                        "category": doc_type,
                        "parties": {
                            "fromLabel": "Unknown",
                            "toLabel": "Unknown",
                            "from": ["Error extracting"],
                            "to": ["Error extracting"]
                        },
                        "dates": {
                            "recordDate": "Error extracting"
                        },
                        "recording": {
                            "locationInstrumentNumber": f"Pages {page_start}-{page_end}",
                            "county": "Error"
                        },
                        "property": {
                            "legalDescription": f"EXTRACTION FAILED: {str(e)}"
                        },
                        "quality": {
                            "confidence": 0,
                            "flags": ["extraction_failed"],
                            "comments": f"Failed to extract after {max_retries} attempts: {str(e)}"
                        }
                    }
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from response text with robust error recovery"""
        text = text.strip()
        
        # Remove markdown code blocks
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.IGNORECASE)
            text = re.sub(r'\s*```\s*$', '', text)
        
        # Find JSON object
        start = text.find('{')
        end = text.rfind('}')
        
        if start == -1 or end == -1:
            raise ValueError("No JSON found in response")
        
        json_str = text[start:end+1]
        
        # Try parsing as-is
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Attempt 1: Fix common issues
            fixed = json_str
            fixed = re.sub(r',\s*}', '}', fixed)  # Remove trailing commas before }
            fixed = re.sub(r',\s*]', ']', fixed)  # Remove trailing commas before ]
            fixed = re.sub(r'}\s*{', '},{', fixed)  # Add comma between objects
            
            try:
                return json.loads(fixed)
            except:
                pass
            
            # Attempt 2: Find the last valid closing brace before the error
            error_pos = e.pos if hasattr(e, 'pos') else len(json_str)
            
            # Try progressively smaller chunks
            for attempt_end in range(error_pos, start, -100):
                # Find the last complete closing brace
                test_str = json_str[:attempt_end]
                brace_count = test_str.count('{') - test_str.count('}')
                
                if brace_count > 0:
                    test_str += '}' * brace_count
                
                try:
                    result = json.loads(test_str)
                    # Log that we recovered partial data
                    print(f"⚠️ Recovered partial JSON (truncated at ~{attempt_end} chars)")
                    return result
                except:
                    continue
            
            # Attempt 3: Save the problematic JSON for debugging
            with open('json_parse_error.txt', 'w') as f:
                f.write(f"Parse error: {e}\n\n")
                f.write(f"Error position: {e.pos if hasattr(e, 'pos') else 'unknown'}\n\n")
                f.write(f"JSON string (first 5000 chars):\n{json_str[:5000]}\n\n")
                f.write(f"JSON string (around error):\n{json_str[max(0, error_pos-500):error_pos+500]}")
            
            raise ValueError(f"Invalid JSON: {e}. Debug info saved to json_parse_error.txt")
