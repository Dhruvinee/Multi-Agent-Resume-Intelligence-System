import os
import json
import re
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
# Taxonomy
# ─────────────────────────────────────────────

TAXONOMY: dict[str, dict] = {
    "Programming Languages": {
        "skills": ["Python", "JavaScript", "Java", "C++", "TypeScript", "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin"],
        "aliases": {"JS": "JavaScript", "py": "Python", "cpp": "C++", "ts": "TypeScript"},
    },
    "Web Frameworks": {
        "skills": ["React", "Angular", "Vue.js", "Django", "FastAPI", "Node.js", "Flask", "Spring Boot"],
        "aliases": {"ReactJS": "React", "React.js": "React", "Vue": "Vue.js"},
    },
    "Cloud & DevOps": {
        "skills": ["AWS", "Azure", "GCP", "Docker", "Kubernetes", "CI/CD", "Terraform", "Jenkins"],
        "aliases": {"K8s": "Kubernetes", "AWS Cloud": "AWS", "GCP Cloud": "GCP"},
    },
    "Data & ML": {
        "skills": ["Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Pandas", "SQL", "Data Analysis", "NumPy"],
        "aliases": {"ML": "Machine Learning", "DL": "Deep Learning", "TF": "TensorFlow"},
    },
    "Soft Skills": {
        "skills": ["Leadership", "Communication", "Problem Solving", "Teamwork", "Critical Thinking", "Adaptability"],
        "aliases": {},
    },
    "Databases": {
        "skills": ["PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch", "Cassandra"],
        "aliases": {"Postgres": "PostgreSQL", "Mongo": "MongoDB"},
    },
}

# Inference rules: if all trigger skills are present, infer the target skill
INFERENCE_RULES: list[dict] = [
    {"triggers": ["TensorFlow", "PyTorch"],      "infer": "Deep Learning"},
    {"triggers": ["React", "Node.js"],           "infer": "Full Stack Development"},
    {"triggers": ["Docker", "Kubernetes"],       "infer": "Container Orchestration"},
    {"triggers": ["AWS", "Terraform"],           "infer": "Cloud Infrastructure"},
]

PROFICIENCY_KEYWORDS: dict[str, list[str]] = {
    "expert":       ["expert", "advanced", "proficient", "deep knowledge", "lead", "senior"],
    "intermediate": ["intermediate", "working knowledge", "experience", "professional"],
    "beginner":     ["beginner", "learning", "familiar", "basic", "introductory"],
}

SEMANTIC_SIMILARITY_THRESHOLD = 0.5
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class NormalizedSkill:
    original: str
    canonical: str
    category: str
    proficiency: str
    similarity_score: Optional[float] = None

    def to_dict(self) -> dict:
        d = {
            "original": self.original,
            "canonical": self.canonical,
            "category": self.category,
            "proficiency": self.proficiency,
        }
        if self.similarity_score is not None:
            d["similarity_score"] = round(self.similarity_score, 4)
        return d


@dataclass
class NormalizationResult:
    normalized_skills: list[NormalizedSkill] = field(default_factory=list)
    inferred_skills: list[str] = field(default_factory=list)
    unknown_skills: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "normalized_skills": [s.to_dict() for s in self.normalized_skills],
            "inferred_skills": self.inferred_skills,
            "unknown_skills": self.unknown_skills,
            "skill_categories": self._category_summary(),
        }

    def _category_summary(self) -> dict[str, list[str]]:
        summary: dict[str, list[str]] = {}
        for skill in self.normalized_skills:
            summary.setdefault(skill.category, [])
            if skill.canonical not in summary[skill.category]:
                summary[skill.category].append(skill.canonical)
        return summary


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def infer_proficiency(skill: str, context: str) -> str:
    """Infer proficiency from context text."""
    context_lower = context.lower()

    years_match = re.search(r"(\d+)\s*year", context_lower)
    if years_match:
        years = int(years_match.group(1))
        if years >= 5:   return "expert"
        if years >= 2:   return "intermediate"
        if years >= 1:   return "beginner"

    for level, keywords in PROFICIENCY_KEYWORDS.items():
        if any(kw in context_lower for kw in keywords):
            return level

    return "intermediate"


def _build_alias_lookup() -> dict[str, tuple[str, str]]:
    """Flat lookup: alias/skill_lower -> (canonical, category)"""
    lookup: dict[str, tuple[str, str]] = {}
    for category, data in TAXONOMY.items():
        for alias, canonical in data["aliases"].items():
            lookup[alias] = (canonical, category)
        for skill in data["skills"]:
            lookup[skill.lower()] = (skill, category)
    return lookup


ALIAS_LOOKUP = _build_alias_lookup()


def _apply_inference_rules(canonical_skills: set[str]) -> list[str]:
    """Return inferred skills not already in the canonical set."""
    inferred = []
    for rule in INFERENCE_RULES:
        if all(t in canonical_skills for t in rule["triggers"]):
            if rule["infer"] not in canonical_skills:
                inferred.append(rule["infer"])
    return inferred


# ─────────────────────────────────────────────
# SkillNormalizer
# ─────────────────────────────────────────────

class SkillNormalizer:
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
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.warning(f"Could not load embedding model: {e}")

        # Pre-compute canonical embeddings once for performance
        self._canonical_embeddings: Optional[dict] = None
        if self.embedding_model:
            self._canonical_embeddings = self._precompute_canonical_embeddings()
            logger.info(f"Pre-computed embeddings for {len(self._canonical_embeddings)} canonical skills")

    def _precompute_canonical_embeddings(self) -> dict[str, tuple]:
        """Pre-encode all canonical skills once to avoid repeated computation."""
        embeddings = {}
        for category, data in TAXONOMY.items():
            for skill in data["skills"]:
                embeddings[skill] = (
                    self.embedding_model.encode(skill.lower()),
                    category,
                )
        return embeddings

    def _semantic_match(self, skill: str) -> Optional[tuple[str, str, float]]:
        """Return (canonical, category, score) for best semantic match, or None."""
        if not self.embedding_model or not self._canonical_embeddings:
            return None
        try:
            skill_vec = self.embedding_model.encode(skill.lower())
            best_skill, best_cat, best_score = None, None, SEMANTIC_SIMILARITY_THRESHOLD

            for canonical, (vec, category) in self._canonical_embeddings.items():
                score = cosine_similarity([skill_vec], [vec])[0][0]
                if score > best_score:
                    best_score = score
                    best_skill = canonical
                    best_cat = category

            return (best_skill, best_cat, float(best_score)) if best_skill else None
        except Exception as e:
            logger.debug(f"Semantic match failed for '{skill}': {e}")
            return None

    def normalize_skills(self, raw_skills: list[str], context: str = "") -> dict:
        result = NormalizationResult()

        for raw in raw_skills:
            skill_clean = raw.strip()
            if not skill_clean:
                continue

            # 1. Alias lookup (case-sensitive first, then lower)
            match = ALIAS_LOOKUP.get(skill_clean) or ALIAS_LOOKUP.get(skill_clean.lower())

            if match:
                canonical, category = match
                result.normalized_skills.append(NormalizedSkill(
                    original=skill_clean,
                    canonical=canonical,
                    category=category,
                    proficiency=infer_proficiency(skill_clean, context),
                ))
                continue

            # 2. Semantic match
            sem = self._semantic_match(skill_clean)
            if sem:
                canonical, category, score = sem
                result.normalized_skills.append(NormalizedSkill(
                    original=skill_clean,
                    canonical=canonical,
                    category=category,
                    proficiency=infer_proficiency(skill_clean, context),
                    similarity_score=score,
                ))
                continue

            # 3. Unknown
            result.unknown_skills.append(skill_clean)

        # Inference rules
        canonical_set = {s.canonical for s in result.normalized_skills}
        result.inferred_skills = _apply_inference_rules(canonical_set)

        return result.to_dict()


# ─────────────────────────────────────────────
# Module-level convenience
# ─────────────────────────────────────────────

_normalizer_instance: Optional[SkillNormalizer] = None

def normalize_skills(raw_skills: list[str], context: str = "") -> dict:
    global _normalizer_instance
    if _normalizer_instance is None:
        _normalizer_instance = SkillNormalizer()
    return _normalizer_instance.normalize_skills(raw_skills, context)
