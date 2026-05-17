/**
 * Claude Code 配置页 Webview Provider
 *
 * 读写 ~/.claude/settings.json 的 env 字段，管理 API Key、Base URL 和模型映射。
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import * as os from 'os';
import * as cp from 'child_process';
import type { ClaudeCodeConfigValues, ClaudeCodeCliStatus } from './webview/claudeCodeConfig/types';

const SETTINGS_DIR = path.join(os.homedir(), '.claude');
const SETTINGS_PATH = path.join(SETTINGS_DIR, 'settings.json');

const ENV_KEY_MAP: Record<keyof ClaudeCodeConfigValues, string> = {
  apiKey: 'ANTHROPIC_API_KEY',
  baseUrl: 'ANTHROPIC_BASE_URL',
  model: 'ANTHROPIC_MODEL',
  sonnetModel: 'ANTHROPIC_DEFAULT_SONNET_MODEL',
  opusModel: 'ANTHROPIC_DEFAULT_OPUS_MODEL',
  haikuModel: 'ANTHROPIC_DEFAULT_HAIKU_MODEL',
};

export class ClaudeCodeConfigProvider {
  public static currentPanel: ClaudeCodeConfigProvider | undefined;
  private static readonly viewType = 'aiSocialScientistClaudeCodeConfig';

  private readonly _panel: vscode.WebviewPanel;
  private readonly _extensionPath: string;
  private _disposables: vscode.Disposable[] = [];

  public static createOrShow(
    context: vscode.ExtensionContext,
    viewColumn: vscode.ViewColumn = vscode.ViewColumn.One
  ): void {
    if (ClaudeCodeConfigProvider.currentPanel) {
      ClaudeCodeConfigProvider.currentPanel._panel.reveal(viewColumn);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      ClaudeCodeConfigProvider.viewType,
      'Claude Code 配置',
      viewColumn,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(context.extensionPath, 'out', 'webview'))
        ]
      }
    );

    ClaudeCodeConfigProvider.currentPanel = new ClaudeCodeConfigProvider(panel, context);
  }

  private constructor(panel: vscode.WebviewPanel, context: vscode.ExtensionContext) {
    this._panel = panel;
    this._extensionPath = context.extensionPath;

    this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      async (message: { command: string; config?: ClaudeCodeConfigValues }) => {
        switch (message.command) {
          case 'requestConfig':
            await this._sendInitialConfig();
            break;
          case 'saveConfig':
            await this._handleSaveConfig(message.config!);
            break;
        }
      },
      null,
      this._disposables
    );
  }

  private _readSettingsFile(): Record<string, any> {
    try {
      if (!fs.existsSync(SETTINGS_PATH)) {
        return {};
      }
      const raw = fs.readFileSync(SETTINGS_PATH, 'utf-8');
      return JSON.parse(raw);
    } catch {
      return {};
    }
  }

  private _extractConfig(settings: Record<string, any>): ClaudeCodeConfigValues {
    const env = settings.env || {};
    return {
      apiKey: env[ENV_KEY_MAP.apiKey] || '',
      baseUrl: env[ENV_KEY_MAP.baseUrl] || 'https://api.anthropic.com',
      model: env[ENV_KEY_MAP.model] || '',
      sonnetModel: env[ENV_KEY_MAP.sonnetModel] || '',
      opusModel: env[ENV_KEY_MAP.opusModel] || '',
      haikuModel: env[ENV_KEY_MAP.haikuModel] || '',
    };
  }

  private _writeSettingsFile(config: ClaudeCodeConfigValues): void {
    const existing = this._readSettingsFile();
    const env = { ...(existing.env || {}) };

    env[ENV_KEY_MAP.apiKey] = config.apiKey.trim();
    env[ENV_KEY_MAP.baseUrl] = config.baseUrl.trim();

    (['model', 'sonnetModel', 'opusModel', 'haikuModel'] as const).forEach(key => {
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

    if (!fs.existsSync(SETTINGS_DIR)) {
      fs.mkdirSync(SETTINGS_DIR, { recursive: true });
    }

    const json = JSON.stringify(updated, null, 2);
    if (process.platform === 'win32') {
      fs.writeFileSync(SETTINGS_PATH, json, 'utf-8');
    } else {
      const tmpPath = SETTINGS_PATH + '.tmp';
      fs.writeFileSync(tmpPath, json, 'utf-8');
      try { fs.chmodSync(tmpPath, 0o600); } catch { /* ignore */ }
      fs.renameSync(tmpPath, SETTINGS_PATH);
    }
  }

  private _detectCli(): Promise<ClaudeCodeCliStatus> {
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
        const version = stdout.trim();
        resolve({ installed: true, version });
      });
    });
  }

  private async _sendInitialConfig(): Promise<void> {
    const settings = this._readSettingsFile();
    const config = this._extractConfig(settings);
    const cliStatus = await this._detectCli();

    this._panel.webview.postMessage({
      command: 'initialConfig',
      config,
      settingsPath: SETTINGS_PATH,
    });

    this._panel.webview.postMessage({
      command: 'cliStatus',
      status: cliStatus,
    });
  }

  private async _handleSaveConfig(config: ClaudeCodeConfigValues): Promise<void> {
    try {
      this._writeSettingsFile(config);
      this._panel.webview.postMessage({ command: 'saveResult', success: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this._panel.webview.postMessage({ command: 'saveResult', success: false, error: message });
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.file(path.join(this._extensionPath, 'out', 'webview', 'claudeCodeConfig.js'))
    );

    const nonce = Array.from({ length: 32 }, () => Math.random().toString(36)[2]).join('');
    const csp = [
      "default-src 'none'",
      `img-src ${webview.cspSource} data:`,
      `style-src ${webview.cspSource} 'unsafe-inline'`,
      `script-src ${webview.cspSource} 'nonce-${nonce}'`,
      `connect-src ${webview.cspSource} http://127.0.0.1:* http://localhost:*`,
    ].join('; ');

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy" content="${csp}">
  <title>Claude Code 配置</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--vscode-font-family, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif);
      background: var(--vscode-editor-background);
      color: var(--vscode-editor-foreground);
      height: 100vh;
      overflow: auto;
    }
    #root { min-height: 100vh; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }

  public dispose(): void {
    ClaudeCodeConfigProvider.currentPanel = undefined;
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) { d.dispose(); }
    }
  }
}
