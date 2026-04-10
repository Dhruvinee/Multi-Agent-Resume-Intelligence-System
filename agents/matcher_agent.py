import os
import json
import re
from typing import Dict, List, Tuple
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

# Try to import embedding libraries
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None
    np = None
    cosine_similarity = None
    print("Note: sentence-transformers not available for matcher. Using basic matching.")

class SemanticMatcher:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )
        
        # Initialize embedding model if available
        self.embedding_model = None
        self.embeddings_available = EMBEDDINGS_AVAILABLE
        
        if self.embeddings_available and SentenceTransformer is not None:
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("✓ Embedding model loaded for matcher")
            except Exception as e:
                print(f"Note: Could not load embedding model: {e}")
                self.embeddings_available = False
        
        # Weight configuration
        self.weights = {
            "required_skills": 0.40,
            "nice_to_have_skills": 0.15,
            "experience": 0.25,
            "education": 0.10,
            "semantic_fit": 0.10
        }
    
    def extract_job_requirements(self, job_description: str) -> dict:
        """Extract structured requirements from job description"""
        # Truncate if too long
        if len(job_description) > 3000:
            job_description = job_description[:3000]
            
        prompt = f"""
Analyze this job description and extract requirements:

Job Description:
{job_description}

Return ONLY valid JSON with this exact structure:
{{
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill3", "skill4"],
  "min_experience_years": 0,
  "education_level": "Bachelor's",
  "responsibilities": ["resp1", "resp2"]
}}

Return ONLY valid JSON, no other text.
"""
        try:
            response = self.llm.invoke(prompt)
            text = response.content.strip()
            
            # Clean markdown
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            # Try to find JSON
            if not text.startswith("{"):
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    text = json_match.group()
            
            return json.loads(text)
        except Exception as e:
            print(f"Error extracting job requirements: {e}")
            return {
                "required_skills": [],
                "nice_to_have_skills": [],
                "min_experience_years": 0,
                "education_level": "",
                "responsibilities": []
            }
    
    def compute_skill_similarity_basic(self, candidate_skills: List[str], required_skills: List[str]) -> Tuple[float, List[str], List[str]]:
        """Basic skill matching (case-insensitive)"""
        if not candidate_skills or not required_skills:
            return 0.0, [], required_skills.copy()
        
        candidate_lower = [s.lower() for s in candidate_skills]
        matched = []
        missing = []
        
        for req_skill in required_skills:
            req_lower = req_skill.lower()
            found = False
            for cand_skill in candidate_lower:
                if req_lower in cand_skill or cand_skill in req_lower:
                    matched.append(req_skill)
                    found = True
                    break
            if not found:
                missing.append(req_skill)
        
        match_score = len(matched) / len(required_skills) if required_skills else 0
        return match_score, matched, missing
    
    def compute_skill_similarity_advanced(self, candidate_skills: List[str], required_skills: List[str]) -> Tuple[float, List[str], List[str]]:
        """Advanced skill matching using embeddings"""
        if not candidate_skills or not required_skills or not self.embeddings_available or self.embedding_model is None:
            return self.compute_skill_similarity_basic(candidate_skills, required_skills)
        
        try:
            # Get embeddings
            candidate_embeddings = self.embedding_model.encode(candidate_skills)
            required_embeddings = self.embedding_model.encode(required_skills)
            
            # Compute similarity matrix
            similarity_matrix = cosine_similarity(candidate_embeddings, required_embeddings)
            
            matched = []
            missing = []
            
            # For each required skill, find best match
            for i, req_skill in enumerate(required_skills):
                best_match_idx = np.argmax(similarity_matrix[:, i])
                best_score = similarity_matrix[best_match_idx, i]
                
                if best_score > 0.5:  # Threshold for match
                    matched.append(req_skill)
                else:
                    missing.append(req_skill)
            
            match_score = len(matched) / len(required_skills) if required_skills else 0
            return match_score, matched, missing
        except Exception as e:
            print(f"Error in advanced matching: {e}")
            return self.compute_skill_similarity_basic(candidate_skills, required_skills)
    
    def compute_experience_match(self, candidate_years: int, required_years: int) -> float:
        """Compute experience match score"""
        if required_years == 0:
            return 1.0
        if candidate_years >= required_years:
            return 1.0
        return candidate_years / required_years
    
    def match_candidate_to_job(self, candidate_profile: dict, job_description: str) -> dict:
        """Enhanced semantic matching"""
        
        # Extract job requirements
        job_req = self.extract_job_requirements(job_description)
        
        # Get candidate skills
        normalized_skills = candidate_profile.get("normalized_skills", {})
        if normalized_skills and "normalized_skills" in normalized_skills:
            candidate_skills = [s["canonical"] for s in normalized_skills["normalized_skills"]]
        else:
            candidate_skills = candidate_profile.get("skills", [])
        
        # Compute skill matches
        required_score, matched_skills, missing_skills = self.compute_skill_similarity_advanced(
            candidate_skills, job_req.get("required_skills", [])
        )
        nice_to_have_score, matched_nice, missing_nice = self.compute_skill_similarity_advanced(
            candidate_skills, job_req.get("nice_to_have_skills", [])
        )
        
        # Experience match
        candidate_exp = candidate_profile.get("years_of_experience", 0)
        exp_score = self.compute_experience_match(candidate_exp, job_req.get("min_experience_years", 0))
        
        # Final weighted score
        final_score = (
            required_score * self.weights["required_skills"] +
            nice_to_have_score * self.weights["nice_to_have_skills"] +
            exp_score * self.weights["experience"]
        ) * 100
        
        # Get LLM-based analysis
        llm_analysis = self._get_llm_analysis(candidate_profile, job_description, final_score)
        
        # Determine verdict
        if final_score >= 80:
            verdict = "Strong Match - Highly recommended"
        elif final_score >= 65:
            verdict = "Good Match - Consider for interview"
        elif final_score >= 50:
            verdict = "Potential Match - Further review needed"
        elif final_score >= 35:
            verdict = "Weak Match - Consider for different role"
        else:
            verdict = "Not a Match - Does not meet requirements"
        
        return {
            "match_score": round(final_score, 2),
            "verdict": verdict,
            "matched_skills": matched_skills[:15] if matched_skills else [],
            "missing_skills": missing_skills[:10] if missing_skills else [],
            "nice_to_have_matched": matched_nice[:10] if matched_nice else [],
            "experience_match": f"{candidate_exp} years vs {job_req.get('min_experience_years', 0)} years required",
            "gap_analysis": llm_analysis.get("gap_analysis", "Review required skills and experience"),
            "recommendation": llm_analysis.get("recommendation", "Schedule technical interview"),
            "upskilling_suggestions": llm_analysis.get("upskilling_suggestions", []),
            "skill_match_details": {
                "required_skills_match": round(required_score * 100, 2),
                "nice_to_have_match": round(nice_to_have_score * 100, 2),
                "experience_match": round(exp_score * 100, 2)
            }
        }
    
    def _get_llm_analysis(self, candidate: dict, job_desc: str, score: float) -> dict:
        """Get detailed analysis from LLM"""
        # Get candidate skills safely
        normalized = candidate.get("normalized_skills", {})
        if normalized and "normalized_skills" in normalized:
            skills = [s["canonical"] for s in normalized["normalized_skills"][:10]]
        else:
            skills = candidate.get("skills", [])[:10]
        
        # Truncate job description
        if len(job_desc) > 500:
            job_desc = job_desc[:500]
        
        prompt = f"""
Analyze this candidate match:

Candidate: {candidate.get('name', 'Unknown')}
Experience: {candidate.get('years_of_experience', 0)} years
Top Skills: {', '.join(skills)}

Match Score: {score}/100

Job Description Summary: {job_desc}

Provide a brief analysis in JSON:
{{
  "gap_analysis": "What are the main gaps? (1 sentence)",
  "recommendation": "Should this candidate proceed? Why? (1 sentence)",
  "upskilling_suggestions": ["suggestion1", "suggestion2"]
}}

Return ONLY valid JSON.
"""
        try:
            response = self.llm.invoke(prompt)
            text = response.content.strip()
            
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            
            # Try to extract JSON
            if not text.startswith("{"):
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    text = json_match.group()
            
            return json.loads(text)
        except Exception as e:
            print(f"Error in LLM analysis: {e}")
            return {
                "gap_analysis": "Review candidate skills against job requirements",
                "recommendation": "Consider for interview based on available information",
                "upskilling_suggestions": ["Review job requirements carefully"]
            }

# Create instance
matcher_instance = SemanticMatcher()

# Export the function
def match_candidate_to_job(candidate_profile: dict, job_description: str) -> dict:
    """Public function to match candidate to job"""
    return matcher_instance.match_candidate_to_job(candidate_profile, job_description)