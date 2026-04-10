from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import os
import uuid
import tempfile
from datetime import datetime
from agents.jd_agent import process_job_description

from agents.parser_agent import parse_resume
from agents.normalizer_agent import normalize_skills, TAXONOMY
from agents.matcher_agent import match_candidate_to_job
from agents.orchestrator import orchestrator

app = FastAPI(
    title="Multi-Agent Resume Intelligence API",
    version="2.0.0",
    description="Multi-Agent AI System for Intelligent Resume Parsing and Skill Matching"
)

# Security
security = HTTPBearer()
API_KEYS = {"test-api-key": "company_a"}

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return credentials.credentials

# In-memory storage
candidates = {}
batch_jobs = {}
jobs = {}
# ============= Models =============

class MatchRequest(BaseModel):
    candidate_id: str
    job_description: str = Field(..., min_length=10)
class JobInput(BaseModel):
    title: Optional[str] = ""
    description: str = Field(..., min_length=10)
    skills: List[str] = []   # admin-specified skills
class MatchJobRequest(BaseModel):
    candidate_id: str
    job_id: str
# ============= API Endpoints =============

@app.post("/api/v1/parse")
async def parse_resume_endpoint(
    file: UploadFile = File(...),
    api_key: str = Depends(verify_api_key)
):
    """Parse a single resume (PDF, DOCX, or TXT)"""
    
    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".txt"}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create temporary file (Windows compatible)
    temp_file = None
    temp_path = None
    try:
        # Read file content
        content = await file.read()
        
        # Create temp file with proper extension
        suffix = f"_{file.filename}"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        temp_file.write(content)
        temp_file.close()
        
        print(f"Temp file created at: {temp_path}")  # Debug print
        
        # Process through orchestrator
        result = orchestrator.process_resume(temp_path)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Store candidate
        candidate_id = result["candidate_id"]
        candidates[candidate_id] = result["candidate_data"]
        
        return {
            "success": True,
            "candidate_id": candidate_id,
            "data": result["candidate_data"],
            "execution_trace": result.get("execution_trace", {})
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")  # Debug print
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
                print(f"Temp file deleted: {temp_path}")  # Debug print
            except Exception as e:
                print(f"Error deleting temp file: {e}")

@app.post("/api/v1/parse/batch")
async def batch_parse_resumes(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = None,
    api_key: str = Depends(verify_api_key)
):
    """Process multiple resumes asynchronously"""
    
    if len(files) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 files per batch")
    
    batch_id = str(uuid.uuid4())
    batch_jobs[batch_id] = {
        "status": "processing",
        "total": len(files),
        "completed": 0,
        "results": [],
        "created_at": datetime.now().isoformat()
    }
    
    def process_batch():
        file_paths = []
        temp_files = []
        
        try:
            # Save all files using temporary files
            import asyncio
            
            for file in files:
                # Create temp file for each upload
                suffix = f"_{file.filename}"
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                temp_path = temp_file.name
                
                # Read file content (handle async in sync context)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                content = loop.run_until_complete(file.read())
                temp_file.write(content)
                temp_file.close()
                
                file_paths.append(temp_path)
                temp_files.append(temp_path)
            
            # Process batch
            results = orchestrator.process_batch(file_paths)
            
            # Store results
            for result in results:
                if result["status"] == "success":
                    candidate_id = result["data"]["candidate_id"]
                    candidates[candidate_id] = result["data"]["candidate_data"]
                    batch_jobs[batch_id]["results"].append({
                        "candidate_id": candidate_id,
                        "status": "success",
                        "file": result.get("file", "unknown")
                    })
                else:
                    batch_jobs[batch_id]["results"].append({
                        "status": "error",
                        "error": result.get("error", "Unknown error"),
                        "file": result.get("file", "unknown")
                    })
                
                batch_jobs[batch_id]["completed"] += 1
            
            batch_jobs[batch_id]["status"] = "completed"
            
        except Exception as e:
            batch_jobs[batch_id]["status"] = "failed"
            batch_jobs[batch_id]["error"] = str(e)
        finally:
            # Clean up temp files
            for path in temp_files:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
    
    background_tasks.add_task(process_batch)
    
    return {
        "batch_id": batch_id,
        "status": "processing",
        "total_files": len(files),
        "message": "Batch processing started"
    }
@app.post("/api/v1/jobs")
async def create_job(job: JobInput, api_key: str = Depends(verify_api_key)):
    """Admin submits a job description. Skills are extracted + normalized automatically."""
    job_id = str(uuid.uuid4())

    # Run JD through the agent pipeline
    processed = process_job_description(job.description, job.skills or [])

    jobs[job_id] = {
        "job_id": job_id,
        "title": job.title or processed.get("role_title", ""),
        "created_at": datetime.now().isoformat(),
        **processed   # merges all structured fields in
    }

    return {
        "success": True,
        "job_id": job_id,
        "role_title": jobs[job_id]["title"],
        "role_summary": processed.get("role_summary", ""),
        "required_skills": processed["required_skills"],
        "nice_to_have_skills": processed["nice_to_have_skills"],
        "unknown_skills": processed.get("unknown_skills", []),
        "skill_categories": processed.get("skill_categories", {}),
        "message": "Job created and skills normalized successfully"
    }
@app.get("/api/v1/jobs/{job_id}")
async def get_job(job_id: str, api_key: str = Depends(verify_api_key)):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return jobs[job_id]
@app.post("/api/v1/match/job")
async def match_with_job(req: MatchJobRequest, api_key: str = Depends(verify_api_key)):
    
    if req.candidate_id not in candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if req.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[req.job_id]

    result = match_candidate_to_job(
        candidates[req.candidate_id],
        job["description"]
    )

    return {
        "job_id": req.job_id,
        "candidate_id": req.candidate_id,
        "match_result": result
    }
@app.get("/api/v1/batch/{batch_id}/status")
async def get_batch_status(batch_id: str, api_key: str = Depends(verify_api_key)):
    """Get batch processing status"""
    if batch_id not in batch_jobs:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch_jobs[batch_id]

@app.get("/api/v1/candidates/{candidate_id}")
async def get_candidate(candidate_id: str, api_key: str = Depends(verify_api_key)):
    """Get candidate profile"""
    if candidate_id not in candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return candidates[candidate_id]

@app.get("/api/v1/candidates/{candidate_id}/skills")
async def get_candidate_skills(candidate_id: str, api_key: str = Depends(verify_api_key)):
    """Get normalized skills"""
    if candidate_id not in candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate = candidates[candidate_id]
    return candidate.get("normalized_skills", {})

@app.post("/api/v1/match")
async def match_job(req: MatchRequest, api_key: str = Depends(verify_api_key)):
    """Match candidate with job"""
    if req.candidate_id not in candidates:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    result = match_candidate_to_job(
        candidates[req.candidate_id], 
        req.job_description
    )
    return result

@app.get("/api/v1/skills/taxonomy")
async def get_taxonomy(
    category: Optional[str] = None,
    search: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Browse skill taxonomy"""
    taxonomy = TAXONOMY
    
    if category and category in taxonomy:
        taxonomy = {category: taxonomy[category]}
    
    if search:
        search_lower = search.lower()
        filtered = {}
        for cat, data in taxonomy.items():
            matching_skills = [
                skill for skill in data["skills"] 
                if search_lower in skill.lower()
            ]
            if matching_skills:
                filtered[cat] = {**data, "skills": matching_skills}
        taxonomy = filtered
    
    return taxonomy

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

@app.get("/metrics")
async def get_metrics():
    """Get system metrics"""
    return {
        "total_candidates": len(candidates),
        "active_batches": len([j for j in batch_jobs.values() if j["status"] == "processing"]),
        "completed_batches": len([j for j in batch_jobs.values() if j["status"] == "completed"])
    }