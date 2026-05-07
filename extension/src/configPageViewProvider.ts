/**
 * 配置页视图提供者 (Config Page View Provider)
 *
 * 在首次启动时或用户手动打开时显示配置页，引导用户填写 LLM API 密钥等必要配置，
 * 避免让用户去 Settings 页面编写 JSON 配置。
 *
 * **重要**: 配置现在保存在工作区的 .env 文件中，而不是 VSCode 设置中。
 *
 * 关联文件：
 * - @extension/src/extension.ts - 主入口，注册命令 'aiSocialScientist.openConfigPage'
 * - @extension/src/envManager.ts - .env文件读写管理
 * - @extension/src/services/llmValidator.ts - LLM配置验证服务
 * - @extension/src/services/backendManager.ts - 后端服务管理（配置保存后启动）
 * - @extension/src/webview/configPage/ - 前端React组件 (编译后为configPage.js)
 *
 * 后端API：
 * - @packages/agentsociety2/agentsociety2/backend/app.py - FastAPI后端
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { localize } from './i18n';
import type { ConfigValues, WorkspaceInfo } from './webview/configPage/types';
import { EnvManager } from './envManager';
import { LLMValidator, PythonValidator, LLMType } from './services/llmValidator';
import { fetchCompat } from './shared/fetchCompat';
import { requestJson } from './services/httpClient';
import { CONFIG_PAGE_API_VALIDATE_TIMEOUT_MS } from './services/validateTimeouts';

const fetch = fetchCompat as unknown as typeof globalThis.fetch;

const DEFAULT_LLM_API_BASE = 'https://api.openai.com/v1';
const DEFAULT_LLM_MODEL = 'gpt-5.4';

export class ConfigPageViewProvider {
  public static currentPanel: ConfigPageViewProvider | undefined;
  private static readonly viewType = 'aiSocialScientistConfigPage';

  private readonly _panel: vscode.WebviewPanel;
  private readonly _extensionPath: string;
  private readonly _context: vscode.ExtensionContext;
  private readonly _envManager: EnvManager;
  private _disposables: vscode.Disposable[] = [];

  public static createOrShow(
    context: vscode.ExtensionContext,
    viewColumn: vscode.ViewColumn = vscode.ViewColumn.One
  ): void {
    if (ConfigPageViewProvider.currentPanel) {
      ConfigPageViewProvider.currentPanel._panel.reveal(viewColumn);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      ConfigPageViewProvider.viewType,
      localize('configPage.title'),
      viewColumn,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [
          vscode.Uri.file(path.join(context.extensionPath, 'out', 'webview'))
        ]
      }
    );

    ConfigPageViewProvider.currentPanel = new ConfigPageViewProvider(panel, context);
  }

  private constructor(panel: vscode.WebviewPanel, context: vscode.ExtensionContext) {
    this._panel = panel;
    this._context = context;
    this._extensionPath = context.extensionPath;
    this._envManager = new EnvManager();

    this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);

    this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

    this._panel.webview.onDidReceiveMessage(
      async (message: { command: string; config?: Partial<ConfigValues>; llmType?: string; url?: string }) => {
        switch (message.command) {
          case 'requestConfig':
            await this._sendInitialConfig();
            break;
          case 'saveConfig':
            await this._handleSaveConfig(message.config || {});
            break;
          case 'startBackend':
            await this._handleStartBackend(message.config || {});
            break;
          case 'validateConfig':
            await this._handleValidateConfig(message.config || {}, message.llmType);
            break;
          case 'validatePython':
            await this._handleValidatePython(message.config || {});
            break;
          case 'validateLiteratureSearch':
            await this._handleValidateLiteratureSearch(message.config || {});
            break;
          case 'closeConfigPage':
            this._panel.dispose();
            break;
          case 'openVscodeSettings':
            await vscode.commands.executeCommand('workbench.action.openSettings', '@aiSocialScientist');
            break;
          case 'openFolder':
            await vscode.commands.executeCommand('workbench.action.files.openFolder');
            break;
          case 'openUrl':
            if (message.url) {
              await vscode.env.openExternal(vscode.Uri.parse(message.url));
            }
            break;
        }
      },
      null,
      this._disposables
    );
  }

  private async _sendInitialConfig(): Promise<void> {
    // Read from .env file instead of VSCode settings
    const envConfig = this._envManager.readEnv();
    const workspaceInfo: WorkspaceInfo = {
      hasWorkspace: !!(vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders.length > 0),
      workspacePath: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
    };

    const configValues: Partial<ConfigValues> = {
      llmApiKey: envConfig.llmApiKey || '',
      backendHost: envConfig.backendHost || '127.0.0.1',
      backendPort: envConfig.backendPort ?? 8001,
      pythonPath: envConfig.pythonPath || '',
      llmApiBase: envConfig.llmApiBase || DEFAULT_LLM_API_BASE,
      llmModel: envConfig.llmModel || DEFAULT_LLM_MODEL,
      backendLogLevel: envConfig.backendLogLevel || 'info',
      coderLlmApiKey: envConfig.coderLlmApiKey || '',
      coderLlmApiBase: envConfig.coderLlmApiBase || '',
      coderLlmModel: envConfig.coderLlmModel || '',
      nanoLlmApiKey: envConfig.nanoLlmApiKey || '',
      nanoLlmApiBase: envConfig.nanoLlmApiBase || '',
      nanoLlmModel: envConfig.nanoLlmModel || '',
      analysisLlmApiKey: envConfig.analysisLlmApiKey || '',
      analysisLlmApiBase: envConfig.analysisLlmApiBase || '',
      analysisLlmModel: envConfig.analysisLlmModel || '',
      embeddingApiKey: envConfig.embeddingApiKey || '',
      embeddingApiBase: envConfig.embeddingApiBase || '',
      embeddingModel: envConfig.embeddingModel || 'text-embedding-3-large',
      embeddingDims: envConfig.embeddingDims ?? 1024,
      webSearchApiUrl: envConfig.webSearchApiUrl || '',
      webSearchApiToken: envConfig.webSearchApiToken || '',
      miroflowDefaultLlm: envConfig.miroflowDefaultLlm || 'qwen-3',
      miroflowDefaultAgent: envConfig.miroflowDefaultAgent || 'mirothinker_v1.5_keep5_max200',
      literatureSearchApiUrl: envConfig.literatureSearchApiUrl || 'http://localhost:8008/api/search',
      literatureSearchApiKey: envConfig.literatureSearchApiKey || '',
    };

    // 获取后端状态
    const backendStatus = await this._getBackendStatus();

    this._panel.webview.postMessage({
      command: 'initialConfig',
      config: configValues
    });

    this._panel.webview.postMessage({
      command: 'workspaceInfo',
      workspaceInfo: workspaceInfo
    });

    this._panel.webview.postMessage({
      command: 'backendStatus',
      backendStatus: backendStatus
    });
  }

  /**
   * 获取后端状态信息
   */
  private async _getBackendStatus(): Promise<{ isRunning: boolean; port?: number; url?: string }> {
    try {
      const status = await vscode.commands.executeCommand<{ isRunning: boolean; port?: number }>('aiSocialScientist.getBackendStatus');
      if (status && status.isRunning && status.port) {
        return {
          isRunning: true,
          port: status.port,
          url: `http://localhost:${status.port}`
        };
      }
    } catch {
      // 命令不存在或执行失败，忽略
    }

    // 尝试从 .env 文件获取端口配置
    const envConfig = this._envManager.readEnv();
    const configuredPort = envConfig.backendPort ?? 8001;
    return {
      isRunning: false,
      port: configuredPort,
      url: `http://localhost:${configuredPort}`
    };
  }

  private async _handleSaveConfig(config: Partial<ConfigValues>): Promise<void> {
    try {
      await this._saveConfigInternal(config);
      this._panel.webview.postMessage({ command: 'saveResult', success: true });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this._panel.webview.postMessage({
        command: 'saveResult',
        success: false,
        error: message
      });
    }
  }

  private async _handleStartBackend(config: Partial<ConfigValues>): Promise<void> {
    try {
      // 确保配置已保存
      await this._saveConfigInternal(config);

      // 启动后端服务
      const success = await vscode.commands.executeCommand<boolean>('aiSocialScientist.startBackend');

      this._panel.webview.postMessage({
        command: 'startBackendResult',
        success: success !== false,
      });
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this._panel.webview.postMessage({
        command: 'startBackendResult',
        success: false,
        error: message
      });
    }
  }

  private async _saveConfigInternal(config: Partial<ConfigValues>): Promise<void> {
    // 检查是否有工作区
    if (!vscode.workspace.workspaceFolders || vscode.workspace.workspaceFolders.length === 0) {
      throw new Error(localize('configPage.noWorkspace'));
    }

    // Write to .env file instead of VSCode settings
    this._envManager.writeEnv({
      llmApiKey: config.llmApiKey,
      backendHost: config.backendHost,
      backendPort: config.backendPort,
      pythonPath: config.pythonPath,
      llmApiBase: config.llmApiBase,
      llmModel: (config.llmModel ?? '').trim() || DEFAULT_LLM_MODEL,
      backendLogLevel: config.backendLogLevel,
      coderLlmApiKey: config.coderLlmApiKey,
      coderLlmApiBase: config.coderLlmApiBase,
      coderLlmModel: config.coderLlmModel,
      nanoLlmApiKey: config.nanoLlmApiKey,
      nanoLlmApiBase: config.nanoLlmApiBase,
      nanoLlmModel: config.nanoLlmModel,
      analysisLlmApiKey: config.analysisLlmApiKey,
      analysisLlmApiBase: config.analysisLlmApiBase,
      analysisLlmModel: config.analysisLlmModel,
      embeddingApiKey: config.embeddingApiKey,
      embeddingApiBase: config.embeddingApiBase,
      embeddingModel: config.embeddingModel,
      embeddingDims: config.embeddingDims,
      webSearchApiUrl: config.webSearchApiUrl,
      webSearchApiToken: config.webSearchApiToken,
      miroflowDefaultLlm: config.miroflowDefaultLlm,
      miroflowDefaultAgent: config.miroflowDefaultAgent,
      literatureSearchApiUrl: config.literatureSearchApiUrl,
      literatureSearchApiKey: config.literatureSearchApiKey,
    });

    // 标记已完成初始配置
    await this._context.globalState.update('configPage.hasCompletedInitialSetup', true);
  }

  /**
   * 处理 LLM 配置验证请求
   */
  private async _handleValidateConfig(config: Partial<ConfigValues>, llmType: string = 'default'): Promise<void> {
    const validator = new LLMValidator();
    const defaultModel = (config.llmModel ?? '').trim() || DEFAULT_LLM_MODEL;

    let apiKey: string = '';
    let apiBase: string = '';
    let model: string = '';
    let validationType: LLMType = LLMType.Chat;

    switch (llmType) {
      case 'coder':
        apiKey = config.coderLlmApiKey || '';
        apiBase = config.coderLlmApiBase || '';
        model = config.coderLlmModel || defaultModel;
        break;
      case 'nano':
        apiKey = config.nanoLlmApiKey || '';
        apiBase = config.nanoLlmApiBase || '';
        model = config.nanoLlmModel || defaultModel;
        break;
      case 'analysis':
        apiKey = config.analysisLlmApiKey || '';
        apiBase = config.analysisLlmApiBase || '';
        model = config.analysisLlmModel || defaultModel;
        break;
      case 'embedding':
        apiKey = config.embeddingApiKey || '';
        apiBase = config.embeddingApiBase || '';
        model = config.embeddingModel || 'text-embedding-3-large';
        validationType = LLMType.Embedding;
        break;
      default: // default LLM
        apiKey = config.llmApiKey || '';
        apiBase = config.llmApiBase || '';
        model = defaultModel;
        break;
    }

    // 对非默认模型：若 API Key 或 Base URL 为空，则回落到默认 LLM 配置
    if (!apiKey && llmType !== 'default') {
      apiKey = config.llmApiKey || '';
    }
    if (!apiBase) {
      apiBase = config.llmApiBase || '';
    }

    const result = await validator.validate({ apiKey, apiBase, model }, validationType);

    this._panel.webview.postMessage({
      command: 'validationResult',
      llmType,
      success: result.success,
      error: result.error || null,
    });
  }

  /**
   * 处理 Python 环境验证请求
   */
  private async _handleValidatePython(config: Partial<ConfigValues>): Promise<void> {
    const validator = new PythonValidator();
    const pythonPath = config.pythonPath || '';

    const result = await validator.validate({ pythonPath });

    this._panel.webview.postMessage({
      command: 'validationResult',
      llmType: 'python',
      success: result.success,
      error: result.error || null,
    });
  }

  private async _literatureValidateHttpGet(
    url: string,
    headerMap: Record<string, string> | undefined
  ): Promise<{ ok: boolean; status: number; json: () => Promise<unknown> }> {
    const headers = headerMap ?? {};
    if (typeof globalThis.fetch === 'function') {
      const res = await fetch(url, { method: 'GET', headers });
      return {
        ok: res.ok,
        status: res.status,
        json: () => res.json(),
      };
    }
    const jr = await requestJson(url, {
      method: 'GET',
      headers,
      timeoutMs: CONFIG_PAGE_API_VALIDATE_TIMEOUT_MS,
    });
    const data = jr.data;
    return {
      ok: jr.ok,
      status: jr.status,
      json: async () => data,
    };
  }

  private async _handleValidateLiteratureSearch(config: Partial<ConfigValues>): Promise<void> {
    const apiUrl = config.literatureSearchApiUrl || '';
    const apiKey = config.literatureSearchApiKey || '';

    try {
      const baseUrl = apiUrl.replace(/\/api\/search\/?$/, '').replace(/\/$/, '');

      const healthUrl = `${baseUrl}/health`;
      const healthResponse = await this._literatureValidateHttpGet(healthUrl, undefined);

      if (!healthResponse.ok) {
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: `服务不可用: HTTP ${healthResponse.status}`,
        });
        return;
      }

      const statsUrl = `${baseUrl}/api/stats`;
      const statsResponse = await this._literatureValidateHttpGet(
        statsUrl,
        apiKey ? { Authorization: `Bearer ${apiKey}` } : {}
      );

      if (statsResponse.status === 401 || statsResponse.status === 403) {
        const errorMsg = apiKey ? 'API Key 无效' : '需要输入 API Key';
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: errorMsg,
        });
        return;
      }

      if (!statsResponse.ok) {
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: `验证失败: HTTP ${statsResponse.status}`,
        });
        return;
      }

      const statsData = (await statsResponse.json()) as { sources?: Record<string, unknown> };
      this._panel.webview.postMessage({
        command: 'literatureValidationResult',
        success: true,
        sources: statsData.sources,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '未知错误';
      this._panel.webview.postMessage({
        command: 'literatureValidationResult',
        success: false,
        error: `连接失败: ${errorMessage}`,
      });
    }
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.file(path.join(this._extensionPath, 'out', 'webview', 'configPage.js'))
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
  <title>${localize('configPage.title')}</title>
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
    ConfigPageViewProvider.currentPanel = undefined;
    this._envManager.dispose();
    while (this._disposables.length) {
      const d = this._disposables.pop();
      if (d) { d.dispose(); }
    }
  }
}
