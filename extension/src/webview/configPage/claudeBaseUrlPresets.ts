export interface ClaudeBaseUrlPreset {
  id: string;
  url: string;
}

export const CLAUDE_BASE_URL_PRESETS: ClaudeBaseUrlPreset[] = [
  { id: 'anthropic', url: 'https://api.anthropic.com' },
  { id: 'bigmodel', url: 'https://open.bigmodel.cn/api/anthropic' },
  { id: 'kimi', url: 'https://api.kimi.com/coding/' },
  { id: 'minimax', url: 'https://api.minimaxi.com/anthropic' },
  { id: 'openrouter', url: 'https://openrouter.ai/api' },
];

export const DEFAULT_CLAUDE_BASE_URL = CLAUDE_BASE_URL_PRESETS[0].url;
