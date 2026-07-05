import type { StandardAccountKey } from "@/types/financial";

export type RiskSignalSeverity = "low" | "medium" | "high";

export type RiskSignal = {
  id: string;
  year: number;
  accountKey: StandardAccountKey | "company";
  title: string;
  description: string;
  severity: RiskSignalSeverity;
};

export type AuditRiskMapping = {
  accountName: string;
  risk: string;
  assertions: string[];
  procedures: string[];
};
