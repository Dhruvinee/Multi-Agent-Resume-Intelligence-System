# 🚀 Multi-Agent AI System for Resume Intelligence

## 📌 Overview
Recruitment teams process thousands of resumes daily across inconsistent formats and layouts. Traditional Applicant Tracking Systems (ATS) rely heavily on keyword matching, often missing qualified candidates due to variations in terminology (e.g., "React.js" vs "ReactJS").

This project presents a **Multi-Agent AI system** that:
- Parses resumes from multiple formats (PDF, DOCX, text)
- Extracts structured candidate information
- Normalizes skills using a hierarchical taxonomy
- Performs semantic matching with job descriptions
- Exposes functionality through production-ready REST APIs

---

## 🎯 Objectives
- Improve candidate-job matching accuracy
- Reduce recruiter workload through automation
- Handle diverse resume formats and structures
- Provide API-ready talent intelligence for integration

---

## 🧠 System Architecture

The system is composed of multiple intelligent agents coordinated through an orchestration layer:

### 🔹 1. Resume Parsing Agent
- Extracts structured data from resumes
- Supports PDF, DOCX, and plain text formats
- Handles multiple layouts (single/multi-column, tables, creative designs)

**Extracted Fields:**
- Personal details (name, contact, location)
- Work experience (role, company, duration)
- Education
- Skills
- Projects, certifications, publications

---

### 🔹 2. Skill Normalization Agent
- Maps extracted skills to a standardized taxonomy
- Handles:
  - Synonyms (JS → JavaScript)
  - Abbreviations (K8s → Kubernetes)
  - Skill hierarchy inference (TensorFlow → Deep Learning)
  - Proficiency estimation
  - New skill detection

---

### 🔹 3. Semantic Matching Agent
- Uses embeddings to match candidate profiles with job descriptions
- Features:
  - Vector similarity-based matching
  - Weighted scoring (required vs optional skills)
  - Experience-based weighting
  - Skill gap analysis
  - Configurable matching thresholds

---

### 🔹 4. Orchestration Layer
- Coordinates all agents
- Handles:
  - Task scheduling
  - Batch processing
  - Retry mechanisms
  - Fault tolerance
  - Logging and monitoring

---

### 🔹 5. API Layer
- RESTful API for external integration
- OpenAPI/Swagger documentation
- Secure and scalable endpoints

---
