import os
import json
import re
from typing import Optional, List, Dict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import pdfplumber
import docx

# Fix for PyMuPDF - use correct import
try:
    import fitz  # PyMuPDF
except ImportError:
    # If fitz doesn't work, try importing as pymupdf
    import pymupdf as fitz

load_dotenv()

class ResumeParser:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0,
            convert_system_message_to_human=True
        )
    
    def extract_text_with_layout(self, file_path: str) -> dict:
        """Extract text with layout analysis for better parsing"""
        result = {"text": "", "layout_info": {}}
        
        if file_path.endswith(".pdf"):
            try:
                # Try PyMuPDF first for better layout detection
                doc = fitz.open(file_path)
                text_by_page = []
                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    text_by_page.append(text)
                    
                    # Detect if multi-column
                    try:
                        blocks = page.get_text("dict")
                        if blocks and "blocks" in blocks:
                            left_col = []
                            right_col = []
                            for block in blocks["blocks"]:
                                if "lines" in block:
                                    for line in block["lines"]:
                                        if "spans" in line:
                                            for span in line["spans"]:
                                                if "bbox" in span and span["bbox"][0] < page.rect.width / 2:
                                                    left_col.append(span["text"])
                                                else:
                                                    right_col.append(span["text"])
                            if left_col and right_col:
                                result["layout_info"][page_num] = "multi-column"
                    except:
                        pass  # Skip layout detection if it fails
                
                result["text"] = "\n".join(text_by_page)
                doc.close()
            except:
                # Fallback to pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text = page.extract_text() or ""
                        result["text"] += text
                result["layout_info"]["type"] = "pdf-fallback"
                
        elif file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            result["text"] = "\n".join([para.text for para in doc.paragraphs])
            result["layout_info"]["type"] = "docx"
        else:
            # Plain text
            with open(file_path, "r", encoding='utf-8', errors='ignore') as f:
                result["text"] = f.read()
            result["layout_info"]["type"] = "text"
            
        return result
    
    def parse_resume(self, file_path: str) -> dict:
        """Enhanced resume parsing with better error handling"""
        try:
            extracted = self.extract_text_with_layout(file_path)
            raw_text = extracted["text"]
            
            if not raw_text.strip():
                raise ValueError("No text could be extracted from the resume")
            
            # Truncate if too long (Gemini has token limits)
            if len(raw_text) > 10000:
                raw_text = raw_text[:10000] + "... (truncated)"
            
            prompt = f"""
Parse this resume and return ONLY valid JSON. Handle ambiguous formatting intelligently.

Resume text:
{raw_text}

Required JSON structure:
{{
  "name": "Full name or empty string",
  "email": "email@example.com or empty",
  "phone": "+1234567890 or empty",
  "location": "City, Country or empty",
  "linkedin": "linkedin url or empty",
  "github": "github url or empty",
  "skills": ["skill1", "skill2"],
  "experience": [
    {{"company": "Company Name", "role": "Job Title", "duration": "MM/YYYY - MM/YYYY", "responsibilities": ["responsibility1"]}}
  ],
  "education": [
    {{"institution": "University", "degree": "B.Sc.", "field": "Computer Science", "year": "2020"}}
  ],
  "certifications": ["Certification Name"],
  "projects": [
    {{"name": "Project Name", "description": "Brief description", "technologies": ["tech1"]}}
  ],
  "publications": ["Publication title"],
  "summary": "Brief professional summary",
  "years_of_experience": 0
}}

Rules:
- Extract ALL information you can find
- For missing fields, use empty strings/arrays
- Infer years of experience from work history
- Return ONLY valid JSON, no markdown
- Do not include any explanatory text outside the JSON
"""

            response = self.llm.invoke(prompt)
            text = response.content.strip()
            
            # Clean markdown
            if text.startswith("```"):
                lines = text.split("\n")
                # Remove first and last line if they contain backticks
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines)
                # Remove any "json" label
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            # Try to find JSON in the text if it's not pure JSON
            if not text.startswith("{"):
                import re
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    text = json_match.group()
            
            parsed_data = json.loads(text)
            
            # Ensure required fields exist
            required_fields = ["name", "email", "phone", "skills", "experience", "education"]
            for field in required_fields:
                if field not in parsed_data:
                    if field in ["skills", "experience", "education"]:
                        parsed_data[field] = []
                    else:
                        parsed_data[field] = ""
            
            parsed_data["_metadata"] = {
                "layout_type": extracted["layout_info"],
                "raw_text_length": len(raw_text)
            }
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            return {
                "error": f"JSON parsing failed: {str(e)}",
                "raw_output": text if 'text' in locals() else "No output",
                "name": "",
                "email": "",
                "skills": [],
                "experience": [],
                "education": []
            }
        except Exception as e:
            return {
                "error": str(e),
                "name": "",
                "email": "",
                "skills": [],
                "experience": [],
                "education": []
            }

# Singleton instance
parser_instance = ResumeParser()

def parse_resume(file_path: str) -> dict:
    return parser_instance.parse_resume(file_path)