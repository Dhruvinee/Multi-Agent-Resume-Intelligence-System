import uuid
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from agents.parser_agent import parse_resume
from agents.normalizer_agent import normalize_skills
from agents.matcher_agent import match_candidate_to_job

class MultiAgentOrchestrator:
    """Orchestrates multiple agents for resume processing pipeline"""
    
    def __init__(self, max_concurrent: int = 5):
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent)
        self.jobs = {}
    
    def process_resume(self, file_path: str, job_description: Optional[str] = None) -> Dict:
        """Orchestrate the entire resume processing pipeline"""
        job_id = str(uuid.uuid4())
        candidate_id = str(uuid.uuid4())
        
        start_time = datetime.now()
        
        try:
            # Step 1: Parse Resume
            print(f"Job {job_id}: Starting parser agent")
            parse_start = datetime.now()
            candidate_data = parse_resume(file_path)
            parse_duration = (datetime.now() - parse_start).total_seconds()
            
            if "error" in candidate_data:
                raise Exception(f"Parser failed: {candidate_data['error']}")
            
            candidate_data["candidate_id"] = candidate_id
            
            # Step 2: Normalize Skills
            print(f"Job {job_id}: Starting normalizer agent")
            norm_start = datetime.now()
            if candidate_data.get("skills"):
                normalized = normalize_skills(
                    candidate_data.get("skills", []),
                    context=str(candidate_data.get("experience", []))
                )
                candidate_data["normalized_skills"] = normalized
            else:
                candidate_data["normalized_skills"] = {
                    "normalized_skills": [], 
                    "inferred_skills": [], 
                    "unknown_skills": []
                }
            norm_duration = (datetime.now() - norm_start).total_seconds()
            
            # Step 3: Match with Job (if provided)
            match_result = None
            match_duration = 0
            if job_description:
                print(f"Job {job_id}: Starting matcher agent")
                match_start = datetime.now()
                match_result = match_candidate_to_job(candidate_data, job_description)
                match_duration = (datetime.now() - match_start).total_seconds()
            
            total_duration = (datetime.now() - start_time).total_seconds()
            
            print(f"Job {job_id} completed in {total_duration:.2f}s")
            
            return {
                "job_id": job_id,
                "candidate_id": candidate_id,
                "candidate_data": candidate_data,
                "match_result": match_result,
                "execution_trace": {
                    "parser_duration": parse_duration,
                    "normalizer_duration": norm_duration,
                    "matcher_duration": match_duration,
                    "total_duration": total_duration
                }
            }
            
        except Exception as e:
            print(f"Job {job_id} failed: {str(e)}")
            return {
                "job_id": job_id,
                "error": str(e)
            }
    
    def process_batch(self, file_paths: List[str], job_description: Optional[str] = None) -> List[Dict]:
        """Process multiple resumes concurrently"""
        results = []
        
        # Submit all tasks
        future_to_path = {
            self.executor.submit(self.process_resume, path, job_description): path 
            for path in file_paths
        }
        
        # Collect results
        for future in as_completed(future_to_path):
            path = future_to_path[future]
            try:
                result = future.result()
                results.append({"status": "success", "data": result, "file": path})
                print(f"Completed processing: {path}")
            except Exception as e:
                print(f"Failed processing {path}: {str(e)}")
                results.append({"status": "error", "error": str(e), "file": path})
        
        return results

# Singleton instance
orchestrator = MultiAgentOrchestrator()