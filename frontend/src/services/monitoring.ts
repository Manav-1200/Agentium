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
