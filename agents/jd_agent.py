import os
import json
import re
from typing import List, Dict
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from agents.normalizer_agent import normalize_skills

load_dotenv()


class JobDescriptionAgent:
    """
    Admin-facing agent that:
    1. Accepts a job description (free text) + optional skill list from admin
    2. Uses Gemini to extract required/nice-to-have skills from the description
    3. Normalizes all skills through the existing normalizer_agent taxonomy
    4. Returns a structured job profile ready to be stored and matched against
    """

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0
        )

    def extract_skills_from_description(self, description: str) -> Dict:
        """
        Use Gemini to pull structured skill requirements out of raw JD text.
        Returns required_skills, nice_to_have_skills, min_experience_years,
        education_level, and a short role_summary.
        """
        if len(description) > 4000:
            description = description[:4000]

        prompt = f"""
You are a technical recruiter assistant. Read the job description below and extract structured information.

Job Description:
{description}

Return ONLY valid JSON with this exact structure:
{{
  "role_title": "inferred job title or empty string",
  "role_summary": "one sentence summary of the role",
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill3", "skill4"],
  "min_experience_years": 0,
  "education_level": "Bachelor's or empty string",
  "responsibilities": ["responsibility1", "responsibility2"]
}}

Rules:
- required_skills = skills explicitly marked as required/must-have
- nice_to_have_skills = skills marked as preferred/bonus/nice-to-have
- If no clear distinction, put all extracted skills in required_skills
- min_experience_years should be a number (0 if not mentioned)
- Return ONLY valid JSON, no markdown, no extra text
"""
        try:
            response = self.llm.invoke(prompt)
            text = response.content.strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()

            if not text.startswith("{"):
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    text = match.group()

            return json.loads(text)

        except Exception as e:
            print(f"JD Agent - extraction error: {e}")
            return {
                "role_title": "",
                "role_summary": "",
                "required_skills": [],
                "nice_to_have_skills": [],
                "min_experience_years": 0,
                "education_level": "",
                "responsibilities": []
            }

    def process_job(self, description: str, admin_skills: List[str] = None) -> Dict:
        """
        Full pipeline:
        - Extract skills from JD text via LLM
        - Merge with admin-provided skills (admin list takes priority)
        - Normalize all skills through the taxonomy
        - Return structured job profile

        Args:
            description: Raw job description text from admin
            admin_skills: Optional list of skills admin explicitly specified

        Returns:
            Structured job profile dict with normalized skills
        """
        # Step 1: Extract from description text
        extracted = self.extract_skills_from_description(description)

        # Step 2: Merge admin-provided skills with LLM-extracted ones
        # Admin-specified skills are added to required_skills (admin knows best)
        required = extracted.get("required_skills", [])
        nice_to_have = extracted.get("nice_to_have_skills", [])

        if admin_skills:
            for skill in admin_skills:
                skill = skill.strip()
                if skill and skill not in required:
                    required.append(skill)

        # Step 3: Normalize all skills through the existing normalizer
        all_skills = required + nice_to_have
        context = description[:500]  # Give context for proficiency inference

        normalized_result = normalize_skills(all_skills, context=context)
        normalized_list = normalized_result.get("normalized_skills", [])

        # Separate back into required vs nice-to-have using normalized names
        required_lower = [s.lower() for s in required]
        normalized_required = []
        normalized_nice = []

        for norm in normalized_list:
            if norm["original"].lower() in required_lower:
                normalized_required.append(norm)
            else:
                normalized_nice.append(norm)

        return {
            "role_title": extracted.get("role_title", ""),
            "role_summary": extracted.get("role_summary", ""),
            "description": description,
            "min_experience_years": extracted.get("min_experience_years", 0),
            "education_level": extracted.get("education_level", ""),
            "responsibilities": extracted.get("responsibilities", []),

            # Raw skill lists (for quick access in matcher)
            "required_skills": required,
            "nice_to_have_skills": nice_to_have,

            # Normalized skill objects (canonical names + categories + proficiency)
            "normalized_required_skills": normalized_required,
            "normalized_nice_to_have_skills": normalized_nice,
            "unknown_skills": normalized_result.get("unknown_skills", []),

            # Skill summary by category
            "skill_categories": normalized_result.get("skill_categories", {}),
        }


# Singleton
jd_agent_instance = JobDescriptionAgent()


def process_job_description(description: str, admin_skills: List[str] = None) -> Dict:
    """Public function used by routes.py"""
    return jd_agent_instance.process_job(description, admin_skills)
