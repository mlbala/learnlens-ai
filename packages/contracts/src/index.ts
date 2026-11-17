/**
 * Shared contract types placeholder.
 * Stable REST schemas land in later phases from docs/02_DATA_AND_API_CONTRACTS.md.
 * No runtime logic in phase 00.
 */

export type ProviderKind = "fake" | "openai" | "gemini" | "deepseek";

export interface ScaffoldMeta {
  phase: "00";
  operationalEndpoints: false;
}
