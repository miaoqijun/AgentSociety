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
