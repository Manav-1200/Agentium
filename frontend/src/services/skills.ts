import { api } from './api';

export interface Skill {
  skill_id: string;
  skill_name: string;
  display_name: string;
  skill_type: string;
  domain: string;
  tags: string[];
  complexity: string;
  description: string;
  success_rate: number;
  usage_count: number;
  verification_status: string;
  creator_id: string;
  // Optional extended fields
  prerequisites?: string[];
  steps?: string[];
  code_template?: string;
  examples?: { input: string; output: string }[];
  common_pitfalls?: string[];
  validation_criteria?: string[];
  created_at?: string;
}

export interface SkillSearchResult {
  skill_id: string;
  relevance_score: number;
  metadata: Skill;
  content_preview: string;
}

export const skillsApi = {
  // Search skills
  search: async (query: string, filters?: Record<string, string>): Promise<SkillSearchResult[]> => {
    const params = new URLSearchParams({ query, ...filters });
    const response = await api.get(`/api/v1/skills/search?${params}`);
    return response.data.results;
  },

  // Update skill
  update: async (skillId: string, updates: Partial<Skill>): Promise<Skill> => {
    const response = await api.post(`/api/v1/skills/${skillId}/update`, updates);
    return response.data;
  },

  // Deprecate (delete) skill
  deprecate: async (skillId: string, reason: string): Promise<void> => {
    await api.post(`/api/v1/skills/${skillId}/deprecate`, { reason });
  },

  // Get skill details with full content (includes content_preview / raw content)
  getFull: async (skillId: string): Promise<Skill> => {
    const response = await api.get(`/api/v1/skills/${skillId}/full`);
    return response.data;
  },

  // Get skill details
  get: async (skillId: string): Promise<Skill> => {
    const response = await api.get(`/api/v1/skills/${skillId}`);
    return response.data;
  },

  // Create skill (Lead/Council/Head only)
  create: async (skillData: Partial<Skill>, autoVerify = false): Promise<{ skill_id: string }> => {
    const response = await api.post(`/api/v1/skills/?auto_verify=${autoVerify}`, skillData);
    return response.data;
  },

  // Execute with skill
  execute: async (skillId: string, taskInput: string): Promise<{
    content: string;
    skills_used: string[];
  }> => {
    const response = await api.post(`/api/v1/skills/${skillId}/execute`, { task_input: taskInput });
    return response.data;
  },

  // Get pending submissions (Council/Head)
  getPendingSubmissions: async (): Promise<unknown> => {
    const response = await api.get('/api/v1/skills/submissions/pending');
    return response.data;
  },

  // Review submission (Council/Head)
  reviewSubmission: async (submissionId: string, decision: 'approve' | 'reject', notes?: string): Promise<unknown> => {
    const response = await api.post(`/api/v1/skills/submissions/${submissionId}/review`, {
      decision,
      notes
    });
    return response.data;
  },

  // Get popular skills
  getPopular: async (domain?: string, limit = 10): Promise<Skill[]> => {
    const params = new URLSearchParams();
    if (domain) params.append('domain', domain);
    params.append('limit', limit.toString());
    const response = await api.get(`/api/v1/skills/stats/popular?${params}`);
    return response.data.skills;
  }
};