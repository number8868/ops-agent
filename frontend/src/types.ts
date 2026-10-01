export type HealthStatus = "normal" | "warning" | "critical" | "unknown";

export interface LocalMetric {
  label: string;
  value: string;
  status: HealthStatus;
  detail: string;
}

export interface InspectionFinding {
  title: string;
  severity: HealthStatus;
  evidence: string;
  recommendation: string;
  nodeId?: string;
}

export interface ClusterNode {
  id: string;
  type: "local" | "ssh" | string;
  role: string;
  host?: string;
  status: HealthStatus;
  metrics: {
    hostname?: string;
    uptime?: string;
    cpuLoadPercent?: number;
    memoryUsedMb?: number;
    memoryTotalMb?: number;
    memoryAvailableMb?: number;
    memoryUsagePercent?: number;
    diskUsedGb?: number;
    diskTotalGb?: number;
    diskUsagePercent?: number;
    gpus?: Array<{
      index: number;
      name: string;
      memoryUsedMb: number;
      memoryTotalMb: number;
      utilization: number;
      temperature: number;
    }>;
  };
  findings: InspectionFinding[];
}

export interface DashboardStatus {
  timestamp: string | null;
  mode?: "local" | "cluster" | string;
  overallStatus: HealthStatus;
  metrics?: LocalMetric[];
  nodes?: ClusterNode[];
  findings: InspectionFinding[];
}

export interface ChatMessage {
  role: "user" | "agent";
  content: string;
  pending?: boolean;
  error?: boolean;
}

export interface ExtensionNode {
  id: string;
  role: string;
  status: HealthStatus;
  note: string;
}
