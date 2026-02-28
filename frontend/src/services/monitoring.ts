import { api } from "./api";
import { MonitoringDashboard, ViolationReport } from "../types";

export const monitoringService = {
  getDashboard: async (monitorId: string): Promise<MonitoringDashboard> => {
    const response = await api.get<MonitoringDashboard>(
      `/api/v1/monitoring/dashboard/${monitorId}`,
    );
    return response.data;
  },

  getAgentHealth: async (agentId: string): Promise<any> => {
    const response = await api.get(
      `/api/v1/monitoring/agents/${agentId}/health`,
    );
    return response.data;
  },

  /**
   * Fetch violations with optional filters.
   * Maps to GET /api/v1/monitoring/violations
   */
  getViolations: async (filters?: {
    status?: string;
    severity?: string;
    agentId?: string;
    days?: number;
    limit?: number;
  }): Promise<ViolationReport[]> => {
    const params = new URLSearchParams();
    if (filters?.status)   params.append("status",   filters.status);
    if (filters?.severity) params.append("severity", filters.severity);
    if (filters?.agentId)  params.append("agent_id", filters.agentId);
    if (filters?.days)     params.append("days",     String(filters.days));
    if (filters?.limit)    params.append("limit",    String(filters.limit));

    const query = params.toString() ? `?${params.toString()}` : "";
    const response = await api.get<{ violations: ViolationReport[] }>(
      `/api/v1/monitoring/violations${query}`,
    );
    return response.data.violations;
  },

  /**
   * Mark a violation as resolved with resolution notes.
   * Maps to PATCH /api/v1/monitoring/violations/{id}/resolve
   */
  resolveViolation: async (
    violationId: string,
    resolutionNotes: string,
  ): Promise<void> => {
    const params = new URLSearchParams();
    params.append("resolution_notes", resolutionNotes);

    await api.patch(
      `/api/v1/monitoring/violations/${violationId}/resolve?${params.toString()}`,
    );
  },

  reportViolation: async (data: {
    reporterId: string;
    violatorId: string;
    severity: string;
    violationType: string;
    description: string;
  }): Promise<ViolationReport> => {
    const params = new URLSearchParams();
    params.append("reporter_id", data.reporterId);
    params.append("violator_id", data.violatorId);
    params.append("severity", data.severity);
    params.append("violation_type", data.violationType);
    params.append("description", data.description);

    const response = await api.post<{ report: ViolationReport }>(
      `/api/v1/monitoring/report-violation?${params.toString()}`,
    );
    return response.data.report;
  },
};