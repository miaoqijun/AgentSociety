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
import {
  CLAUDE_SETTINGS_PATH,
  detectClaudeCli,
  isClaudeCodeEnvCustomized,
  readClaudeConfig,
  writeClaudeConfig,
} from './services/claudeCodeSettings';
import type { ClaudeCodeConfigValues } from './webview/configPage/claudeCodeTypes';
import * as path from 'path';
import { localize } from './i18n';
import type { ConfigValues, WorkspaceInfo } from './webview/configPage/types';
import type { EasyPaperConfigValues } from './webview/configPage/types';
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
      async (message: {
        command: string;
        config?: Partial<ConfigValues> | ClaudeCodeConfigValues;
        llmType?: string;
        url?: string;
      }) => {
        switch (message.command) {
          case 'requestConfig':
            await this._sendInitialConfig();
            break;
          case 'saveConfig':
            await this._handleSaveConfig((message.config || {}) as Partial<ConfigValues>);
            break;
          case 'startBackend':
            await this._handleStartBackend((message.config || {}) as Partial<ConfigValues>);
            break;
          case 'validateConfig':
            await this._handleValidateConfig((message.config || {}) as Partial<ConfigValues>, message.llmType);
            break;
          case 'validatePython':
            await this._handleValidatePython((message.config || {}) as Partial<ConfigValues>);
            break;
          case 'validateLiteratureSearch':
            await this._handleValidateLiteratureSearch((message.config || {}) as Partial<ConfigValues>);
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
          case 'saveClaudeConfig':
            await this._handleSaveClaudeConfig((message.config || {}) as ClaudeCodeConfigValues);
            break;
          case 'saveEasyPaperConfig':
            await this._handleSaveEasyPaperConfig(message.config);
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
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    const workspacePath = workspaceFolder?.uri.fsPath;
    const envPath = this._envManager.getEnvPath();
    let envFilePath: string | undefined;
    if (workspacePath && envPath) {
      envFilePath = path.relative(workspacePath, envPath) || path.basename(envPath);
    }

    const workspaceInfo: WorkspaceInfo = {
      hasWorkspace: Boolean(workspaceFolder),
      workspacePath,
      envFilePath,
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
      literatureSearchMcpUrl:
        envConfig.literatureSearchMcpUrl || 'https://llmapi.fiblab.net/mcp/',
      literatureSearchApiKey: envConfig.literatureSearchApiKey || '',
    };

    this._panel.webview.postMessage({
      command: 'initialConfig',
      config: configValues
    });

    this._panel.webview.postMessage({
      command: 'workspaceInfo',
      workspaceInfo: workspaceInfo
    });

    await this._sendClaudeInitialConfig();
    await this._sendEasyPaperInitialConfig();
    await this._postOverviewStatus();
  }

  public navigateToAdvancedTab(tab: 'models' | 'python' | 'literature' | 'claude'): void {
    this._panel.webview.postMessage({ command: 'navigateAdvanced', tab });
  }

  private async _sendClaudeInitialConfig(): Promise<void> {
    const cliStatus = await detectClaudeCli();
    const claudeConfig = readClaudeConfig();
    claudeConfig.permissionMode = vscode.workspace.getConfiguration('claudeCode').get<string>('initialPermissionMode', '');
    this._panel.webview.postMessage({
      command: 'initialClaudeConfig',
      config: claudeConfig,
      settingsPath: CLAUDE_SETTINGS_PATH,
      cliStatus,
    });
  }

  private async _handleSaveClaudeConfig(config: ClaudeCodeConfigValues): Promise<void> {
    try {
      writeClaudeConfig(config);

      const mode = (config.permissionMode || '').trim();
      const claudeCfg = vscode.workspace.getConfiguration('claudeCode');
      if (mode === 'bypassPermissions') {
        await claudeCfg.update('allowDangerouslySkipPermissions', true, vscode.ConfigurationTarget.Workspace);
        await claudeCfg.update('initialPermissionMode', 'bypassPermissions', vscode.ConfigurationTarget.Workspace);
      } else {
        await claudeCfg.update('allowDangerouslySkipPermissions', undefined, vscode.ConfigurationTarget.Workspace);
        await claudeCfg.update('initialPermissionMode', undefined, vscode.ConfigurationTarget.Workspace);
      }

      this._panel.webview.postMessage({ command: 'claudeSaveResult', success: true });
      await this._postOverviewStatus();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      this._panel.webview.postMessage({
        command: 'claudeSaveResult',
        success: false,
        error: message,
      });
    }
  }

  // ============ EasyPaper Config ============

  private async _sendEasyPaperInitialConfig(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      this._panel.webview.postMessage({ command: 'initialEasyPaperConfig', config: undefined });
      return;
    }
    const configPath = path.join(workspaceFolder.uri.fsPath, 'easypaper_config.yaml');
    const config = readEasyPaperConfig(configPath);
    this._panel.webview.postMessage({ command: 'initialEasyPaperConfig', config });
  }

  private async _handleSaveEasyPaperConfig(config: any): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      this._panel.webview.postMessage({ command: 'easyPaperSaveResult', success: false, error: 'No workspace open' });
      return;
    }
    try {
      const configPath = path.join(workspaceFolder.uri.fsPath, 'easypaper_config.yaml');
      writeEasyPaperConfig(configPath, config);
      this._panel.webview.postMessage({ command: 'easyPaperSaveResult', success: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      this._panel.webview.postMessage({ command: 'easyPaperSaveResult', success: false, error: message });
    }
  }

  private async _postOverviewStatus(): Promise<void> {
    const backendStatus = await this._getBackendStatus();
    this._panel.webview.postMessage({
      command: 'backendStatus',
      backendStatus,
      claudeCodeCustomized: isClaudeCodeEnvCustomized(),
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
      literatureSearchMcpUrl: config.literatureSearchMcpUrl,
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

  private async _literatureValidateHttpPost(
    url: string,
    headerMap: Record<string, string> | undefined,
    body: Record<string, unknown>
  ): Promise<{ ok: boolean; status: number; json: () => Promise<unknown> }> {
    const headers = {
      ...(headerMap ?? {}),
      'Content-Type': 'application/json',
    };
    if (typeof globalThis.fetch === 'function') {
      const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
      return {
        ok: res.ok,
        status: res.status,
        json: () => res.json(),
      };
    }
    const jr = await requestJson(url, {
      method: 'POST',
      headers,
      body,
      timeoutMs: CONFIG_PAGE_API_VALIDATE_TIMEOUT_MS,
    });
    return {
      ok: jr.ok,
      status: jr.status,
      json: async () => jr.data,
    };
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

  private _literatureAuthHeaders(apiKey: string): Record<string, string> | undefined {
    const trimmed = apiKey.trim();
    if (!trimmed) {
      return undefined;
    }
    return { Authorization: `Bearer ${trimmed}` };
  }

  private _literatureAuthError(status: number, apiKey: string): string {
    if (status === 401 || status === 403) {
      return apiKey.trim()
        ? localize('configPage.validation.literatureAuthInvalid')
        : localize('configPage.validation.literatureAuthRequired');
    }
    return localize('configPage.validation.literatureGatewayError', String(status));
  }

  private static readonly LITERATURE_MCP_TOOL_SUFFIXES = [
    'literature_search',
    'literature_status',
    'literature_ingest_text',
  ] as const;

  /** Validation only requires search + status; ingest is optional and unused by the runtime. */
  private static readonly LITERATURE_MCP_REQUIRED_SUFFIXES = [
    'literature_search',
    'literature_status',
  ] as const;

  private _isLiteratureMcpTool(name: string): boolean {
    return ConfigPageViewProvider.LITERATURE_MCP_TOOL_SUFFIXES.some(
      (suffix) => name === suffix || name.endsWith(`-${suffix}`)
    );
  }

  private _literatureMcpGatewayOrigin(mcpUrl: string): string | null {
    try {
      let normalized = mcpUrl.trim();
      if (normalized.endsWith('/mcp')) {
        normalized = `${normalized}/`;
      }
      const parsed = new URL(normalized);
      return parsed.origin;
    } catch {
      return null;
    }
  }

  private _pickLiteratureMcpTool(
    toolNames: string[],
    suffix: (typeof ConfigPageViewProvider.LITERATURE_MCP_TOOL_SUFFIXES)[number]
  ): string | null {
    const literatureTools = toolNames.filter((name) => this._isLiteratureMcpTool(name));
    const exact = literatureTools.find((name) => name === suffix || name.endsWith(`-${suffix}`));
    return exact ?? null;
  }

  private _missingLiteratureTools(toolNames: string[]): string[] {
    return ConfigPageViewProvider.LITERATURE_MCP_REQUIRED_SUFFIXES.filter(
      (suffix) => !this._pickLiteratureMcpTool(toolNames, suffix)
    );
  }

  private async _handleValidateLiteratureSearch(config: Partial<ConfigValues>): Promise<void> {
    const mcpUrl = config.literatureSearchMcpUrl || '';
    const apiKey = config.literatureSearchApiKey || '';
    const authHeaders = this._literatureAuthHeaders(apiKey);

    if (!mcpUrl.trim()) {
      this._panel.webview.postMessage({
        command: 'literatureValidationResult',
        success: false,
        error: '请输入学术文献检索 MCP 地址',
      });
      return;
    }

    if (!apiKey.trim()) {
      this._panel.webview.postMessage({
        command: 'literatureValidationResult',
        success: false,
        error: '需要输入 API Key',
      });
      return;
    }

    if (!mcpUrl.includes('/mcp')) {
      this._panel.webview.postMessage({
        command: 'literatureValidationResult',
        success: false,
        error: 'MCP 地址应为 https://llmapi.fiblab.net/mcp/',
      });
      return;
    }

    const gatewayOrigin = this._literatureMcpGatewayOrigin(mcpUrl);
    if (!gatewayOrigin) {
      this._panel.webview.postMessage({
        command: 'literatureValidationResult',
        success: false,
        error: '请使用 MCP 网关地址 https://llmapi.fiblab.net/mcp/',
      });
      return;
    }

    try {
      const listUrl = `${gatewayOrigin}/mcp-rest/tools/list`;
      const listResponse = await this._literatureValidateHttpGet(listUrl, authHeaders);
      if (!listResponse.ok) {
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: this._literatureAuthError(listResponse.status, apiKey),
        });
        return;
      }

      const listData = (await listResponse.json()) as {
        tools?: Array<{ name?: string }>;
      };
      const toolNames = (listData.tools ?? [])
        .map((tool) => tool.name)
        .filter((name): name is string => Boolean(name));
      const missing = this._missingLiteratureTools(toolNames);
      if (missing.length > 0) {
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: '网关未提供学术文献检索服务，请确认 API Key 具备文献检索权限',
        });
        return;
      }

      const statusTool = this._pickLiteratureMcpTool(toolNames, 'literature_status');
      if (!statusTool) {
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: '无法获取学术文献检索服务状态',
        });
        return;
      }

      const callUrl = `${gatewayOrigin}/mcp-rest/tools/call`;
      const callResponse = await this._literatureValidateHttpPost(
        callUrl,
        authHeaders,
        { name: statusTool, arguments: {} }
      );
      if (!callResponse.ok) {
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: this._literatureAuthError(callResponse.status, apiKey),
        });
        return;
      }

      const callPayload = (await callResponse.json()) as Array<{ text?: string }>;
      const textBlock = callPayload.find((block) => block.text)?.text;
      if (!textBlock) {
        this._panel.webview.postMessage({
          command: 'literatureValidationResult',
          success: false,
          error: '学术文献检索服务未返回有效状态',
        });
        return;
      }

      const statusData = JSON.parse(textBlock) as { sources?: Record<string, unknown> };
      this._panel.webview.postMessage({
        command: 'literatureValidationResult',
        success: true,
        sources: statusData.sources,
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

// ============ EasyPaper YAML Utilities ============

const EASY_PAPER_AGENT_NAMES = [
  'paper_parser', 'template_parser', 'commander', 'writer',
  'typesetter', 'metadata', 'reviewer', 'planner',
];

function readEasyPaperConfig(configPath: string): EasyPaperConfigValues | undefined {
  const fs = require('fs');
  const yaml = require('js-yaml');
  if (!fs.existsSync(configPath)) {
    return undefined;
  }
  try {
    const raw = fs.readFileSync(configPath, 'utf-8');
    const data = yaml.load(raw) as any;
    if (!data || typeof data !== 'object') {
      return undefined;
    }
    const result: EasyPaperConfigValues = {
      llmModelName: '',
      llmApiKey: '',
      llmBaseUrl: '',
      vlmEnabled: false,
      vlmModel: '',
      vlmApiKey: '',
      vlmBaseUrl: '',
    };
    // Extract LLM config from first agent
    const agents = Array.isArray(data.agents) ? data.agents : [];
    const firstModel = agents[0]?.model;
    if (firstModel) {
      result.llmModelName = firstModel.model_name || '';
      result.llmApiKey = firstModel.api_key || '';
      result.llmBaseUrl = firstModel.base_url || '';
    }
    // Extract VLM config
    const vlm = data.vlm_service;
    if (vlm && vlm.model) {
      result.vlmEnabled = true;
      result.vlmModel = vlm.model || '';
      result.vlmApiKey = vlm.api_key || '';
      result.vlmBaseUrl = vlm.base_url || '';
    }
    return result;
  } catch {
    return undefined;
  }
}

function writeEasyPaperConfig(configPath: string, config: EasyPaperConfigValues): void {
  const fs = require('fs');
  const hasLlm = config.llmModelName?.trim() || config.llmApiKey?.trim() || config.llmBaseUrl?.trim();
  if (!hasLlm) {
    // No LLM config — delete the file if it exists
    if (fs.existsSync(configPath)) {
      fs.unlinkSync(configPath);
    }
    return;
  }

  const agentBlock = (name: string) => {
    const entry: any = {
      name,
      model: {
        model_name: config.llmModelName || '',
        api_key: config.llmApiKey || '',
        base_url: config.llmBaseUrl || '',
      },
    };
    if (name === 'writer') {
      entry.writer_config = {};
    }
    if (name === 'metadata') {
      entry.metadata_config = {};
    }
    return entry;
  };

  const yamlObj: any = {
    skills: {},
    tools: {
      table_critic_enabled: true,
      table_rendered_review_enabled: true,
      paper_search: { timeout: 15, search_results_per_round: 12 },
      research_context: {},
      core_ref_analysis: {},
      docling: { enabled: true },
      exemplar: { enabled: true },
    },
    agents: EASY_PAPER_AGENT_NAMES.map(agentBlock),
  };

  // vlm_review agent (no model if VLM disabled)
  if (!config.vlmEnabled) {
    yamlObj.agents.push({ name: 'vlm_review', vlm_review_config: { check_layout: true } });
  } else {
    yamlObj.agents.push({ name: 'vlm_review', vlm_review_config: { check_layout: true } });
  }

  // VLM service
  if (config.vlmEnabled && (config.vlmModel?.trim() || config.vlmApiKey?.trim())) {
    yamlObj.vlm_service = {
      model: config.vlmModel || '',
      api_key: config.vlmApiKey || '',
      base_url: config.vlmBaseUrl || '',
    };
  }

  // Generate YAML manually to preserve formatting
  const yaml = require('js-yaml');
  const content = yaml.dump(yamlObj, { lineWidth: 120, noRefs: true });
  fs.writeFileSync(configPath, content, 'utf-8');
}
