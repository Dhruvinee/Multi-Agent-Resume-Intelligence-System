import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// API Configuration
const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'test-api-key';

// Configure axios defaults
axios.defaults.baseURL = API_BASE_URL;
axios.defaults.headers.common['Authorization'] = `Bearer ${API_KEY}`;

function App() {
  const [activeTab, setActiveTab] = useState('company'); // 'company', 'resume', 'match'
  const [loading, setLoading] = useState(false);
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [selectedCandidate, setSelectedCandidate] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [matchResults, setMatchResults] = useState(null);
  
  // Company form states
  const [companySkills, setCompanySkills] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [minExperience, setMinExperience] = useState('');
  const [educationLevel, setEducationLevel] = useState('');
  const [extractedSkills, setExtractedSkills] = useState(null);
  
  // Resume upload states
  const [uploadedFile, setUploadedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  
  // Fetch candidates on load
  useEffect(() => {
    fetchCandidates();
    fetchJobs();
  }, []);
  
  const fetchCandidates = async () => {
    try {
      // Note: You might need to add a GET /candidates endpoint
      const response = await axios.get('/api/v1/candidates');
      setCandidates(Object.values(response.data));
    } catch (error) {
      console.error('Error fetching candidates:', error);
    }
  };
  
  const fetchJobs = async () => {
    try {
      const response = await axios.get('/api/v1/company/jobs');
      setJobs(response.data.jobs || []);
    } catch (error) {
      console.error('Error fetching jobs:', error);
    }
  };
  
  // Extract skills from company text
  const handleExtractSkills = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/api/v1/company/extract-skills', {
        skills_text: companySkills,
        context: jobTitle || 'Job Requirement'
      });
      setExtractedSkills(response.data);
      alert(`Extracted ${response.data.total_skills_found} skills successfully!`);
    } catch (error) {
      console.error('Error extracting skills:', error);
      alert('Error extracting skills: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  // Create job requirements
  const handleCreateJob = async () => {
    if (!jobTitle || !jobDescription) {
      alert('Please fill in job title and description');
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post('/api/v1/company/job-requirements', {
        job_title: jobTitle,
        job_description: jobDescription,
        min_experience_years: minExperience ? parseFloat(minExperience) : null,
        education_level: educationLevel || null,
        department: 'Engineering'
      });
      alert('Job created successfully!');
      fetchJobs();
      // Clear form
      setJobTitle('');
      setJobDescription('');
      setMinExperience('');
      setEducationLevel('');
      setCompanySkills('');
      setExtractedSkills(null);
    } catch (error) {
      console.error('Error creating job:', error);
      alert('Error creating job: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  // Upload and parse resume
  const handleUploadResume = async () => {
    if (!uploadedFile) {
      alert('Please select a file first');
      return;
    }
    
    setLoading(true);
    setUploadProgress(0);
    
    const formData = new FormData();
    formData.append('file', uploadedFile);
    
    try {
      const response = await axios.post('/api/v1/parse', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        }
      });
      
      alert('Resume parsed successfully!');
      setUploadedFile(null);
      setUploadProgress(0);
      fetchCandidates();
      
      // Show parsed data
      console.log('Parsed resume:', response.data);
    } catch (error) {
      console.error('Error uploading resume:', error);
      alert('Error uploading resume: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  // Match candidate with job
  const handleMatchCandidate = async () => {
    if (!selectedCandidate || !selectedJob) {
      alert('Please select both a candidate and a job');
      return;
    }
    
    setLoading(true);
    try {
      // First get the job requirements
      const jobData = jobs.find(j => j.job_id === selectedJob);
      
      const response = await axios.post(`/api/v1/company/match-candidate?candidate_id=${selectedCandidate}`, {
        job_title: jobData.job_title,
        job_description: jobData.original_description,
        min_experience_years: jobData.requirements.min_experience_years,
        education_level: jobData.requirements.education_level
      });
      
      setMatchResults(response.data.match_result);
      alert('Matching completed!');
    } catch (error) {
      console.error('Error matching:', error);
      alert('Error matching: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  // Quick match with skills text
  const handleQuickMatch = async (skillsText) => {
    if (!selectedCandidate) {
      alert('Please select a candidate first');
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post(`/api/v1/company/match-from-text`, null, {
        params: {
          candidate_id: selectedCandidate,
          skills_text: skillsText,
          job_context: 'Quick Match'
        }
      });
      
      setMatchResults(response.data.match_result);
      alert('Quick match completed!');
    } catch (error) {
      console.error('Error in quick match:', error);
      alert('Error in quick match: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="App">
      <header className="header">
        <h1>🤖 Multi-Agent Resume Intelligence System</h1>
        <p>AI-Powered Resume Parsing & Skill Matching</p>
      </header>
      
      <div className="tabs">
        <button 
          className={activeTab === 'company' ? 'tab active' : 'tab'} 
          onClick={() => setActiveTab('company')}
        >
          🏢 Company Portal
        </button>
        <button 
          className={activeTab === 'resume' ? 'tab active' : 'tab'} 
          onClick={() => setActiveTab('resume')}
        >
          📄 Resume Upload
        </button>
        <button 
          className={activeTab === 'match' ? 'tab active' : 'tab'} 
          onClick={() => setActiveTab('match')}
        >
          🎯 Candidate Matching
        </button>
      </div>
      
      {/* Company Portal Tab */}
      {activeTab === 'company' && (
        <div className="tab-content">
          <div className="card">
            <h2>📝 Enter Job Requirements</h2>
            
            <div className="form-group">
              <label>Job Title *</label>
              <input
                type="text"
                placeholder="e.g., Senior Python Developer"
                value={jobTitle}
                onChange={(e) => setJobTitle(e.target.value)}
              />
            </div>
            
            <div className="form-group">
              <label>Skills Text (comma-separated or paragraph)</label>
              <textarea
                rows="4"
                placeholder="e.g., Python, Machine Learning, SQL, AWS, Docker, Kubernetes&#10;&#10;Or paste job description paragraph here..."
                value={companySkills}
                onChange={(e) => setCompanySkills(e.target.value)}
              />
              <button 
                onClick={handleExtractSkills} 
                disabled={!companySkills || loading}
                className="btn-secondary"
              >
                🔍 Extract Skills
              </button>
            </div>
            
            {extractedSkills && (
              <div className="skills-preview">
                <h3>✅ Extracted Skills ({extractedSkills.total_skills_found})</h3>
                <div className="skills-list">
                  {extractedSkills.extracted_skills.map((skill, idx) => (
                    <span key={idx} className="skill-tag">{skill}</span>
                  ))}
                </div>
                {extractedSkills.normalized_skills.length > 0 && (
                  <>
                    <h4>📚 Normalized Skills:</h4>
                    <div className="skills-list">
                      {extractedSkills.normalized_skills.map((skill, idx) => (
                        <span key={idx} className="skill-tag normalized">
                          {skill.canonical}
                        </span>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
            
            <div className="form-group">
              <label>Full Job Description *</label>
              <textarea
                rows="6"
                placeholder="Paste complete job description here..."
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
            </div>
            
            <div className="form-row">
              <div className="form-group">
                <label>Minimum Experience (years)</label>
                <input
                  type="number"
                  placeholder="e.g., 3"
                  value={minExperience}
                  onChange={(e) => setMinExperience(e.target.value)}
                />
              </div>
              
              <div className="form-group">
                <label>Education Level</label>
                <select value={educationLevel} onChange={(e) => setEducationLevel(e.target.value)}>
                  <option value="">Not specified</option>
                  <option value="Bachelor's">Bachelor's Degree</option>
                  <option value="Master's">Master's Degree</option>
                  <option value="PhD">PhD</option>
                  <option value="Associate">Associate Degree</option>
                </select>
              </div>
            </div>
            
            <button 
              onClick={handleCreateJob} 
              disabled={!jobTitle || !jobDescription || loading}
              className="btn-primary"
            >
              {loading ? 'Creating...' : '✨ Create Job Requirements'}
            </button>
          </div>
          
          {/* List Created Jobs */}
          {jobs.length > 0 && (
            <div className="card">
              <h2>📋 Created Jobs ({jobs.length})</h2>
              <div className="jobs-list">
                {jobs.map(job => (
                  <div key={job.job_id} className="job-item">
                    <div>
                      <strong>{job.job_title}</strong>
                      <span className="job-date">{new Date(job.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="job-meta">
                      <span>🎯 {job.required_skills_count} skills required</span>
                      {job.department && <span>🏢 {job.department}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Resume Upload Tab */}
      {activeTab === 'resume' && (
        <div className="tab-content">
          <div className="card">
            <h2>📄 Upload Resume</h2>
            <p className="info-text">Supported formats: PDF, DOCX, TXT</p>
            
            <div className="upload-area">
              <input
                type="file"
                id="resume-file"
                accept=".pdf,.docx,.txt"
                onChange={(e) => setUploadedFile(e.target.files[0])}
                style={{ display: 'none' }}
              />
              <label htmlFor="resume-file" className="upload-label">
                {uploadedFile ? uploadedFile.name : 'Click to select file'}
              </label>
              
              {uploadProgress > 0 && (
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${uploadProgress}%` }}>
                    {uploadProgress}%
                  </div>
                </div>
              )}
              
              <button 
                onClick={handleUploadResume} 
                disabled={!uploadedFile || loading}
                className="btn-primary"
              >
                {loading ? 'Processing...' : '🚀 Parse Resume'}
              </button>
            </div>
          </div>
          
          {/* List Parsed Candidates */}
          {candidates.length > 0 && (
            <div className="card">
              <h2>📊 Parsed Candidates ({candidates.length})</h2>
              <div className="candidates-grid">
                {candidates.map(candidate => (
                  <div key={candidate.candidate_id} className="candidate-card">
                    <h3>{candidate.name || 'Unknown Name'}</h3>
                    <p>📧 {candidate.email || 'No email'}</p>
                    <p>💼 Experience: {candidate.years_of_experience || 0} years</p>
                    {candidate.skills && (
                      <div>
                        <strong>Skills:</strong>
                        <div className="skills-list small">
                          {candidate.skills.slice(0, 5).map((skill, idx) => (
                            <span key={idx} className="skill-tag small">{skill}</span>
                          ))}
                          {candidate.skills.length > 5 && <span>+{candidate.skills.length - 5} more</span>}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Candidate Matching Tab */}
      {activeTab === 'match' && (
        <div className="tab-content">
          <div className="card">
            <h2>🎯 Match Candidates with Jobs</h2>
            
            <div className="form-row">
              <div className="form-group">
                <label>Select Candidate</label>
                <select 
                  value={selectedCandidate || ''} 
                  onChange={(e) => setSelectedCandidate(e.target.value)}
                >
                  <option value="">Choose a candidate...</option>
                  {candidates.map(candidate => (
                    <option key={candidate.candidate_id} value={candidate.candidate_id}>
                      {candidate.name || candidate.candidate_id.substring(0, 8)} ({candidate.years_of_experience || 0} years)
                    </option>
                  ))}
                </select>
              </div>
              
              <div className="form-group">
                <label>Select Job</label>
                <select 
                  value={selectedJob || ''} 
                  onChange={(e) => setSelectedJob(e.target.value)}
                >
                  <option value="">Choose a job...</option>
                  {jobs.map(job => (
                    <option key={job.job_id} value={job.job_id}>
                      {job.job_title} ({job.required_skills_count} skills)
                    </option>
                  ))}
                </select>
              </div>
            </div>
            
            <button 
              onClick={handleMatchCandidate} 
              disabled={!selectedCandidate || !selectedJob || loading}
              className="btn-primary"
            >
              {loading ? 'Matching...' : '🔍 Match Candidate'}
            </button>
            
            {/* Quick Match Section */}
            <hr className="divider" />
            <h3>⚡ Quick Match with Skills Text</h3>
            <div className="quick-match-buttons">
              <button onClick={() => handleQuickMatch('Python, SQL, Machine Learning')}>
                Python/SQL/ML
              </button>
              <button onClick={() => handleQuickMatch('JavaScript, React, Node.js')}>
                Full Stack
              </button>
              <button onClick={() => handleQuickMatch('AWS, Docker, Kubernetes')}>
                DevOps
              </button>
              <button onClick={() => handleQuickMatch('Java, Spring Boot, Microservices')}>
                Java Backend
              </button>
            </div>
          </div>
          
          {/* Match Results */}
          {matchResults && (
            <div className="card results">
              <h2>📊 Match Results</h2>
              
              <div className="score-card">
                <div className="score-circle">
                  <div className="score-number">{matchResults.match_score}</div>
                  <div className="score-label">Match Score</div>
                </div>
                <div className="verdict">{matchResults.verdict}</div>
              </div>
              
              <div className="match-details">
                <div className="detail-section">
                  <h3>✅ Matched Skills</h3>
                  <div className="skills-list">
                    {matchResults.matched_skills.map((skill, idx) => (
                      <span key={idx} className="skill-tag matched">{skill}</span>
                    ))}
                  </div>
                </div>
                
                <div className="detail-section">
                  <h3>❌ Missing Skills</h3>
                  <div className="skills-list">
                    {matchResults.missing_skills.map((skill, idx) => (
                      <span key={idx} className="skill-tag missing">{skill}</span>
                    ))}
                  </div>
                </div>
                
                <div className="detail-section">
                  <h3>💼 Experience Match</h3>
                  <p>{matchResults.experience_match}</p>
                </div>
                
                <div className="detail-section">
                  <h3>💡 Recommendation</h3>
                  <p className="recommendation">{matchResults.recommendation}</p>
                </div>
                
                <div className="detail-section">
                  <h3>📝 Gap Analysis</h3>
                  <p>{matchResults.gap_analysis}</p>
                </div>
                
                {matchResults.upskilling_suggestions && (
                  <div className="detail-section">
                    <h3>📚 Upskilling Suggestions</h3>
                    <ul>
                      {matchResults.upskilling_suggestions.map((suggestion, idx) => (
                        <li key={idx}>{suggestion}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
      
      {loading && (
        <div className="loading-overlay">
          <div className="spinner"></div>
          <p>Processing...</p>
        </div>
      )}
    </div>
  );
}

export default App;