export interface ClaudeBaseUrlPreset {
  id: string;
  url: string;
}

export const CLAUDE_BASE_URL_PRESETS: ClaudeBaseUrlPreset[] = [
  { id: 'deepseek', url: 'https://api.deepseek.com/anthropic' },
  { id: 'volcengine', url: 'https://ark.cn-beijing.volces.com/api/plan' },
  { id: 'mimo', url: 'https://token-plan-cn.xiaomimimo.com/anthropic' },
  { id: 'bigmodel', url: 'https://open.bigmodel.cn/api/anthropic' },
  { id: 'kimi', url: 'https://api.kimi.com/coding/' },
  { id: 'minimax', url: 'https://api.minimaxi.com/anthropic' },
  { id: 'openrouter', url: 'https://openrouter.ai/api' },
];

export const KNOWN_CLAUDE_BASE_URLS = new Set(
  CLAUDE_BASE_URL_PRESETS.map((preset) => preset.url),
);

/** Empty until user picks a preset or types a custom URL. */
export const DEFAULT_CLAUDE_BASE_URL = '';
