import google.generativeai as genai
from typing import Dict

class GeminiClient:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
    def process_file(self, file_uri: str, prompt: str, timeout: int = 300) -> str:
        """
        Process uploaded file via Files API
        """
        try:
            file_name = file_uri.split('/')[-1]
            file = genai.get_file(name=file_name)
            
            response = self.model.generate_content(
                [
                    prompt,
                    file
                ],
                generation_config={
                    'temperature': 0,
                    'max_output_tokens': 65536,
                    'top_p': 0.95,
                    'top_k': 40
                }
            )
            
            # Check if response was truncated
            print(f"Response finish reason: {response.candidates[0].finish_reason}")
            print(f"Safety ratings: {response.candidates[0].safety_ratings}")
            
            return response.text
            
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def estimate_cost(self, num_pages: int) -> float:
        return num_pages * 0.015
