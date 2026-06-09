/**
 * 配置页 Webview 的类型定义
 */

export interface VSCodeAPI {
  postMessage(message: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
}

export interface ConfigValues {
  // 必填
  llmApiKey: string;
  // 后端服务
  backendHost: string;
  backendPort: number;
  pythonPath: string;
  // LLM 默认配置
  llmApiBase: string;
  llmModel: string;
  // 可选
  backendLogLevel: string;
  coderLlmApiKey: string;
  coderLlmApiBase: string;
  coderLlmModel: string;
  nanoLlmApiKey: string;
  nanoLlmApiBase: string;
  nanoLlmModel: string;
  // Analysis LLM (for data analysis, insight generation, and report writing)
  analysisLlmApiKey: string;
  analysisLlmApiBase: string;
  analysisLlmModel: string;
  // Embedding
  embeddingApiKey: string;
  embeddingApiBase: string;
  embeddingModel: string;
  embeddingDims: number;
  // Literature Search (optional, for search_literature tool)
  literatureSearchMcpUrl: string;
  literatureSearchApiKey: string;
}

export interface ValidationState {
  validating: boolean;
  valid: boolean | null;
  error: string | null;
}

export interface WorkspaceInfo {
  hasWorkspace: boolean;
  workspacePath?: string;
  /** Relative path to the loaded .env file, e.g. agentsociety/.env */
  envFilePath?: string;
}

export interface BackendStatus {
  isRunning: boolean;
  port?: number;
  url?: string;
}

export interface ImportedModelOptions {
  openaiCompatible: string[];
  claudeCode: string[];
  embedding: string[];
}

export interface ImportedModelDefaults {
  simulation: string;
  coder: string;
  analysis: string;
  nano: string;
  embedding: string;
  claudeCode: string;
  claudeCodeSonnet: string;
  claudeCodeOpus: string;
  claudeCodeHaiku: string;
  easyPaperVlm: string;
}

export interface OverviewStatusMessage {
  backendStatus: BackendStatus;
  claudeCodeCustomized?: boolean;
}

// ============ EasyPaper 配置 ============

export interface EasyPaperConfigValues {
  llmModelName: string;
  llmApiKey: string;
  llmBaseUrl: string;
  vlmEnabled: boolean;
  vlmModel: string;
  vlmApiKey: string;
  vlmBaseUrl: string;
}
