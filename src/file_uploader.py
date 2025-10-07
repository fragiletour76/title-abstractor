import google.generativeai as genai
from typing import Optional
import time

class FileUploader:
    """
    Handles uploading PDFs to Gemini Files API
    Files persist for 48 hours
    """
    
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
    
    def upload_pdf(self, pdf_path: str, display_name: str) -> dict:
        """
        Upload PDF to Files API
        Returns: {"uri": "...", "name": "...", "state": "ACTIVE"}
        """
        print(f"Uploading {display_name} to Gemini Files API...")
        
        try:
            # Correct method for version 0.8.5: upload_file (not files.upload)
            file = genai.upload_file(
                path=pdf_path,
                display_name=display_name
            )
            
            print(f"✓ Uploaded: {file.name}")
            print(f"  URI: {file.uri}")
            print(f"  State: {file.state.name}")
            
            # Wait for file to be processed (if needed)
            while file.state.name == "PROCESSING":
                print("  Processing file...")
                time.sleep(2)
                file = genai.get_file(file.name)
            
            if file.state.name == "FAILED":
                raise Exception(f"File upload failed")
            
            print(f"✓ File ready for processing")
            
            return {
                "uri": file.uri,
                "name": file.name,
                "state": file.state.name,
                "display_name": display_name
            }
            
        except Exception as e:
            raise Exception(f"Upload error: {str(e)}")
    
    def delete_file(self, file_name: str):
        """
        Clean up uploaded file (optional - files auto-delete after 48hrs)
        """
        try:
            genai.delete_file(file_name)
            print(f"✓ Deleted file: {file_name}")
        except Exception as e:
            print(f"⚠️ Could not delete file: {e}")
