from pdf2image import convert_from_path
from PIL import Image
from typing import List

class PDFProcessor:
    def __init__(self):
        self.dpi = 300
        
    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        try:
            return convert_from_path(pdf_path, dpi=self.dpi, fmt='png')
        except Exception as e:
            raise Exception(f"PDF conversion error: {str(e)}")
