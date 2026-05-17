/**
 * Claude Code 配置页的类型定义
 */

export interface VSCodeAPI {
  postMessage(message: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
}

export interface ClaudeCodeConfigValues {
  apiKey: string;
  baseUrl: string;
  model: string;
  sonnetModel: string;
  opusModel: string;
  haikuModel: string;
}

export interface ClaudeCodeCliStatus {
  installed: boolean;
  version?: string;
  error?: string;
}

