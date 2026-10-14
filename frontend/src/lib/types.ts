export type Id = string;
export interface Owned { id: Id; created_at: string; }
export interface User { id: Id; email: string; created_at: string; }
export interface Profile extends Owned { name: string; email: string; phone: string; location: string; target_roles: string[]; target_locations: string[]; summary: string; preferences: Record<string, unknown>; }
export interface Fact extends Owned { kind: 'education' | 'experience' | 'project' | 'skill' | 'interest' | 'achievement'; title: string; content: string; source_text: string; tags: string[]; confirmed: boolean; confirmed_at: string | null; revision_number: number; lineage_id: Id; supersedes_id: Id | null; document_id: Id | null; details: Record<string, unknown>; }
export interface DocumentRecord extends Owned { filename: string; status: string; parsed_text: string; error: string | null; size_bytes: number; }
export interface Source extends Owned { name: string; kind: string; url: string; capability: string; notes: string; last_synced_at: string | null; new_jobs_count: number; sync_task_id: Id | null; archived: boolean; }
export interface Job extends Owned { company: string; title: string; location: string; industry: string; jd_text: string; jd_complete: boolean; requirements: unknown[]; salary_text: string; source_id: Id | null; source_url: string; published_at: string | null; deadline: string | null; status: 'active' | 'closed' | 'archived'; version_number: number; }
export interface Claim { text: string; fact_ids: Id[]; }
export interface ResumeSection { heading: string; fact_ids: Id[]; bullets: Claim[]; }
export interface ResumeContent { basics: { name: string; email: string; phone: string; location: string }; summary: Claim; education: ResumeSection[]; experience: ResumeSection[]; skills: Claim[]; interests: Claim[]; }
export interface Resume extends Owned { name: string; language: 'zh' | 'en'; style: string; template: string; }
export interface ResumeVersion extends Owned { resume_id: Id; version_number: number; parent_version_id: Id | null; job_id: Id | null; job_version_id: Id | null; language: 'zh' | 'en'; style: string; template: string; content: ResumeContent; evidence_status: 'pending' | 'validated' | 'rejected'; approved_at: string | null; approval_source: string; export_status: string; export_path: string | null; facts_snapshot: unknown[]; }
export type ApplicationStatus = 'pending' | 'applied' | 'hr_chat' | 'interview_1' | 'interview_2' | 'offer' | 'rejected' | 'withdrawn';
export interface Application extends Owned { job_id: Id; resume_version_id: Id | null; status: ApplicationStatus; applied_at: string | null; hr_name: string; hr_contact: string; notes: string; version: number; attempt_no: number; company?: string; job_title?: string; }
export interface ApplicationEvent extends Owned { from_status: ApplicationStatus | null; to_status: ApplicationStatus; notes: string; occurred_at: string; sequence: number; }
export interface Task extends Owned { kind: string; status: 'queued' | 'running' | 'retry' | 'succeeded' | 'failed' | 'cancelled'; input_json: Record<string, unknown>; output_json: Record<string, unknown>; error: string | null; attempts: number; finished_at: string | null; }
export interface Policy extends Owned { name: string; enabled: boolean; daily_target: number; max_attempts_per_day: number; auto_submit: boolean; auto_approve_grounded: boolean; schedule_time: string; timezone: string; filters_json: Record<string, unknown>; channels_json: string[]; last_run_at: string | null; }
export interface Batch extends Owned { policy_id: Id; run_date: string; status: 'queued' | 'running' | 'paused' | 'completed' | 'failed'; target_count: number; prepared_count: number; attempted_count: number; confirmed_count: number; error: string | null; }
export interface BatchItem extends Owned { batch_id: Id; job_id: Id; resume_version_id: Id | null; status: string; channel: string; capability: string; prepared_at: string | null; attempted_at: string | null; confirmed_at: string | null; artifact_path: string | null; receipt_json: Record<string, unknown>; error: string | null; }
export interface ChatMessage { role: 'user' | 'assistant'; content: string; }
