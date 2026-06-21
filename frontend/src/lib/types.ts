export type Role = "doctor" | "nurse" | "billing_executive" | "technician" | "admin";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  role: Role;
  username: string;
}

export interface SourceCitation {
  source_document: string;
  section_title: string;
  collection: string;
}

export interface ChatResponse {
  answer: string;
  sources: SourceCitation[];
  retrieval_type: "hybrid_rag" | "sql_rag";
  role: Role;
}

export interface Message {
  id: string;
  type: "user" | "bot";
  text: string;
  sources?: SourceCitation[];
  retrieval_type?: "hybrid_rag" | "sql_rag";
  timestamp: Date;
}

export interface AuthState {
  token: string;
  role: Role;
  username: string;
}

export const ROLE_META: Record<Role, { label: string; color: string; bg: string; collections: string[] }> = {
  doctor:            { label: "Doctor",            color: "text-blue-700",   bg: "bg-blue-100",   collections: ["general", "clinical", "nursing"] },
  nurse:             { label: "Nurse",             color: "text-green-700",  bg: "bg-green-100",  collections: ["general", "nursing"] },
  billing_executive: { label: "Billing Executive", color: "text-purple-700", bg: "bg-purple-100", collections: ["general", "billing"] },
  technician:        { label: "Technician",        color: "text-orange-700", bg: "bg-orange-100", collections: ["general", "equipment"] },
  admin:             { label: "Admin",             color: "text-red-700",    bg: "bg-red-100",    collections: ["general", "clinical", "nursing", "billing", "equipment"] },
};
