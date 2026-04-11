import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import './App.css';

const API_BASE_URL = 'http://localhost:8000';
const API_KEY = 'test-api-key';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { Authorization: `Bearer ${API_KEY}` },
});

// ─── Toast notification system ───────────────────────────────────────────────
function Toast({ toasts, onDismiss }) {
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast toast--${t.type}`}>
          <span className="toast__icon">
            {t.type === 'success' ? '✓' : t.type === 'error' ? '✕' : 'ℹ'}
          </span>
          <span className="toast__msg">{t.message}</span>
          <button className="toast__close" onClick={() => onDismiss(t.id)}>×</button>
        </div>
      ))}
    </div>
  );
}

// ─── Skill tag component ──────────────────────────────────────────────────────
function SkillTag({ label, variant = 'default' }) {
  return <span className={`skill-tag skill-tag--${variant}`}>{label}</span>;
}

// ─── Score ring SVG ───────────────────────────────────────────────────────────
function ScoreRing({ score }) {
  const r = 52;
  const circ = 2 * Math.PI * r;
  const fill = (score / 100) * circ;
  const color =
    score >= 80 ? 'var(--c-teal)' : score >= 60 ? 'var(--c-amber)' : score >= 40 ? 'var(--c-coral)' : 'var(--c-red)';
  const label =
    score >= 80 ? 'Strong Match' : score >= 60 ? 'Good Match' : score >= 40 ? 'Potential' : 'Weak Match';

  return (
    <div className="score-ring-wrap">
      <svg viewBox="0 0 120 120" className="score-ring">
        <circle cx="60" cy="60" r={r} className="score-ring__bg" />
        <circle
          cx="60" cy="60" r={r}
          className="score-ring__fill"
          stroke={color}
          strokeDasharray={`${fill} ${circ}`}
          strokeDashoffset={circ / 4}
        />
        <text x="60" y="56" textAnchor="middle" className="score-ring__num">{Math.round(score)}</text>
        <text x="60" y="72" textAnchor="middle" className="score-ring__pct">/ 100</text>
      </svg>
      <p className="score-ring__label" style={{ color }}>{label}</p>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState('jobs');
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState('Processing…');
  const [toasts, setToasts] = useState([]);

  // Data
  const [candidates, setCandidates] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [matchResult, setMatchResult] = useState(null);
  const [parsedCandidate, setParsedCandidate] = useState(null);
  const [createdJob, setCreatedJob] = useState(null);

  // Job form
  const [jobTitle, setJobTitle] = useState('');
  const [jobDesc, setJobDesc] = useState('');
  const [adminSkills, setAdminSkills] = useState('');

  // Resume upload
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [dragOver, setDragOver] = useState(false);

  // Match tab
  const [selCandidate, setSelCandidate] = useState('');
  const [selJob, setSelJob] = useState('');

  // ── Toasts ──────────────────────────────────────────────────────────────────
  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now();
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5000);
  }, []);
  const dismissToast = (id) => setToasts((t) => t.filter((x) => x.id !== id));

  // ── Data loaders ─────────────────────────────────────────────────────────────
  const loadCandidates = useCallback(async () => {
    // Backend has no list endpoint — we keep a local registry
    // populated after each successful parse. Nothing to fetch on mount.
  }, []);

  const loadJobs = useCallback(async () => {
    // Same — jobs are returned from POST and stored locally
  }, []);

  useEffect(() => {
    loadCandidates();
    loadJobs();
  }, [loadCandidates, loadJobs]);

  // ── Create Job ───────────────────────────────────────────────────────────────
  const handleCreateJob = async () => {
    if (!jobDesc.trim() || jobDesc.trim().length < 10) {
      addToast('Job description must be at least 10 characters.', 'error');
      return;
    }
    setLoading(true);
    setLoadingMsg('Extracting and normalizing skills from your job description…');
    try {
      const skillsList = adminSkills
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

      const { data } = await api.post('/api/v1/jobs', {
        title: jobTitle || undefined,
        description: jobDesc,
        skills: skillsList,
      });

      const newJob = {
        job_id: data.job_id,
        title: data.role_title || jobTitle || 'Untitled Role',
        required_skills: data.required_skills,
        nice_to_have_skills: data.nice_to_have_skills,
        unknown_skills: data.unknown_skills,
        skill_categories: data.skill_categories,
        role_summary: data.role_summary,
        description: jobDesc,
        created_at: new Date().toISOString(),
      };

      setJobs((prev) => [newJob, ...prev]);
      setCreatedJob(newJob);
      addToast(`Job "${newJob.title}" created successfully!`, 'success');

      setJobTitle('');
      setJobDesc('');
      setAdminSkills('');
    } catch (err) {
      addToast(err.response?.data?.detail || err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ── Upload Resume ─────────────────────────────────────────────────────────────
  const handleUpload = async (file) => {
    if (!file) return;
    const allowed = ['.pdf', '.docx', '.txt'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!allowed.includes(ext)) {
      addToast(`Unsupported file type. Allowed: ${allowed.join(', ')}`, 'error');
      return;
    }

    setLoading(true);
    setLoadingMsg('Parsing resume with AI agents…');
    setUploadProgress(0);

    const fd = new FormData();
    fd.append('file', file);

    try {
      const { data } = await api.post('/api/v1/parse', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          setUploadProgress(Math.round((e.loaded * 100) / e.total));
        },
      });

      const candidate = {
        ...data.data,
        candidate_id: data.candidate_id,
      };

      setCandidates((prev) => {
        const exists = prev.find((c) => c.candidate_id === data.candidate_id);
        return exists ? prev : [candidate, ...prev];
      });
      setParsedCandidate(candidate);
      setUploadFile(null);
      setUploadProgress(0);
      addToast(`Parsed "${candidate.name || file.name}" successfully!`, 'success');
    } catch (err) {
      addToast(err.response?.data?.detail || err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleFileDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) { setUploadFile(file); handleUpload(file); }
  };

  // ── Match ─────────────────────────────────────────────────────────────────────
  const handleMatch = async () => {
    if (!selCandidate || !selJob) {
      addToast('Select both a candidate and a job first.', 'error');
      return;
    }
    setLoading(true);
    setLoadingMsg('Running semantic skill matching…');
    try {
      const { data } = await api.post('/api/v1/match/job', {
        candidate_id: selCandidate,
        job_id: selJob,
      });
      setMatchResult(data.match_result);
      addToast('Matching complete!', 'success');
    } catch (err) {
      addToast(err.response?.data?.detail || err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div className="app">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      {/* Header */}
      <header className="app-header">
        <div className="app-header__inner">
          <div className="app-header__brand">
            <div className="brand-icon">
              <svg viewBox="0 0 32 32" fill="none">
                <rect width="32" height="32" rx="8" fill="currentColor" className="brand-icon__bg" />
                <path d="M8 24L14 10L20 18L24 14" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                <circle cx="24" cy="14" r="2.5" fill="white" />
              </svg>
            </div>
            <div>
              <h1 className="app-header__title">ResumeIQ</h1>
              <p className="app-header__sub">Multi-Agent Hiring Intelligence</p>
            </div>
          </div>

          <nav className="app-nav">
            {[
              { id: 'jobs', label: 'Post a Job' },
              { id: 'resume', label: 'Parse Resume' },
              { id: 'match', label: 'Match' },
            ].map(({ id, label }) => (
              <button
                key={id}
                className={`nav-btn${tab === id ? ' nav-btn--active' : ''}`}
                onClick={() => setTab(id)}
              >
                {label}
                {id === 'resume' && candidates.length > 0 && (
                  <span className="nav-badge">{candidates.length}</span>
                )}
                {id === 'jobs' && jobs.length > 0 && (
                  <span className="nav-badge">{jobs.length}</span>
                )}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="app-main">

        {/* ── JOBS TAB ───────────────────────────────────────────────────────── */}
        {tab === 'jobs' && (
          <div className="tab-view">
            <div className="tab-view__split">
              {/* Form panel */}
              <div className="panel">
                <div className="panel__head">
                  <h2 className="panel__title">Create Job Posting</h2>
                  <p className="panel__sub">AI will extract and normalize required skills from your description.</p>
                </div>

                <div className="field">
                  <label className="field__label">Job Title <span className="field__opt">(optional)</span></label>
                  <input
                    className="field__input"
                    type="text"
                    placeholder="e.g. Senior Backend Engineer"
                    value={jobTitle}
                    onChange={(e) => setJobTitle(e.target.value)}
                  />
                </div>

                <div className="field">
                  <label className="field__label">Job Description <span className="field__req">*</span></label>
                  <textarea
                    className="field__textarea"
                    rows={8}
                    placeholder="Paste or type the full job description here…"
                    value={jobDesc}
                    onChange={(e) => setJobDesc(e.target.value)}
                  />
                  <p className="field__hint">{jobDesc.length} / 4000 chars</p>
                </div>

                <div className="field">
                  <label className="field__label">Supplementary Skills <span className="field__opt">(optional)</span></label>
                  <input
                    className="field__input"
                    type="text"
                    placeholder="Python, Docker, PostgreSQL  (comma-separated)"
                    value={adminSkills}
                    onChange={(e) => setAdminSkills(e.target.value)}
                  />
                  <p className="field__hint">Added directly to required skills — useful if the JD is sparse.</p>
                </div>

                <button
                  className="btn btn--primary btn--full"
                  onClick={handleCreateJob}
                  disabled={loading || jobDesc.trim().length < 10}
                >
                  {loading ? <span className="btn__spinner" /> : null}
                  {loading ? 'Processing…' : 'Create Job Posting'}
                </button>
              </div>

              {/* Result / job list panel */}
              <div className="panel">
                {createdJob ? (
                  <>
                    <div className="panel__head">
                      <h2 className="panel__title">Job Created</h2>
                      <span className="badge badge--success">Live</span>
                    </div>

                    <div className="info-block">
                      <p className="info-block__role">{createdJob.title}</p>
                      {createdJob.role_summary && (
                        <p className="info-block__summary">{createdJob.role_summary}</p>
                      )}
                      <p className="info-block__id">ID: {createdJob.job_id}</p>
                    </div>

                    {createdJob.required_skills?.length > 0 && (
                      <div className="skills-section">
                        <p className="skills-section__label">Required Skills ({createdJob.required_skills.length})</p>
                        <div className="skills-wrap">
                          {createdJob.required_skills.map((s) => (
                            <SkillTag key={s} label={s} variant="required" />
                          ))}
                        </div>
                      </div>
                    )}

                    {createdJob.nice_to_have_skills?.length > 0 && (
                      <div className="skills-section">
                        <p className="skills-section__label">Nice to Have ({createdJob.nice_to_have_skills.length})</p>
                        <div className="skills-wrap">
                          {createdJob.nice_to_have_skills.map((s) => (
                            <SkillTag key={s} label={s} variant="optional" />
                          ))}
                        </div>
                      </div>
                    )}

                    {createdJob.unknown_skills?.length > 0 && (
                      <div className="skills-section">
                        <p className="skills-section__label">Unrecognized Skills</p>
                        <div className="skills-wrap">
                          {createdJob.unknown_skills.map((s) => (
                            <SkillTag key={s} label={s} variant="unknown" />
                          ))}
                        </div>
                      </div>
                    )}

                    {createdJob.skill_categories && Object.keys(createdJob.skill_categories).length > 0 && (
                      <div className="category-grid">
                        {Object.entries(createdJob.skill_categories).map(([cat, skills]) => (
                          <div key={cat} className="category-card">
                            <p className="category-card__name">{cat}</p>
                            <p className="category-card__count">{skills.length} skill{skills.length !== 1 ? 's' : ''}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <div className="empty-state">
                    <div className="empty-state__icon">
                      <svg viewBox="0 0 48 48" fill="none">
                        <rect x="8" y="6" width="32" height="36" rx="4" stroke="currentColor" strokeWidth="2" />
                        <line x1="16" y1="16" x2="32" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                        <line x1="16" y1="22" x2="32" y2="22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                        <line x1="16" y1="28" x2="24" y2="28" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                    </div>
                    <p className="empty-state__title">No job created yet</p>
                    <p className="empty-state__sub">Fill in the form and click "Create Job Posting"</p>
                  </div>
                )}

                {/* All jobs list */}
                {jobs.length > 1 && (
                  <div className="jobs-list">
                    <p className="jobs-list__heading">All Postings ({jobs.length})</p>
                    {jobs.map((j) => (
                      <div key={j.job_id} className="job-row">
                        <div className="job-row__info">
                          <span className="job-row__title">{j.title}</span>
                          <span className="job-row__meta">
                            {j.required_skills?.length || 0} required skills ·{' '}
                            {new Date(j.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        <span className="badge badge--subtle">{j.job_id.slice(0, 8)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── RESUME TAB ─────────────────────────────────────────────────────── */}
        {tab === 'resume' && (
          <div className="tab-view">
            <div className="tab-view__split">
              {/* Upload panel */}
              <div className="panel">
                <div className="panel__head">
                  <h2 className="panel__title">Upload Resume</h2>
                  <p className="panel__sub">PDF, DOCX, or TXT — multi-column layouts supported.</p>
                </div>

                <div
                  className={`dropzone${dragOver ? ' dropzone--over' : ''}`}
                  onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                  onDragLeave={() => setDragOver(false)}
                  onDrop={handleFileDrop}
                  onClick={() => document.getElementById('resume-input').click()}
                >
                  <input
                    id="resume-input"
                    type="file"
                    accept=".pdf,.docx,.txt"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const f = e.target.files[0];
                      if (f) { setUploadFile(f); handleUpload(f); }
                      e.target.value = '';
                    }}
                  />
                  <div className="dropzone__icon">
                    <svg viewBox="0 0 48 48" fill="none">
                      <path d="M24 32V16M24 16l-6 6M24 16l6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      <path d="M8 36c0 2.2 1.8 4 4 4h24c2.2 0 4-1.8 4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                    </svg>
                  </div>
                  {uploadFile ? (
                    <p className="dropzone__filename">{uploadFile.name}</p>
                  ) : (
                    <>
                      <p className="dropzone__label">Drop a file here, or click to browse</p>
                      <p className="dropzone__hint">PDF · DOCX · TXT</p>
                    </>
                  )}
                </div>

                {uploadProgress > 0 && uploadProgress < 100 && (
                  <div className="progress">
                    <div className="progress__bar" style={{ width: `${uploadProgress}%` }} />
                    <span className="progress__pct">{uploadProgress}%</span>
                  </div>
                )}

                {loading && (
                  <p className="loading-msg">
                    <span className="btn__spinner" style={{ display: 'inline-block', marginRight: 8 }} />
                    {loadingMsg}
                  </p>
                )}
              </div>

              {/* Parsed candidate panel */}
              <div className="panel">
                {parsedCandidate ? (
                  <>
                    <div className="panel__head">
                      <h2 className="panel__title">Parsed Profile</h2>
                      <span className="badge badge--success">Done</span>
                    </div>

                    <div className="candidate-hero">
                      <div className="candidate-avatar">
                        {(parsedCandidate.name || '?').charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="candidate-hero__name">{parsedCandidate.name || 'Unknown'}</p>
                        <p className="candidate-hero__meta">
                          {parsedCandidate.email && <span>{parsedCandidate.email}</span>}
                          {parsedCandidate.location && <span>{parsedCandidate.location}</span>}
                          <span>{parsedCandidate.years_of_experience || 0} yrs exp.</span>
                        </p>
                      </div>
                    </div>

                    {parsedCandidate.summary && (
                      <p className="candidate-summary">{parsedCandidate.summary}</p>
                    )}

                    {parsedCandidate.skills?.length > 0 && (
                      <div className="skills-section">
                        <p className="skills-section__label">Skills ({parsedCandidate.skills.length})</p>
                        <div className="skills-wrap">
                          {parsedCandidate.skills.map((s) => (
                            <SkillTag key={s} label={s} variant="neutral" />
                          ))}
                        </div>
                      </div>
                    )}

                    {parsedCandidate.experience?.length > 0 && (
                      <div className="timeline">
                        <p className="skills-section__label">Experience</p>
                        {parsedCandidate.experience.map((exp, i) => (
                          <div key={i} className="timeline-item">
                            <div className="timeline-item__dot" />
                            <div>
                              <p className="timeline-item__role">{exp.role}</p>
                              <p className="timeline-item__co">{exp.company} · {exp.duration}</p>
                              {exp.responsibilities?.length > 0 && (
                                <ul className="timeline-item__resp">
                                  {exp.responsibilities.slice(0, 3).map((r, j) => (
                                    <li key={j}>{r}</li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {parsedCandidate.education?.length > 0 && (
                      <div className="timeline">
                        <p className="skills-section__label">Education</p>
                        {parsedCandidate.education.map((ed, i) => (
                          <div key={i} className="timeline-item">
                            <div className="timeline-item__dot timeline-item__dot--edu" />
                            <div>
                              <p className="timeline-item__role">{ed.degree} in {ed.field}</p>
                              <p className="timeline-item__co">{ed.institution} · {ed.year}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    <p className="candidate-id">Candidate ID: {parsedCandidate.candidate_id}</p>
                  </>
                ) : (
                  <div className="empty-state">
                    <div className="empty-state__icon">
                      <svg viewBox="0 0 48 48" fill="none">
                        <circle cx="24" cy="18" r="8" stroke="currentColor" strokeWidth="2" />
                        <path d="M8 40c0-8.8 7.2-16 16-16s16 7.2 16 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                    </div>
                    <p className="empty-state__title">No resume parsed yet</p>
                    <p className="empty-state__sub">Upload a file to see the extracted profile here</p>
                  </div>
                )}
              </div>
            </div>

            {/* Candidates library */}
            {candidates.length > 0 && (
              <div className="panel panel--wide">
                <p className="panel__title" style={{ marginBottom: '1rem' }}>
                  Candidate Library ({candidates.length})
                </p>
                <div className="candidates-grid">
                  {candidates.map((c) => (
                    <div key={c.candidate_id} className="cand-card">
                      <div className="cand-card__avatar">
                        {(c.name || '?').charAt(0).toUpperCase()}
                      </div>
                      <div className="cand-card__info">
                        <p className="cand-card__name">{c.name || 'Unknown'}</p>
                        <p className="cand-card__meta">{c.years_of_experience || 0} yrs · {c.skills?.length || 0} skills</p>
                        <div className="skills-wrap" style={{ marginTop: 6 }}>
                          {(c.skills || []).slice(0, 4).map((s) => (
                            <SkillTag key={s} label={s} variant="neutral" />
                          ))}
                          {(c.skills?.length || 0) > 4 && (
                            <span className="skill-tag skill-tag--more">+{c.skills.length - 4}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── MATCH TAB ──────────────────────────────────────────────────────── */}
        {tab === 'match' && (
          <div className="tab-view">
            <div className="tab-view__split">
              {/* Selectors */}
              <div className="panel">
                <div className="panel__head">
                  <h2 className="panel__title">Match Candidate to Job</h2>
                  <p className="panel__sub">Semantic skill matching + LLM gap analysis.</p>
                </div>

                {candidates.length === 0 && (
                  <div className="callout callout--warn">
                    No candidates yet. Parse a resume first in the Resume tab.
                  </div>
                )}
                {jobs.length === 0 && (
                  <div className="callout callout--warn">
                    No jobs yet. Create a job posting in the Post a Job tab.
                  </div>
                )}

                <div className="field">
                  <label className="field__label">Select Candidate</label>
                  <select
                    className="field__select"
                    value={selCandidate}
                    onChange={(e) => setSelCandidate(e.target.value)}
                    disabled={candidates.length === 0}
                  >
                    <option value="">Choose a candidate…</option>
                    {candidates.map((c) => (
                      <option key={c.candidate_id} value={c.candidate_id}>
                        {c.name || 'Unknown'} — {c.years_of_experience || 0} yrs · {c.skills?.length || 0} skills
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label className="field__label">Select Job</label>
                  <select
                    className="field__select"
                    value={selJob}
                    onChange={(e) => setSelJob(e.target.value)}
                    disabled={jobs.length === 0}
                  >
                    <option value="">Choose a job…</option>
                    {jobs.map((j) => (
                      <option key={j.job_id} value={j.job_id}>
                        {j.title} — {j.required_skills?.length || 0} required skills
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  className="btn btn--primary btn--full"
                  onClick={handleMatch}
                  disabled={loading || !selCandidate || !selJob}
                >
                  {loading ? <span className="btn__spinner" /> : null}
                  {loading ? 'Matching…' : 'Run Match'}
                </button>

                {/* Selected previews */}
                {selCandidate && (
                  <div className="preview-card">
                    {(() => {
                      const c = candidates.find((x) => x.candidate_id === selCandidate);
                      return c ? (
                        <>
                          <p className="preview-card__label">Candidate</p>
                          <p className="preview-card__value">{c.name || 'Unknown'}</p>
                          <p className="preview-card__meta">{c.years_of_experience || 0} years · {c.skills?.length || 0} skills</p>
                        </>
                      ) : null;
                    })()}
                  </div>
                )}
                {selJob && (
                  <div className="preview-card">
                    {(() => {
                      const j = jobs.find((x) => x.job_id === selJob);
                      return j ? (
                        <>
                          <p className="preview-card__label">Job</p>
                          <p className="preview-card__value">{j.title}</p>
                          <p className="preview-card__meta">{j.required_skills?.length || 0} required · {j.nice_to_have_skills?.length || 0} nice-to-have</p>
                        </>
                      ) : null;
                    })()}
                  </div>
                )}
              </div>

              {/* Match results */}
              <div className="panel">
                {matchResult ? (
                  <>
                    <div className="panel__head">
                      <h2 className="panel__title">Match Results</h2>
                      <span className="badge badge--info">AI Analysis</span>
                    </div>

                    <ScoreRing score={matchResult.match_score} />

                    <p className="verdict-text">{matchResult.verdict}</p>

                    <div className="match-grid">
                      <div className="stat-chip">
                        <span className="stat-chip__num">{Math.round(matchResult.skill_match_details?.required_skills_match || 0)}%</span>
                        <span className="stat-chip__label">Required Skills</span>
                      </div>
                      <div className="stat-chip">
                        <span className="stat-chip__num">{Math.round(matchResult.skill_match_details?.nice_to_have_match || 0)}%</span>
                        <span className="stat-chip__label">Nice to Have</span>
                      </div>
                      <div className="stat-chip">
                        <span className="stat-chip__num">{Math.round(matchResult.skill_match_details?.experience_match || 0)}%</span>
                        <span className="stat-chip__label">Experience</span>
                      </div>
                    </div>

                    <div className="result-row">
                      <p className="result-row__label">Experience</p>
                      <p className="result-row__val">{matchResult.experience_match}</p>
                    </div>

                    {matchResult.matched_skills?.length > 0 && (
                      <div className="skills-section">
                        <p className="skills-section__label">Matched Skills ({matchResult.matched_skills.length})</p>
                        <div className="skills-wrap">
                          {matchResult.matched_skills.map((s) => (
                            <SkillTag key={s} label={s} variant="matched" />
                          ))}
                        </div>
                      </div>
                    )}

                    {matchResult.missing_skills?.length > 0 && (
                      <div className="skills-section">
                        <p className="skills-section__label">Missing Skills ({matchResult.missing_skills.length})</p>
                        <div className="skills-wrap">
                          {matchResult.missing_skills.map((s) => (
                            <SkillTag key={s} label={s} variant="missing" />
                          ))}
                        </div>
                      </div>
                    )}

                    {matchResult.nice_to_have_matched?.length > 0 && (
                      <div className="skills-section">
                        <p className="skills-section__label">Nice-to-Have Matched</p>
                        <div className="skills-wrap">
                          {matchResult.nice_to_have_matched.map((s) => (
                            <SkillTag key={s} label={s} variant="optional" />
                          ))}
                        </div>
                      </div>
                    )}

                    {matchResult.recommendation && (
                      <div className="insight-card insight-card--green">
                        <p className="insight-card__label">Recommendation</p>
                        <p className="insight-card__text">{matchResult.recommendation}</p>
                      </div>
                    )}

                    {matchResult.gap_analysis && (
                      <div className="insight-card">
                        <p className="insight-card__label">Gap Analysis</p>
                        <p className="insight-card__text">{matchResult.gap_analysis}</p>
                      </div>
                    )}

                    {matchResult.upskilling_suggestions?.length > 0 && (
                      <div className="insight-card insight-card--amber">
                        <p className="insight-card__label">Upskilling Suggestions</p>
                        <ul className="insight-list">
                          {matchResult.upskilling_suggestions.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </>
                ) : (
                  <div className="empty-state">
                    <div className="empty-state__icon">
                      <svg viewBox="0 0 48 48" fill="none">
                        <circle cx="18" cy="24" r="10" stroke="currentColor" strokeWidth="2" />
                        <circle cx="30" cy="24" r="10" stroke="currentColor" strokeWidth="2" />
                      </svg>
                    </div>
                    <p className="empty-state__title">No match run yet</p>
                    <p className="empty-state__sub">Select a candidate and a job, then click "Run Match"</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Loading overlay */}
      {loading && (
        <div className="loading-overlay" aria-live="polite">
          <div className="loading-box">
            <div className="loading-spinner" />
            <p className="loading-box__msg">{loadingMsg}</p>
          </div>
        </div>
      )}
    </div>
  );
}