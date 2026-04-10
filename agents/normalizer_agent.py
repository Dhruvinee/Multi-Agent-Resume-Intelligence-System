import os
import json
import re
from typing import List, Dict, Optional
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Try to import sentence-transformers, but don't fail if not available
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
    print("Note: sentence-transformers not available. Using basic matching.")

class SkillNormalizer:
    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )
        
        # Initialize embeddings if available
        self.embedding_model = None
        self.embeddings_available = EMBEDDINGS_AVAILABLE
        
        if self.embeddings_available and SentenceTransformer is not None:
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                print("✓ Embedding model loaded successfully")
            except Exception as e:
                print(f"Note: Could not load embedding model: {e}")
                self.embeddings_available = False
        
        # Extended taxonomy
        self.taxonomy = {
            "Programming Languages": {
                "skills": ["Python", "JavaScript", "Java", "C++", "TypeScript", "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin"],
                "aliases": {"JS": "JavaScript", "py": "Python", "java": "Java", "cpp": "C++", "ts": "TypeScript"}
            },
            "Web Frameworks": {
                "skills": ["React", "Angular", "Vue.js", "Django", "FastAPI", "Node.js", "Flask", "Spring Boot"],
                "aliases": {"ReactJS": "React", "React.js": "React", "Vue": "Vue.js"}
            },
            "Cloud & DevOps": {
                "skills": ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Terraform", "Jenkins"],
                "aliases": {"K8s": "Kubernetes", "AWS Cloud": "AWS", "GCP Cloud": "GCP"}
            },
            "Data & ML": {
                "skills": ["Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Pandas", "SQL", "Data Analysis", "NumPy"],
                "aliases": {"ML": "Machine Learning", "DL": "Deep Learning", "TF": "TensorFlow"}
            },
            "Soft Skills": {
                "skills": ["Leadership", "Communication", "Problem Solving", "Teamwork", "Critical Thinking", "Adaptability"],
                "aliases": {}
            },
            "Databases": {
                "skills": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra"],
                "aliases": {"Postgres": "PostgreSQL", "Mongo": "MongoDB"}
            }
        }
    
    def infer_proficiency(self, skill: str, context: str) -> str:
        """Infer proficiency level from context"""
        context_lower = context.lower()
        
        # Extract years of experience
        years_match = re.search(r'(\d+)\s*year', context_lower)
        if years_match:
            years = int(years_match.group(1))
            if years >= 5:
                return "expert"
            elif years >= 2:
                return "intermediate"
            elif years >= 1:
                return "beginner"
        
        # Keyword matching
        keywords = {
            "expert": ["expert", "advanced", "proficient", "deep knowledge", "lead", "senior"],
            "intermediate": ["intermediate", "working knowledge", "experience", "professional"],
            "beginner": ["beginner", "learning", "familiar", "basic", "introductory"]
        }
        
        for level, words in keywords.items():
            if any(word in context_lower for word in words):
                return level
        
        return "intermediate"
    
    def normalize_skills(self, raw_skills: List[str], context: str = "") -> dict:
        """Enhanced skill normalization"""
        
        normalized = []
        unknown_skills = []
        
        for skill in raw_skills:
            skill_clean = skill.strip()
            skill_lower = skill_clean.lower()
            matched = False
            
            # Check aliases and direct matches
            for category, data in self.taxonomy.items():
                # Check aliases
                if skill_clean in data.get("aliases", {}):
                    canonical = data["aliases"][skill_clean]
                    normalized.append({
                        "original": skill_clean,
                        "canonical": canonical,
                        "category": category,
                        "proficiency": self.infer_proficiency(skill_clean, context)
                    })
                    matched = True
                    break
                
                # Check direct match (case-insensitive)
                for canonical_skill in data["skills"]:
                    if skill_lower == canonical_skill.lower():
                        normalized.append({
                            "original": skill_clean,
                            "canonical": canonical_skill,
                            "category": category,
                            "proficiency": self.infer_proficiency(skill_clean, context)
                        })
                        matched = True
                        break
                if matched:
                    break
            
            if not matched and self.embeddings_available and self.embedding_model:
                # Try semantic matching
                try:
                    skill_embedding = self.embedding_model.encode(skill_lower)
                    best_match = None
                    best_score = 0.5
                    best_category = None
                    
                    for category, data in self.taxonomy.items():
                        for canonical_skill in data["skills"]:
                            canonical_embedding = self.embedding_model.encode(canonical_skill.lower())
                            similarity = cosine_similarity([skill_embedding], [canonical_embedding])[0][0]
                            if similarity > best_score:
                                best_score = similarity
                                best_match = canonical_skill
                                best_category = category
                    
                    if best_match:
                        normalized.append({
                            "original": skill_clean,
                            "canonical": best_match,
                            "category": best_category,
                            "proficiency": self.infer_proficiency(skill_clean, context),
                            "similarity_score": float(best_score)
                        })
                        matched = True
                except:
                    pass
            
            if not matched:
                unknown_skills.append(skill_clean)
        
        # Infer higher-level skills
        inferred_skills = []
        all_canonical = [n["canonical"] for n in normalized]
        
        if "TensorFlow" in all_canonical and "PyTorch" in all_canonical:
            if "Deep Learning" not in all_canonical:
                inferred_skills.append("Deep Learning")
        
        if "React" in all_canonical and "Node.js" in all_canonical:
            if "Full Stack Development" not in all_canonical:
                inferred_skills.append("Full Stack Development")
        
        return {
            "normalized_skills": normalized,
            "inferred_skills": inferred_skills,
            "unknown_skills": unknown_skills,
            "skill_categories": self._get_category_summary(normalized)
        }
    
    def _get_category_summary(self, normalized: List[dict]) -> dict:
        """Get summary of skills by category"""
        summary = {}
        for skill in normalized:
            cat = skill["category"]
            if cat not in summary:
                summary[cat] = []
            if skill["canonical"] not in summary[cat]:
                summary[cat].append(skill["canonical"])
        return summary

# Create global instance
normalizer_instance = SkillNormalizer()

# Export the function
def normalize_skills(raw_skills: list, context: str = "") -> dict:
    """Public function to normalize skills"""
    return normalizer_instance.normalize_skills(raw_skills, context)

# Export taxonomy
TAXONOMY = normalizer_instance.taxonomy