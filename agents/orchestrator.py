import uuid
import logging
from typing import Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from agents.parser_agent import parse_resume
from agents.normalizer_agent import normalize_skills
from agents.matcher_agent import match_candidate_to_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class ExecutionTrace:
    parse_duration:     float = 0.0
    normalize_duration: float = 0.0
    match_duration:     float = 0.0
    total_duration:     float = 0.0

    def to_dict(self) -> dict:
        return {
            "parser_duration":     round(self.parse_duration, 3),
            "normalizer_duration": round(self.normalize_duration, 3),
            "matcher_duration":    round(self.match_duration, 3),
            "total_duration":      round(self.total_duration, 3),
        }


@dataclass
class PipelineResult:
    job_id:         str
    candidate_id:   str
    candidate_data: dict
    match_result:   Optional[dict]
    trace:          ExecutionTrace
    error:          Optional[str] = None

    def to_dict(self) -> dict:
        if self.error:
            return {"job_id": self.job_id, "error": self.error}
        return {
            "job_id":          self.job_id,
            "candidate_id":    self.candidate_id,
            "candidate_data":  self.candidate_data,
            "match_result":    self.match_result,
            "execution_trace": self.trace.to_dict(),
        }


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _timer() -> float:
    return datetime.now().timestamp()


def _elapsed(start: float) -> float:
    return round(datetime.now().timestamp() - start, 3)


# ─────────────────────────────────────────────
# Orchestrator
# ─────────────────────────────────────────────

class MultiAgentOrchestrator:
    def __init__(self, max_concurrent: int = 5):
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)

    def process_resume(
        self,
        file_path: str,
        job_description: Optional[str] = None,
    ) -> dict:
        job_id       = str(uuid.uuid4())
        candidate_id = str(uuid.uuid4())
        trace        = ExecutionTrace()
        total_start  = _timer()

        logger.info(f"[{job_id}] Pipeline started — {file_path}")

        try:
            # ── Step 1: Parse ─────────────────────────
            t = _timer()
            candidate_data = parse_resume(file_path)
            trace.parse_duration = _elapsed(t)

            if candidate_data.get("error"):
                raise RuntimeError(f"Parser failed: {candidate_data['error']}")

            candidate_data["candidate_id"] = candidate_id
            logger.info(f"[{job_id}] Parse done ({trace.parse_duration}s)")

            # ── Step 2: Normalize ─────────────────────
            t = _timer()
            raw_skills = candidate_data.get("skills", [])
            candidate_data["normalized_skills"] = (
                normalize_skills(
                    raw_skills,
                    context=str(candidate_data.get("experience", [])),
                )
                if raw_skills
                else {"normalized_skills": [], "inferred_skills": [], "unknown_skills": []}
            )
            trace.normalize_duration = _elapsed(t)
            logger.info(f"[{job_id}] Normalize done ({trace.normalize_duration}s)")

            # ── Step 3: Match (optional) ──────────────
            match_result = None
            if job_description:
                t = _timer()
                match_result = match_candidate_to_job(candidate_data, job_description)
                trace.match_duration = _elapsed(t)
                logger.info(f"[{job_id}] Match done ({trace.match_duration}s)")

            trace.total_duration = _elapsed(total_start)
            logger.info(f"[{job_id}] Pipeline complete ({trace.total_duration}s)")

            return PipelineResult(
                job_id=job_id,
                candidate_id=candidate_id,
                candidate_data=candidate_data,
                match_result=match_result,
                trace=trace,
            ).to_dict()

        except Exception as e:
            logger.error(f"[{job_id}] Pipeline failed: {e}")
            return PipelineResult(
                job_id=job_id,
                candidate_id=candidate_id,
                candidate_data={},
                match_result=None,
                trace=trace,
                error=str(e),
            ).to_dict()

    def process_batch(
        self,
        file_paths: list[str],
        job_description: Optional[str] = None,
    ) -> list[dict]:
        """Process multiple resumes concurrently, preserving per-file status."""
        futures = {
            self.executor.submit(self.process_resume, path, job_description): path
            for path in file_paths
        }
        results = []
        for future in as_completed(futures):
            path = futures[future]
            try:
                data = future.result()
                results.append({"status": "success", "file": path, "data": data})
                logger.info(f"Completed: {path}")
            except Exception as e:
                logger.error(f"Failed: {path} — {e}")
                results.append({"status": "error", "file": path, "error": str(e)})

        return results

    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shut down the thread pool."""
        self.executor.shutdown(wait=wait)
        logger.info("Orchestrator shut down")


# ─────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────

_orchestrator_instance: Optional[MultiAgentOrchestrator] = None

def get_orchestrator(max_concurrent: int = 5) -> MultiAgentOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = MultiAgentOrchestrator(max_concurrent=max_concurrent)
    return _orchestrator_instance
