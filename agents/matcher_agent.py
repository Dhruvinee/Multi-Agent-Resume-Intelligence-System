import os
import re
import json
import logging
from typing import Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

from langchain_groq import ChatGroq

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Optional dependencies
# ─────────────────────────────────────────────

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not available. Falling back to basic matching.")

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
SEMANTIC_THRESHOLD = 0.5
JOB_DESC_MAX_CHARS = 3000
JOB_DESC_ANALYSIS_CHARS = 500
MAX_SKILLS_IN_PROMPT = 10
MAX_MATCHED_SKILLS = 15
MAX_MISSING_SKILLS = 10

WEIGHTS = {
    "required_skills":    0.40,
    "nice_to_have_skills": 0.15,
    "experience":         0.25,
    "education":          0.10,
    "semantic_fit":       0.10,
}

VERDICTS = [
    (80, "Strong Match — Highly recommended"),
    (65, "Good Match — Consider for interview"),
    (50, "Potential Match — Further review needed"),
    (35, "Weak Match — Consider for different role"),
    (0,  "Not a Match — Does not meet requirements"),
]

JOB_REQUIREMENTS_PROMPT = """
Analyze this job description and extract requirements.

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

LLM_ANALYSIS_PROMPT = """
Analyze this candidate-job match and return ONLY valid JSON.

Candidate: {name}
Experience: {years} years
Top Skills: {skills}
Match Score: {score}/100
Job Description Summary: {job_desc}

JSON structure:
{{
  "gap_analysis": "Main gaps in one sentence",
  "recommendation": "Should this candidate proceed and why, in one sentence",
  "upskilling_suggestions": ["suggestion1", "suggestion2"]
}}
"""

# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class SkillMatchResult:
    score: float
    matched: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    match_score: float
    verdict: str
    matched_skills: list[str]
    missing_skills: list[str]
    nice_to_have_matched: list[str]
    experience_match: str
    gap_analysis: str
    recommendation: str
    upskilling_suggestions: list[str]
    skill_match_details: dict

    def to_dict(self) -> dict:
        return {
            "match_score": round(self.match_score, 2),
            "verdict": self.verdict,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "nice_to_have_matched": self.nice_to_have_matched,
            "experience_match": self.experience_match,
            "gap_analysis": self.gap_analysis,
            "recommendation": self.recommendation,
            "upskilling_suggestions": self.upskilling_suggestions,
            "skill_match_details": self.skill_match_details,
        }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _clean_llm_json(raw: str) -> str:
    """Strip markdown fences and extract JSON object."""
    text = re.sub(r"^```[a-zA-Z]*\n?", "", raw.strip())
    text = re.sub(r"\n?```$", "", text).strip()
    if not text.startswith("{"):
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group()
    return text


def _verdict(score: float) -> str:
    for threshold, label in VERDICTS:
        if score >= threshold:
            return label
    return VERDICTS[-1][1]


def _get_candidate_skills(profile: dict) -> list[str]:
    normalized = profile.get("normalized_skills", {})
    if isinstance(normalized, dict) and "normalized_skills" in normalized:
        return [s["canonical"] for s in normalized["normalized_skills"]]
    return profile.get("skills", [])


# ─────────────────────────────────────────────
# SemanticMatcher
# ─────────────────────────────────────────────

class SemanticMatcher:
    def __init__(self, model: str = "llama-3.3-70b-versatile"):
        self.llm = ChatGroq(
            model=model,
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=0,
        )

        self.embedding_model = None
        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
                logger.info("Embedding model loaded for matcher")
            except Exception as e:
                logger.warning(f"Could not load embedding model: {e}")

    # ── LLM calls ────────────────────────────

    def extract_job_requirements(self, job_description: str) -> dict:
        truncated = job_description[:JOB_DESC_MAX_CHARS]
        prompt = JOB_REQUIREMENTS_PROMPT.format(job_description=truncated)
        try:
            response = self.llm.invoke(prompt)
            return json.loads(_clean_llm_json(response.content))
        except Exception as e:
            logger.error(f"Failed to extract job requirements: {e}")
            return {
                "required_skills": [],
                "nice_to_have_skills": [],
                "min_experience_years": 0,
                "education_level": "",
                "responsibilities": [],
            }

    def _get_llm_analysis(self, candidate: dict, job_desc: str, score: float) -> dict:
        skills = _get_candidate_skills(candidate)[:MAX_SKILLS_IN_PROMPT]
        prompt = LLM_ANALYSIS_PROMPT.format(
            name=candidate.get("name", "Unknown"),
            years=candidate.get("years_of_experience", 0),
            skills=", ".join(skills),
            score=round(score, 1),
            job_desc=job_desc[:JOB_DESC_ANALYSIS_CHARS],
        )
        try:
            response = self.llm.invoke(prompt)
            return json.loads(_clean_llm_json(response.content))
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return {
                "gap_analysis": "Review candidate skills against job requirements",
                "recommendation": "Consider for interview based on available information",
                "upskilling_suggestions": ["Review job requirements carefully"],
            }

    # ── Skill matching ────────────────────────

    def _match_basic(self, candidate: list[str], required: list[str]) -> SkillMatchResult:
        if not candidate or not required:
            return SkillMatchResult(score=0.0, missing=list(required))

        candidate_lower = [s.lower() for s in candidate]
        matched, missing = [], []

        for req in required:
            req_l = req.lower()
            if any(req_l in c or c in req_l for c in candidate_lower):
                matched.append(req)
            else:
                missing.append(req)

        return SkillMatchResult(
            score=len(matched) / len(required),
            matched=matched,
            missing=missing,
        )

    def _match_semantic(self, candidate: list[str], required: list[str]) -> SkillMatchResult:
        if not self.embedding_model or not candidate or not required:
            return self._match_basic(candidate, required)
        try:
            cand_vecs = self.embedding_model.encode(candidate)
            req_vecs  = self.embedding_model.encode(required)
            sim_matrix = cosine_similarity(cand_vecs, req_vecs)

            matched, missing = [], []
            for i, req in enumerate(required):
                if sim_matrix[:, i].max() > SEMANTIC_THRESHOLD:
                    matched.append(req)
                else:
                    missing.append(req)

            return SkillMatchResult(
                score=len(matched) / len(required),
                matched=matched,
                missing=missing,
            )
        except Exception as e:
            logger.warning(f"Semantic matching failed, using basic: {e}")
            return self._match_basic(candidate, required)

    # ── Experience ────────────────────────────

    @staticmethod
    def _experience_score(candidate_years: int, required_years: int) -> float:
        if required_years == 0:
            return 1.0
        return min(candidate_years / required_years, 1.0)

    # ── Main entry ────────────────────────────

    def match_candidate_to_job(self, candidate_profile: dict, job_description: str) -> dict:
        job_req = self.extract_job_requirements(job_description)
        candidate_skills = _get_candidate_skills(candidate_profile)

        required_match    = self._match_semantic(candidate_skills, job_req.get("required_skills", []))
        nice_match        = self._match_semantic(candidate_skills, job_req.get("nice_to_have_skills", []))
        candidate_exp     = candidate_profile.get("years_of_experience", 0)
        exp_score         = self._experience_score(candidate_exp, job_req.get("min_experience_years", 0))

        final_score = (
            required_match.score * WEIGHTS["required_skills"] +
            nice_match.score     * WEIGHTS["nice_to_have_skills"] +
            exp_score            * WEIGHTS["experience"]
        ) * 100

        llm_analysis = self._get_llm_analysis(candidate_profile, job_description, final_score)

        return MatchResult(
            match_score=final_score,
            verdict=_verdict(final_score),
            matched_skills=required_match.matched[:MAX_MATCHED_SKILLS],
            missing_skills=required_match.missing[:MAX_MISSING_SKILLS],
            nice_to_have_matched=nice_match.matched[:MAX_MISSING_SKILLS],
            experience_match=f"{candidate_exp} years vs {job_req.get('min_experience_years', 0)} required",
            gap_analysis=llm_analysis.get("gap_analysis", ""),
            recommendation=llm_analysis.get("recommendation", ""),
            upskilling_suggestions=llm_analysis.get("upskilling_suggestions", []),
            skill_match_details={
                "required_skills_match":  round(required_match.score * 100, 2),
                "nice_to_have_match":     round(nice_match.score * 100, 2),
                "experience_match":       round(exp_score * 100, 2),
            },
        ).to_dict()


# ─────────────────────────────────────────────
# Module-level convenience
# ─────────────────────────────────────────────

_matcher_instance: Optional[SemanticMatcher] = None

def match_candidate_to_job(candidate_profile: dict, job_description: str) -> dict:
    global _matcher_instance
    if _matcher_instance is None:
        _matcher_instance = SemanticMatcher()
    return _matcher_instance.match_candidate_to_job(candidate_profile, job_description)