import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';
import * as cp from 'child_process';
import type { ClaudeCodeCliStatus, ClaudeCodeConfigValues } from '../webview/configPage/claudeCodeTypes';
export const CLAUDE_SETTINGS_DIR = path.join(os.homedir(), '.claude');
export const CLAUDE_SETTINGS_PATH = path.join(CLAUDE_SETTINGS_DIR, 'settings.json');

type EnvMappedKeys = Exclude<keyof ClaudeCodeConfigValues, 'permissionMode'>;
const ENV_KEY_MAP: Record<EnvMappedKeys, string> = {
  apiKey: 'ANTHROPIC_AUTH_TOKEN',
  baseUrl: 'ANTHROPIC_BASE_URL',
  model: 'ANTHROPIC_MODEL',
  sonnetModel: 'ANTHROPIC_DEFAULT_SONNET_MODEL',
  opusModel: 'ANTHROPIC_DEFAULT_OPUS_MODEL',
  haikuModel: 'ANTHROPIC_DEFAULT_HAIKU_MODEL',
};

export function readClaudeSettingsFile(): Record<string, unknown> {
  try {
    if (!fs.existsSync(CLAUDE_SETTINGS_PATH)) {
      return {};
    }
    const raw = fs.readFileSync(CLAUDE_SETTINGS_PATH, 'utf-8');
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
}

export function extractClaudeConfig(settings: Record<string, unknown>): ClaudeCodeConfigValues {
  const env = (settings.env as Record<string, string> | undefined) ?? {};
  return {
    apiKey: (env[ENV_KEY_MAP.apiKey] ?? '').trim(),
    baseUrl: (env[ENV_KEY_MAP.baseUrl] ?? '').trim(),
    model: env[ENV_KEY_MAP.model] || '',
    sonnetModel: env[ENV_KEY_MAP.sonnetModel] || '',
    opusModel: env[ENV_KEY_MAP.opusModel] || '',
    haikuModel: env[ENV_KEY_MAP.haikuModel] || '',
    permissionMode: '',
  };
}

export function readClaudeConfig(): ClaudeCodeConfigValues {
  return extractClaudeConfig(readClaudeSettingsFile());
}

export function isClaudeCodeEnvCustomized(): boolean {
  try {
    const env = (readClaudeSettingsFile().env as Record<string, string> | undefined) ?? {};
    if ((env[ENV_KEY_MAP.apiKey] ?? '').trim()) {
      return true;
    }
    const base = (env.ANTHROPIC_BASE_URL ?? '').trim();
    if (base) {
      return true;
    }
    return [
      'ANTHROPIC_MODEL',
      'ANTHROPIC_DEFAULT_SONNET_MODEL',
      'ANTHROPIC_DEFAULT_OPUS_MODEL',
      'ANTHROPIC_DEFAULT_HAIKU_MODEL',
    ].some((key) => Boolean((env[key] ?? '').trim()));
  } catch {
    return false;
  }
}

export function writeClaudeConfig(config: ClaudeCodeConfigValues): void {
  const existing = readClaudeSettingsFile();
  const env = { ...((existing.env as Record<string, string> | undefined) ?? {}) };

  const token = config.apiKey.trim();
  if (token) {
    env[ENV_KEY_MAP.apiKey] = token;
  } else {
    delete env[ENV_KEY_MAP.apiKey];
  }
  delete env.ANTHROPIC_API_KEY;
  env[ENV_KEY_MAP.baseUrl] = config.baseUrl.trim();

  (['model', 'sonnetModel', 'opusModel', 'haikuModel'] as const).forEach((key) => {
    const val = (config[key] || '').trim();
    if (val) {
      env[ENV_KEY_MAP[key]] = val;
    } else {
      delete env[ENV_KEY_MAP[key]];
    }
  });

  if (!env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC) {
    env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC = '1';
  }

  const updated = { ...existing, env };

  if (!fs.existsSync(CLAUDE_SETTINGS_DIR)) {
    fs.mkdirSync(CLAUDE_SETTINGS_DIR, { recursive: true });
  }

  const json = JSON.stringify(updated, null, 2);
  if (process.platform === 'win32') {
    fs.writeFileSync(CLAUDE_SETTINGS_PATH, json, 'utf-8');
  } else {
    const tmpPath = CLAUDE_SETTINGS_PATH + '.tmp';
    fs.writeFileSync(tmpPath, json, 'utf-8');
    try {
      fs.chmodSync(tmpPath, 0o600);
    } catch {
      /* ignore */
    }
    fs.renameSync(tmpPath, CLAUDE_SETTINGS_PATH);
  }
}

export function detectClaudeCli(): Promise<ClaudeCodeCliStatus> {
  return new Promise((resolve) => {
    const timeout = setTimeout(() => {
      resolve({ installed: false, error: '检测超时' });
    }, 5000);

    cp.execFile('claude', ['--version'], (error, stdout) => {
      clearTimeout(timeout);
      if (error) {
        resolve({ installed: false, error: 'Claude Code CLI 未安装' });
        return;
      }
      resolve({ installed: true, version: stdout.trim() });
    });
  });
}
