"""
test_system.py
Comprehensive test script for Multi-Agent Resume Intelligence System
"""

import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

# Add project root to path if needed
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import all agents
from agents.parser_agent import parse_resume, ResumeParser
from agents.normalizer_agent import normalize_skills, TAXONOMY
from agents.matcher_agent import match_candidate_to_job
from agents.jd_agent import process_job_description
from agents.orchestrator import get_orchestrator


def create_sample_resume_pdf() -> str:
    """Create a sample resume PDF file for testing."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        print("⚠️  reportlab not installed. Creating a text file instead.")
        return create_sample_resume_txt()
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_file.close()
    
    doc = SimpleDocTemplate(temp_file.name, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=12,
        spaceBefore=20,
        spaceAfter=10
    )
    
    # Content
    story = []
    
    # Name and contact
    story.append(Paragraph("John Smith", title_style))
    story.append(Paragraph("Email: john.smith@email.com | Phone: +1 (555) 123-4567", styles['Normal']))
    story.append(Paragraph("Location: San Francisco, CA | LinkedIn: linkedin.com/in/johnsmith", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Summary
    story.append(Paragraph("Professional Summary", heading_style))
    story.append(Paragraph("Senior Software Engineer with 5+ years of experience in full-stack development, specializing in Python, React, and cloud technologies.", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Skills
    story.append(Paragraph("Technical Skills", heading_style))
    story.append(Paragraph("• Python, JavaScript, TypeScript", styles['Normal']))
    story.append(Paragraph("• React, Node.js, FastAPI, Django", styles['Normal']))
    story.append(Paragraph("• AWS, Docker, Kubernetes, Terraform", styles['Normal']))
    story.append(Paragraph("• PostgreSQL, MongoDB, Redis", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Experience
    story.append(Paragraph("Work Experience", heading_style))
    story.append(Paragraph("<b>Senior Software Engineer</b> | Tech Corp | 2022 - Present", styles['Normal']))
    story.append(Paragraph("• Led development of microservices architecture using Python and FastAPI", styles['Normal']))
    story.append(Paragraph("• Deployed applications on AWS EKS with 99.9% uptime", styles['Normal']))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("<b>Software Engineer</b> | Startup Inc | 2019 - 2022", styles['Normal']))
    story.append(Paragraph("• Built responsive web applications using React and Redux", styles['Normal']))
    story.append(Paragraph("• Implemented CI/CD pipelines using GitHub Actions", styles['Normal']))
    story.append(Spacer(1, 15))
    
    # Education
    story.append(Paragraph("Education", heading_style))
    story.append(Paragraph("<b>M.S. in Computer Science</b> | Stanford University | 2019", styles['Normal']))
    story.append(Paragraph("<b>B.S. in Software Engineering</b> | UC Berkeley | 2017", styles['Normal']))
    
    doc.build(story)
    return temp_file.name


def create_sample_resume_txt() -> str:
    """Create a sample resume text file."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode='w', encoding='utf-8')
    
    resume_content = """
    JOHN SMITH
    Email: john.smith@email.com
    Phone: +1 (555) 123-4567
    Location: San Francisco, CA
    LinkedIn: linkedin.com/in/johnsmith
    GitHub: github.com/johnsmith

    PROFESSIONAL SUMMARY
    Senior Software Engineer with 5+ years of experience in full-stack development, 
    specializing in Python, React, and cloud technologies.

    TECHNICAL SKILLS
    • Programming: Python, JavaScript, TypeScript, Java
    • Web Frameworks: React, Node.js, FastAPI, Django
    • Cloud & DevOps: AWS, Docker, Kubernetes, Terraform, CI/CD
    • Databases: PostgreSQL, MongoDB, Redis
    • ML & Data: TensorFlow, Pandas, NumPy

    WORK EXPERIENCE
    Senior Software Engineer | Tech Corp | 2022 - Present
    • Led development of microservices architecture using Python and FastAPI
    • Deployed applications on AWS EKS with 99.9% uptime
    • Implemented automated testing and monitoring solutions

    Software Engineer | Startup Inc | 2019 - 2022
    • Built responsive web applications using React and Redux
    • Implemented CI/CD pipelines using GitHub Actions
    • Optimized database queries improving performance by 40%

    EDUCATION
    M.S. in Computer Science | Stanford University | 2019
    B.S. in Software Engineering | UC Berkeley | 2017

    CERTIFICATIONS
    • AWS Certified Solutions Architect
    • Kubernetes Administrator (CKA)
    """
    
    temp_file.write(resume_content.strip())
    temp_file.close()
    return temp_file.name


def create_sample_job_description() -> str:
    """Create a sample job description."""
    return """
    Senior Full Stack Engineer
    
    We are looking for a Senior Full Stack Engineer to join our growing team!
    
    Required Skills:
    - 5+ years of experience in software development
    - Strong proficiency in Python and JavaScript/TypeScript
    - Experience with React or similar frontend frameworks
    - Knowledge of Node.js or similar backend frameworks
    - Experience with AWS services (EC2, S3, Lambda)
    - Docker and Kubernetes experience
    
    Nice to Have:
    - Experience with FastAPI or Django
    - Terraform knowledge
    - Machine learning experience
    
    Responsibilities:
    - Design and implement scalable web applications
    - Lead technical discussions and code reviews
    - Mentor junior developers
    - Collaborate with cross-functional teams
    
    Education: Bachelor's degree in Computer Science or related field
    """


def test_parser_agent() -> Dict[str, Any]:
    """Test the parser agent with a sample resume."""
    print("\n" + "="*60)
    print("TESTING: Parser Agent")
    print("="*60)
    
    try:
        # Create sample resume
        resume_path = create_sample_resume_pdf() if reportlab_available() else create_sample_resume_txt()
        print(f"✅ Created test resume: {resume_path}")
        
        # Parse resume
        result = parse_resume(resume_path)
        
        # Clean up
        os.unlink(resume_path)
        
        if "error" in result:
            print(f"❌ Parser failed: {result['error']}")
            return {"status": "failed", "error": result["error"]}
        
        # Validate results
        print(f"✅ Name: {result.get('name', 'N/A')}")
        print(f"✅ Email: {result.get('email', 'N/A')}")
        print(f"✅ Years Experience: {result.get('years_of_experience', 0)}")
        print(f"✅ Skills found: {len(result.get('skills', []))}")
        print(f"✅ Experience entries: {len(result.get('experience', []))}")
        print(f"✅ Education entries: {len(result.get('education', []))}")
        
        assert result.get('name'), "Name should not be empty"
        assert result.get('email'), "Email should not be empty"
        assert len(result.get('skills', [])) > 0, "Skills should be extracted"
        
        print("✅ Parser agent test PASSED")
        return {"status": "passed", "data": result}
        
    except Exception as e:
        print(f"❌ Parser agent test FAILED: {e}")
        return {"status": "failed", "error": str(e)}


def test_normalizer_agent() -> Dict[str, Any]:
    """Test the normalizer agent with sample skills."""
    print("\n" + "="*60)
    print("TESTING: Normalizer Agent")
    print("="*60)
    
    try:
        # Sample raw skills
        raw_skills = [
            "Python", "py", "JS", "ReactJS", "AWS Cloud", 
            "K8s", "ML", "TensorFlow", "Postgres", "Mongo"
        ]
        
        print(f"📝 Raw skills: {raw_skills}")
        
        # Normalize skills
        result = normalize_skills(raw_skills, context="5 years experience in software development")
        
        normalized = result.get("normalized_skills", [])
        unknown = result.get("unknown_skills", [])
        
        print(f"✅ Normalized skills: {len(normalized)}")
        for skill in normalized[:5]:  # Show first 5
            print(f"   - {skill['original']} → {skill['canonical']} ({skill['category']})")
        
        print(f"✅ Unknown skills: {unknown}")
        print(f"✅ Skill categories: {list(result.get('skill_categories', {}).keys())}")
        
        assert len(normalized) > 0, "Should normalize at least some skills"
        assert "python" in [s["canonical"].lower() for s in normalized], "Python should be recognized"
        
        print("✅ Normalizer agent test PASSED")
        return {"status": "passed", "data": result}
        
    except Exception as e:
        print(f"❌ Normalizer agent test FAILED: {e}")
        return {"status": "failed", "error": str(e)}


def test_jd_agent() -> Dict[str, Any]:
    """Test the job description agent."""
    print("\n" + "="*60)
    print("TESTING: Job Description Agent")
    print("="*60)
    
    try:
        jd_text = create_sample_job_description()
        admin_skills = ["Team Leadership", "Agile Methodology"]
        
        print("📝 Processing job description...")
        result = process_job_description(jd_text, admin_skills)
        
        print(f"✅ Role Title: {result.get('role_title', 'N/A')}")
        print(f"✅ Role Summary: {result.get('role_summary', 'N/A')[:100]}...")
        print(f"✅ Required Skills: {len(result.get('required_skills', []))}")
        print(f"✅ Nice-to-have Skills: {len(result.get('nice_to_have_skills', []))}")
        print(f"✅ Min Experience: {result.get('min_experience_years', 0)} years")
        print(f"✅ Education Level: {result.get('education_level', 'N/A')}")
        
        assert result.get('required_skills'), "Should have required skills"
        assert "python" in [s.lower() for s in result.get('required_skills', [])], "Python should be required"
        
        print("✅ JD Agent test PASSED")
        return {"status": "passed", "data": result}
        
    except Exception as e:
        print(f"❌ JD Agent test FAILED: {e}")
        return {"status": "failed", "error": str(e)}


def test_matcher_agent() -> Dict[str, Any]:
    """Test the matcher agent with sample candidate and job."""
    print("\n" + "="*60)
    print("TESTING: Matcher Agent")
    print("="*60)
    
    try:
        # Sample candidate profile
        candidate_profile = {
            "name": "John Smith",
            "years_of_experience": 5,
            "skills": ["Python", "React", "AWS", "Docker", "Kubernetes", "PostgreSQL"],
            "normalized_skills": {
                "normalized_skills": [
                    {"canonical": "Python", "category": "Programming Languages"},
                    {"canonical": "React", "category": "Web Frameworks"},
                    {"canonical": "AWS", "category": "Cloud & DevOps"}
                ]
            }
        }
        
        job_description = create_sample_job_description()
        
        print("📝 Matching candidate to job...")
        result = match_candidate_to_job(candidate_profile, job_description)
        
        print(f"✅ Match Score: {result.get('match_score', 0)}/100")
        print(f"✅ Verdict: {result.get('verdict', 'N/A')}")
        print(f"✅ Matched Skills: {len(result.get('matched_skills', []))}")
        print(f"✅ Missing Skills: {len(result.get('missing_skills', []))}")
        print(f"✅ Gap Analysis: {result.get('gap_analysis', 'N/A')[:100]}...")
        
        assert result.get('match_score', 0) > 0, "Should have a match score"
        assert result.get('verdict'), "Should have a verdict"
        
        print("✅ Matcher Agent test PASSED")
        return {"status": "passed", "data": result}
        
    except Exception as e:
        print(f"❌ Matcher Agent test FAILED: {e}")
        return {"status": "failed", "error": str(e)}


def test_orchestrator() -> Dict[str, Any]:
    """Test the orchestrator with full pipeline."""
    print("\n" + "="*60)
    print("TESTING: Orchestrator (Full Pipeline)")
    print("="*60)
    
    try:
        orchestrator = get_orchestrator(max_concurrent=2)
        
        # Create sample resume
        resume_path = create_sample_resume_pdf() if reportlab_available() else create_sample_resume_txt()
        job_description = create_sample_job_description()
        
        print(f"✅ Processing resume: {resume_path}")
        
        # Process single resume
        result = orchestrator.process_resume(resume_path, job_description)
        
        # Clean up
        os.unlink(resume_path)
        
        if "error" in result:
            print(f"❌ Orchestrator failed: {result['error']}")
            return {"status": "failed", "error": result["error"]}
        
        print(f"✅ Job ID: {result.get('job_id', 'N/A')}")
        print(f"✅ Candidate ID: {result.get('candidate_id', 'N/A')}")
        print(f"✅ Execution Trace: {result.get('execution_trace', {})}")
        
        if result.get('match_result'):
            print(f"✅ Match Score: {result['match_result'].get('match_score', 0)}")
        
        assert result.get('candidate_data'), "Should have candidate data"
        assert result.get('execution_trace'), "Should have execution trace"
        
        print("✅ Orchestrator test PASSED")
        return {"status": "passed", "data": result}
        
    except Exception as e:
        print(f"❌ Orchestrator test FAILED: {e}")
        return {"status": "failed", "error": str(e)}


def test_taxonomy() -> Dict[str, Any]:
    """Test the skill taxonomy."""
    print("\n" + "="*60)
    print("TESTING: Skill Taxonomy")
    print("="*60)
    
    try:
        categories = list(TAXONOMY.keys())
        print(f"✅ Categories found: {len(categories)}")
        for cat in categories:
            skills_count = len(TAXONOMY[cat]["skills"])
            aliases_count = len(TAXONOMY[cat]["aliases"])
            print(f"   - {cat}: {skills_count} skills, {aliases_count} aliases")
        
        assert len(categories) > 0, "Should have at least one category"
        
        # Check for common skills
        all_skills = []
        for cat, data in TAXONOMY.items():
            all_skills.extend(data["skills"])
        
        common_skills = ["Python", "JavaScript", "AWS", "Docker"]
        found_skills = [s for s in common_skills if s in all_skills]
        print(f"✅ Found common skills: {found_skills}")
        
        print("✅ Taxonomy test PASSED")
        return {"status": "passed", "data": {"categories": categories, "total_skills": len(all_skills)}}
        
    except Exception as e:
        print(f"❌ Taxonomy test FAILED: {e}")
        return {"status": "failed", "error": str(e)}


def reportlab_available() -> bool:
    """Check if reportlab is available for PDF generation."""
    try:
        import reportlab
        return True
    except ImportError:
        return False


def run_all_tests():
    """Run all tests and print summary."""
    print("\n" + "🚀"*30)
    print("STARTING MULTI-AGENT SYSTEM TESTS")
    print("🚀"*30)
    
    # Check environment
    print("\n📋 Environment Check:")
    print(f"   - GROQ_API_KEY: {'✅ Set' if os.getenv('GROQ_API_KEY') else '❌ Missing'}")
    print(f"   - reportlab (PDF creation): {'✅ Available' if reportlab_available() else '⚠️ Not installed (will use TXT)'}")
    
    if not os.getenv('GROQ_API_KEY'):
        print("\n⚠️  WARNING: GROQ_API_KEY not set. Tests requiring LLM will fail.")
        print("   Please set your GROQ_API_KEY environment variable.")
    
    # Run tests
    tests = {
        "Taxonomy": test_taxonomy,
        "Normalizer Agent": test_normalizer_agent,
        "Parser Agent": test_parser_agent,
        "JD Agent": test_jd_agent,
        "Matcher Agent": test_matcher_agent,
        "Orchestrator": test_orchestrator,
    }
    
    results = {}
    for name, test_func in tests.items():
        if name in ["JD Agent", "Matcher Agent", "Orchestrator"] and not os.getenv('GROQ_API_KEY'):
            print(f"\n⚠️  Skipping {name} (GROQ_API_KEY not set)")
            results[name] = {"status": "skipped", "error": "GROQ_API_KEY not set"}
        else:
            results[name] = test_func()
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results.values() if r.get("status") == "passed")
    failed = sum(1 for r in results.values() if r.get("status") == "failed")
    skipped = sum(1 for r in results.values() if r.get("status") == "skipped")
    
    for name, result in results.items():
        status = result.get("status", "unknown")
        if status == "passed":
            print(f"✅ {name}: PASSED")
        elif status == "failed":
            print(f"❌ {name}: FAILED - {result.get('error', 'Unknown error')}")
        else:
            print(f"⚠️  {name}: SKIPPED")
    
    print(f"\n📊 Total: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        print("\n🎉 All tests passed successfully!")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please check the errors above.")
    
    return results


if __name__ == "__main__":
    run_all_tests()