/**
 * 技能管理 Webview：Agent 运行时技能（后端 API）与 Claude 目录技能（.claude/skills）分栏；
 * 技能市场仅从用户配置的 GitHub 源拉取，无静默回退与占位 stub。
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { execSync } from 'child_process';
import type { MarketplaceSkill, AgentSkill, ClaudeCodeSkill, BuiltinSkill } from './webview/skillMarketplace/types';
import { ApiClient } from './apiClient';

const PANEL_VIEW_TYPE = 'aiSocialScientist.skillMarketplace';

const GITHUB_API_TIMEOUT_MS = 45_000;
const GITHUB_RAW_TIMEOUT_MS = 28_000;

const CATEGORY_MAP: Record<string, { id: string; name: string; nameZh: string }> = {
  pdf: { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  docx: { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  xlsx: { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  pptx: { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  'artifacts-builder': { id: 'development', name: 'Development Tools', nameZh: '开发工具' },
  'canvas-design': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'algorithmic-art': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'mcp-builder': { id: 'integration', name: 'Integrations', nameZh: '集成工具' },
  'webapp-testing': { id: 'development', name: 'Development Tools', nameZh: '开发工具' },
  'skill-creator': { id: 'development', name: 'Development Tools', nameZh: '开发工具' },
  'internal-comms': { id: 'productivity', name: 'Productivity', nameZh: '效率工具' },
  'slack-gif-creator': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'brand-guidelines': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'theme-factory': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' }
};

type GitHubContentItem = { name: string; type: string; path: string };

export class SkillMarketplacePanel {
  public static current: SkillMarketplacePanel | undefined;

  private readonly _extensionUri: vscode.Uri;
  private readonly _outputChannel: vscode.OutputChannel;
  private readonly _panel: vscode.WebviewPanel;
  private readonly _webview: vscode.Webview;
  private readonly _apiClient: ApiClient;

  private constructor(
    extensionUri: vscode.Uri,
    outputChannel: vscode.OutputChannel,
    panel: vscode.WebviewPanel,
    apiClient: ApiClient
  ) {
    this._extensionUri = extensionUri;
    this._outputChannel = outputChannel;
    this._panel = panel;
    this._webview = panel.webview;
    this._apiClient = apiClient;

    this._webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };
    this._webview.html = this._getHtmlForWebview(this._webview);

    this._webview.onDidReceiveMessage(
      async (data) => {
        if (!data) {
          return;
        }
        switch (data.type) {
          case 'ready':
            await this._loadAgentSkills();
            await this._loadClaudeCodeSkills();
            await this._loadBuiltinSkills();
            await this._loadMarketplaceSkills();
            break;

          // Agent Skills
          case 'listAgentSkills':
            await this._loadAgentSkills();
            break;
          case 'enableAgentSkill':
            await this._enableAgentSkill(data.payload.name);
            break;
          case 'disableAgentSkill':
            await this._disableAgentSkill(data.payload.name);
            break;
          case 'reloadAgentSkill':
            await this._reloadAgentSkill(data.payload.name);
            break;
          case 'removeAgentSkill':
            await this._removeAgentSkill(data.payload.name);
            break;

          // Claude Code Skills
          case 'listClaudeCodeSkills':
            await this._loadClaudeCodeSkills();
            break;
          case 'deleteClaudeCodeSkill':
            await this._deleteClaudeCodeSkill(data.payload.name);
            break;

          // Marketplace
          case 'refreshMarketplace':
            await this._loadMarketplaceSkills();
            break;
          case 'installAgentSkill':
            await this._installAgentSkill(data.payload.skill);
            break;
          case 'installClaudeCodeSkill':
            await this._installClaudeCodeSkill(data.payload.skill);
            break;
          case 'importAgentSkill':
            await this._importAgentSkill();
            break;
          case 'importClaudeCodeSkill':
            await this._importClaudeCodeSkill();
            break;
          case 'listBuiltinSkills':
            await this._loadBuiltinSkills();
            break;
          case 'scanAgentSkills':
            await this._scanAgentSkills();
            break;
          case 'updateExtensionSkills':
            await vscode.commands.executeCommand('aiSocialScientist.updateExtensionSkills');
            await this._loadBuiltinSkills();
            await this._loadClaudeCodeSkills();
            break;
          case 'openAgentSkillDoc':
            await vscode.commands.executeCommand(
              'aiSocialScientist.openAgentSkillDoc',
              data.payload.skillName,
              data.payload.skillPath,
              data.payload.isBuiltin
            );
            break;
          case 'openLocalSkillMarkdown':
            this._openLocalSkillMarkdown(data.payload.skillDir);
            break;
          case 'openSkillFolder':
            this._openSkillFolder(data.payload.path);
            break;
          case 'fetchAgentSkillDetail':
            await this._fetchAgentSkillDetail(data.payload.name);
            break;
          case 'fetchLocalSkillMarkdown':
            await this._fetchLocalSkillMarkdown(data.payload.skillDir);
            break;
          case 'openExternal':
            vscode.env.openExternal(vscode.Uri.parse(data.payload.url));
            break;
          case 'openSkillSourcesSettings':
            await vscode.commands.executeCommand('workbench.action.openSettings', 'agentSkills.skillSources');
            break;
        }
      },
      undefined,
      []
    );

    this._panel.onDidDispose(
      () => {
        SkillMarketplacePanel.current = undefined;
      },
      null,
      []
    );
  }

  public static createOrShow(
    context: vscode.ExtensionContext,
    outputChannel: vscode.OutputChannel,
    apiClient: ApiClient,
    column: vscode.ViewColumn = vscode.ViewColumn.One
  ): void {
    if (SkillMarketplacePanel.current) {
      SkillMarketplacePanel.current._panel.reveal(column);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      PANEL_VIEW_TYPE,
      'Skill Management',
      column,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [context.extensionUri]
      }
    );

    context.subscriptions.push(panel);
    SkillMarketplacePanel.current = new SkillMarketplacePanel(context.extensionUri, outputChannel, panel, apiClient);
  }

  private _normalizeSkillSources(
    sources: any[]
  ): Array<{ owner: string; repo: string; branch: string; skillsPath: string }> {
    const out: Array<{ owner: string; repo: string; branch: string; skillsPath: string }> = [];
    for (const s of sources) {
      if (!s || typeof s !== 'object') {
        continue;
      }
      const owner = String((s as any).owner ?? '').trim();
      const repo = String((s as any).repo ?? '').trim();
      const branch = String((s as any).branch ?? 'main').trim() || 'main';
      const skillsPath = String((s as any).skillsPath ?? (s as any).path ?? '')
        .trim()
        .replace(/^\/+|\/+$/g, '');
      if (!owner || !repo) {
        continue;
      }
      out.push({ owner, repo, branch, skillsPath });
    }
    return out;
  }

  private _dedupeMarketplaceSkills(skills: MarketplaceSkill[]): MarketplaceSkill[] {
    const seen = new Set<string>();
    const result: MarketplaceSkill[] = [];
    for (const s of skills) {
      const segments = s.path.split('/').filter(Boolean);
      const key = (segments.length ? segments[segments.length - 1] : s.id).toLowerCase();
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      result.push(s);
    }
    return result;
  }

  private async _fetchWithTimeout(url: string, headers: Record<string, string>, timeoutMs: number): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(url, { headers, signal: controller.signal });
    } finally {
      clearTimeout(timer);
    }
  }

  private _isNetworkOrTimeoutError(error: unknown): boolean {
    const e = error as { name?: string; message?: string };
    const msg = (e?.message || String(error)).toLowerCase();
    if (e?.name === 'AbortError') {
      return true;
    }
    return (
      msg.includes('fetch failed') ||
      msg.includes('network') ||
      msg.includes('econnrefused') ||
      msg.includes('enotfound') ||
      msg.includes('etimedout') ||
      msg.includes('timeout') ||
      msg.includes('getaddrinfo')
    );
  }

  private _githubHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      Accept: 'application/vnd.github.v3+json',
      'User-Agent': 'AI-Social-Scientist-VSCode'
    };
    const token = vscode.workspace.getConfiguration('agentSkills').get<string>('githubToken', '')?.trim();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    return headers;
  }

  // ============ Agent Skills ============

  private async _loadAgentSkills(): Promise<void> {
    try {
      const response = await this._apiClient.listAgentSkills();
      if (response.success) {
        const skills: AgentSkill[] = response.skills.map(s => ({
          name: s.name,
          description: s.description,
          source: s.source,
          enabled: s.enabled,
          path: s.path,
          has_skill_md: s.has_skill_md,
          script: s.script,
          requires: s.requires
        }));
        await this._postMessage({ type: 'agentSkillsLoaded', payload: skills });
      }
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Failed to load agent skills: ${error.message}`);
      await this._postMessage({ type: 'agentSkillsLoaded', payload: [] });
    }
  }

  private async _enableAgentSkill(name: string): Promise<void> {
    try {
      const response = await this._apiClient.enableAgentSkill(name);
      await this._postMessage({ type: 'agentSkillEnabled', payload: { message: response.message } });
    } catch (error: any) {
      await this._postMessage({ type: 'error', payload: `Failed to enable skill: ${error.message}` });
    }
  }

  private async _disableAgentSkill(name: string): Promise<void> {
    try {
      const response = await this._apiClient.disableAgentSkill(name);
      await this._postMessage({ type: 'agentSkillDisabled', payload: { message: response.message } });
    } catch (error: any) {
      await this._postMessage({ type: 'error', payload: `Failed to disable skill: ${error.message}` });
    }
  }

  private async _reloadAgentSkill(name: string): Promise<void> {
    try {
      const response = await this._apiClient.reloadAgentSkill(name);
      await this._postMessage({ type: 'agentSkillReloaded', payload: { message: response.message } });
    } catch (error: any) {
      await this._postMessage({ type: 'error', payload: `Failed to reload skill: ${error.message}` });
    }
  }

  private async _removeAgentSkill(name: string): Promise<void> {
    try {
      const response = await this._apiClient.removeAgentSkill(name);
      await this._postMessage({ type: 'agentSkillRemoved', payload: { message: response.message } });
      await this._loadAgentSkills();
    } catch (error: any) {
      await this._postMessage({ type: 'error', payload: error.message || String(error) });
    }
  }

  private async _scanAgentSkills(): Promise<void> {
    try {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      const response = await this._apiClient.scanAgentSkills(workspaceFolder?.uri.fsPath);
      if (response.success) {
        vscode.window.showInformationMessage(response.message);
      }
      await this._loadAgentSkills();
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Scan failed: ${error.message}`);
      await this._postMessage({ type: 'error', payload: error.message || String(error) });
    }
  }

  private async _loadBuiltinSkills(): Promise<void> {
    const skills: BuiltinSkill[] = [];
    const skillsDir = path.join(this._extensionUri.fsPath, 'skills');
    if (fs.existsSync(skillsDir)) {
      try {
        const names = fs.readdirSync(skillsDir).filter((name) => {
          const skillPath = path.join(skillsDir, name);
          return fs.statSync(skillPath).isDirectory() && fs.existsSync(path.join(skillPath, 'SKILL.md'));
        });
        for (const name of names) {
          const skillPath = path.join(skillsDir, name);
          const mdPath = path.join(skillPath, 'SKILL.md');
          const content = fs.readFileSync(mdPath, 'utf-8');
          const frontmatter = this._parseFrontmatter(content);
          skills.push({
            name,
            path: skillPath,
            hasSkillMd: true,
            description: typeof frontmatter.description === 'string' ? frontmatter.description : undefined
          });
        }
      } catch (error: any) {
        this._outputChannel.appendLine(`[SkillManagement] Failed to load extension skills: ${error.message}`);
      }
    }
    await this._postMessage({ type: 'builtinSkillsLoaded', payload: skills });
  }

  private _openLocalSkillMarkdown(skillDir: string): void {
    const mdPath = path.join(skillDir, 'SKILL.md');
    if (!fs.existsSync(mdPath)) {
      vscode.window.showWarningMessage('SKILL.md not found');
      return;
    }
    void vscode.commands.executeCommand('markdown.showPreview', vscode.Uri.file(mdPath));
  }

  // ============ Claude Code Skills ============

  private async _loadClaudeCodeSkills(): Promise<void> {
    const skills: ClaudeCodeSkill[] = [];
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

    if (workspaceFolder) {
      const workspaceSkillsPath = path.join(workspaceFolder.uri.fsPath, '.claude', 'skills');
      this._scanClaudeCodeSkills(workspaceSkillsPath, skills, 'workspace');
    }

    const globalSkillsPath = path.join(process.env.HOME || process.env.USERPROFILE || '', '.claude', 'skills');
    this._scanClaudeCodeSkills(globalSkillsPath, skills, 'global');

    await this._postMessage({ type: 'claudeCodeSkillsLoaded', payload: skills });
  }

  private _scanClaudeCodeSkills(dirPath: string, skills: ClaudeCodeSkill[], origin: 'workspace' | 'global'): void {
    if (!fs.existsSync(dirPath)) {
      return;
    }

    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory()) {
          const skillPath = path.join(dirPath, entry.name);
          const skillMdPath = path.join(skillPath, 'SKILL.md');
          const hasSkillMd = fs.existsSync(skillMdPath);

          let description: string | undefined;
          if (hasSkillMd) {
            const content = fs.readFileSync(skillMdPath, 'utf-8');
            const frontmatter = this._parseFrontmatter(content);
            description = frontmatter.description;
          }

          const files = fs.readdirSync(skillPath).filter(f => !f.startsWith('.'));

          skills.push({
            name: entry.name,
            path: skillPath,
            hasSkillMd,
            description,
            files,
            origin
          });
        }
      }
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Failed to scan ${dirPath}: ${error.message}`);
    }
  }

  private async _deleteClaudeCodeSkill(skillName: string): Promise<void> {
    try {
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      const paths = [
        workspaceFolder ? path.join(workspaceFolder.uri.fsPath, '.claude', 'skills', skillName) : null,
        path.join(process.env.HOME || process.env.USERPROFILE || '', '.claude', 'skills', skillName)
      ].filter(Boolean) as string[];

      for (const skillPath of paths) {
        if (fs.existsSync(skillPath)) {
          fs.rmSync(skillPath, { recursive: true, force: true });
          this._outputChannel.appendLine(`[SkillManagement] Deleted skill: ${skillPath}`);
        }
      }

      await this._postMessage({ type: 'claudeCodeSkillDeleted', payload: { name: skillName } });
      await this._loadClaudeCodeSkills();
    } catch (error: any) {
      await this._postMessage({ type: 'error', payload: `Failed to delete skill: ${error.message}` });
    }
  }

  private _isUnderDir(resolvedPath: string, resolvedDir: string): boolean {
    return resolvedPath === resolvedDir || resolvedPath.startsWith(resolvedDir + path.sep);
  }

  private _canReadSkillDir(skillDir: string): boolean {
    const resolved = path.resolve(skillDir);
    const extSkills = path.resolve(path.join(this._extensionUri.fsPath, 'skills'));
    if (this._isUnderDir(resolved, extSkills)) {
      return true;
    }
    const wf = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
    if (wf) {
      if (this._isUnderDir(resolved, path.resolve(path.join(wf, 'custom', 'skills')))) {
        return true;
      }
      if (this._isUnderDir(resolved, path.resolve(path.join(wf, '.claude', 'skills')))) {
        return true;
      }
    }
    const home = process.env.HOME || process.env.USERPROFILE || '';
    if (home) {
      const globalClaude = path.resolve(path.join(home, '.claude', 'skills'));
      if (this._isUnderDir(resolved, globalClaude)) {
        return true;
      }
    }
    return false;
  }

  private async _fetchAgentSkillDetail(name: string): Promise<void> {
    try {
      const r = await this._apiClient.getAgentSkillInfo(name);
      if (r.success) {
        await this._postMessage({ type: 'agentSkillDetailLoaded', payload: r });
      } else {
        await this._postMessage({
          type: 'skillDetailError',
          payload: { key: `agent:${name}`, error: 'Skill not found or no detail' }
        });
      }
    } catch (error: any) {
      await this._postMessage({
        type: 'skillDetailError',
        payload: { key: `agent:${name}`, error: error.message || String(error) }
      });
    }
  }

  private async _fetchLocalSkillMarkdown(skillDir: string): Promise<void> {
    if (!this._canReadSkillDir(skillDir)) {
      await this._postMessage({
        type: 'skillDetailError',
        payload: { key: `path:${skillDir}`, error: 'Path not allowed' }
      });
      return;
    }
    const mdPath = path.join(skillDir, 'SKILL.md');
    if (!fs.existsSync(mdPath)) {
      await this._postMessage({
        type: 'localSkillMarkdownLoaded',
        payload: { path: skillDir, content: '' }
      });
      return;
    }
    const stat = fs.statSync(mdPath);
    const max = 512 * 1024;
    if (stat.size > max) {
      await this._postMessage({
        type: 'skillDetailError',
        payload: { key: `path:${skillDir}`, error: 'SKILL.md too large' }
      });
      return;
    }
    const content = fs.readFileSync(mdPath, 'utf-8');
    await this._postMessage({ type: 'localSkillMarkdownLoaded', payload: { path: skillDir, content } });
  }

  // ============ Marketplace ============

  private async _loadMarketplaceSkills(): Promise<void> {
    const raw = vscode.workspace.getConfiguration('agentSkills').get<unknown>('skillSources');
    const sources = this._normalizeSkillSources(Array.isArray(raw) ? raw : []);
    const errors: Array<
      | { code: 'NO_SKILL_SOURCES' }
      | { code: 'NETWORK'; message: string }
      | { code: 'GITHUB_SOURCE_FAILED'; source: string; message: string }
    > = [];
    const remote: MarketplaceSkill[] = [];

    if (sources.length === 0) {
      errors.push({ code: 'NO_SKILL_SOURCES' });
      await this._postMessage({ type: 'marketplaceSkillsLoaded', payload: { skills: [], errors } });
      return;
    }

    for (const source of sources) {
      const label = `${source.owner}/${source.repo}`;
      try {
        const skills = await this._fetchSkillsFromGitHub(source);
        remote.push(...skills);
      } catch (error: any) {
        const msg = error?.message || String(error);
        this._outputChannel.appendLine(`[SkillManagement] Marketplace source ${label}: ${msg}`);
        if (this._isNetworkOrTimeoutError(error)) {
          errors.push({ code: 'NETWORK', message: `${label}: ${msg}` });
        } else {
          errors.push({ code: 'GITHUB_SOURCE_FAILED', source: label, message: msg });
        }
      }
    }

    const merged = this._dedupeMarketplaceSkills(remote);
    await this._postMessage({ type: 'marketplaceSkillsLoaded', payload: { skills: merged, errors } });
  }

  private async _fetchSkillsFromGitHub(
    source: { owner: string; repo: string; branch: string; skillsPath: string }
  ): Promise<MarketplaceSkill[]> {
    const { owner, repo, branch, skillsPath } = source;
    const base = `https://api.github.com/repos/${owner}/${repo}/contents`;
    const apiUrl = skillsPath
      ? `${base}/${skillsPath.replace(/^\/+|\/+$/g, '')}?ref=${encodeURIComponent(branch)}`
      : `${base}?ref=${encodeURIComponent(branch)}`;

    this._outputChannel.appendLine(`[SkillMarketplace] Fetching skills from: ${apiUrl}`);

    const response = await this._fetchWithTimeout(apiUrl, this._githubHeaders(), GITHUB_API_TIMEOUT_MS);

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`GitHub API error: ${response.status} ${response.statusText} ${text.slice(0, 200)}`);
    }

    const contents = (await response.json()) as unknown;
    if (!Array.isArray(contents)) {
      const errBody =
        typeof contents === 'object' && contents !== null && 'message' in contents
          ? String((contents as { message: string }).message)
          : JSON.stringify(contents);
      throw new Error(`GitHub API returned non-array: ${errBody}`);
    }

    const skills: MarketplaceSkill[] = [];
    const dirs = contents.filter((item): item is GitHubContentItem => item.type === 'dir');

    const concurrency = 6;
    for (let i = 0; i < dirs.length; i += concurrency) {
      const batch = dirs.slice(i, i + concurrency);
      const batchResults = await Promise.all(
        batch.map((item) => this._fetchSkillInfo(owner, repo, branch, item.path, item.name))
      );
      for (const skillInfo of batchResults) {
        if (skillInfo) {
          skills.push(skillInfo);
        }
      }
    }

    return skills;
  }

  private async _fetchSkillInfo(
    owner: string,
    repo: string,
    branch: string,
    skillPath: string,
    skillName: string
  ): Promise<MarketplaceSkill | null> {
    try {
      const skillMdUrl = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${skillPath}/SKILL.md`;
      const response = await this._fetchWithTimeout(
        skillMdUrl,
        { 'User-Agent': 'AI-Social-Scientist-VSCode' },
        GITHUB_RAW_TIMEOUT_MS
      );

      if (!response.ok) {
        this._outputChannel.appendLine(
          `[SkillMarketplace] Skip ${skillName}: SKILL.md unavailable (${response.status})`
        );
        return null;
      }

      const content = await response.text();
      const frontmatter = this._parseFrontmatter(content);

      const catInfo = CATEGORY_MAP[skillName] || { id: 'other', name: 'Other', nameZh: '其他' };

      return {
        id: skillName,
        name: frontmatter.name || this._formatSkillName(skillName),
        description:
          typeof frontmatter.description === 'string' && frontmatter.description.trim()
            ? frontmatter.description
            : '',
        descriptionZh:
          typeof frontmatter.descriptionZh === 'string' && frontmatter.descriptionZh.trim()
            ? frontmatter.descriptionZh
            : undefined,
        category: catInfo.id,
        author: typeof frontmatter.author === 'string' && frontmatter.author.trim() ? frontmatter.author : owner,
        repo: `https://github.com/${owner}/${repo}`,
        branch,
        path: skillPath,
        tags: Array.isArray(frontmatter.tags) ? frontmatter.tags : [skillName],
        compatibility: ['claude', 'copilot', 'cursor'],
        version: frontmatter.version || '1.0.0',
        installTarget: 'both'
      };
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Skip ${skillName}: ${error.message}`);
      return null;
    }
  }

  private _parseFrontmatter(content: string): Record<string, any> {
    const result: Record<string, any> = {};
    const normalized = content.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n');
    const frontmatterMatch = normalized.match(/^---\n([\s\S]*?)\n---/);

    if (!frontmatterMatch) {
      return result;
    }

    const lines = frontmatterMatch[1].split('\n');
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) {
        continue;
      }
      const match = trimmed.match(/^([\w-]+):\s*(.*)$/);
      if (match) {
        const key = match[1];
        let value: any = match[2].trim();

        if (value.startsWith('[') && value.endsWith(']')) {
          value = value
            .slice(1, -1)
            .split(',')
            .map((s: string) => s.trim().replace(/['"]/g, ''));
        } else if (value.startsWith('"') && value.endsWith('"')) {
          value = value.slice(1, -1);
        }

        result[key] = value;
      }
    }

    return result;
  }

  private _formatSkillName(name: string): string {
    return name
      .split('-')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  private async _installAgentSkill(skill: MarketplaceSkill): Promise<void> {
    try {
      await this._postMessage({ type: 'installProgress', payload: { skillId: skill.id, status: 'downloading' } });
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      const targetDir = path.join(workspaceFolder?.uri.fsPath || '', 'custom', 'skills', skill.id);

      if (fs.existsSync(targetDir)) {
        fs.rmSync(targetDir, { recursive: true, force: true });
      }
      fs.mkdirSync(path.dirname(targetDir), { recursive: true });

      await this._postMessage({ type: 'installProgress', payload: { skillId: skill.id, status: 'installing' } });

      const tempDir = path.join(process.env.TMP || '/tmp', `skill-${skill.id}-${Date.now()}`);
      execSync(`git clone --depth 1 --branch ${skill.branch || 'main'} ${skill.repo} "${tempDir}"`, { encoding: 'utf-8', timeout: 120000 });

      const sourcePath = path.join(tempDir, skill.path);
      if (fs.existsSync(sourcePath)) {
        fs.cpSync(sourcePath, targetDir, { recursive: true });
      } else if (skill.path === '.' || skill.path === '' || skill.path === skill.id) {
        fs.cpSync(tempDir, targetDir, { recursive: true });
      } else {
        throw new Error(`Skill path not found: ${sourcePath}`);
      }
      fs.rmSync(tempDir, { recursive: true, force: true });

      await this._postMessage({
        type: 'installComplete',
        payload: { skillId: skill.id, name: skill.name, skillType: 'agent' }
      });
      this._outputChannel.appendLine(`[SkillManagement] Successfully installed Agent Skill: ${skill.name}`);
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Failed to install ${skill.name}: ${error.message}`);
      await this._postMessage({ type: 'installFailed', payload: { skillId: skill.id, error: error.message } });
    }
  }

  private async _installClaudeCodeSkill(skill: MarketplaceSkill): Promise<void> {
    try {
      await this._postMessage({ type: 'installProgress', payload: { skillId: skill.id, status: 'downloading' } });
      const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
      const targetDir = path.join(workspaceFolder?.uri.fsPath || '', '.claude', 'skills', skill.id);

      if (fs.existsSync(targetDir)) {
        fs.rmSync(targetDir, { recursive: true, force: true });
      }
      fs.mkdirSync(path.dirname(targetDir), { recursive: true });

      await this._postMessage({ type: 'installProgress', payload: { skillId: skill.id, status: 'installing' } });

      const tempDir = path.join(process.env.TMP || '/tmp', `skill-${skill.id}-${Date.now()}`);
      execSync(`git clone --depth 1 --branch ${skill.branch || 'main'} ${skill.repo} "${tempDir}"`, { encoding: 'utf-8', timeout: 120000 });

      const sourcePath = path.join(tempDir, skill.path);
      if (fs.existsSync(sourcePath)) {
        fs.cpSync(sourcePath, targetDir, { recursive: true });
      } else if (skill.path === '.' || skill.path === '' || skill.path === skill.id) {
        fs.cpSync(tempDir, targetDir, { recursive: true });
      } else {
        throw new Error(`Skill path not found: ${sourcePath}`);
      }
      fs.rmSync(tempDir, { recursive: true, force: true });

      await this._postMessage({
        type: 'installComplete',
        payload: { skillId: skill.id, name: skill.name, skillType: 'claudeCode' }
      });
      this._outputChannel.appendLine(`[SkillManagement] Successfully installed Claude Code Skill: ${skill.name}`);
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Failed to install ${skill.name}: ${error.message}`);
      await this._postMessage({ type: 'installFailed', payload: { skillId: skill.id, error: error.message } });
    }
  }

  private async _importAgentSkill(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    const uris = await vscode.window.showOpenDialog({
      canSelectFolders: true,
      canSelectFiles: false,
      canSelectMany: false,
      openLabel: 'Import Skill Directory'
    });
    if (!uris?.[0]) {
      return;
    }
    try {
      const response = await this._apiClient.importAgentSkill(uris[0].fsPath, workspaceFolder?.uri.fsPath);
      if (response.success) {
        vscode.window.showInformationMessage(response.message);
        await this._postMessage({ type: 'agentSkillImported', payload: { name: path.basename(uris[0].fsPath) } });
        await this._loadAgentSkills();
      }
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Failed to import skill: ${error.message}`);
      await this._postMessage({ type: 'error', payload: error.message || String(error) });
    }
  }

  private async _importClaudeCodeSkill(): Promise<void> {
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
    if (!workspaceFolder) {
      vscode.window.showErrorMessage('请先打开工作区文件夹，再导入 Claude Code 技能。');
      return;
    }
    const uris = await vscode.window.showOpenDialog({
      canSelectFolders: true,
      canSelectFiles: false,
      canSelectMany: false,
      openLabel: 'Import Claude Code Skill Directory'
    });
    if (!uris?.[0]) {
      return;
    }
    const src = uris[0].fsPath;
    const dirName = path.basename(src);
    const skillMd = path.join(src, 'SKILL.md');
    if (!fs.existsSync(skillMd)) {
      vscode.window.showErrorMessage('所选目录必须包含 SKILL.md');
      return;
    }
    const destRoot = path.join(workspaceFolder.uri.fsPath, '.claude', 'skills');
    const dest = path.join(destRoot, dirName);
    try {
      fs.mkdirSync(destRoot, { recursive: true });
      if (fs.existsSync(dest)) {
        vscode.window.showErrorMessage(`目标已存在同名技能目录：${dirName}`);
        return;
      }
      fs.cpSync(src, dest, { recursive: true });
      vscode.window.showInformationMessage(`已导入 Claude Code 技能：${dirName}`);
      await this._postMessage({ type: 'claudeCodeSkillImported', payload: { name: dirName } });
      await this._loadClaudeCodeSkills();
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillManagement] Claude import failed: ${error.message}`);
      await this._postMessage({ type: 'error', payload: error.message || String(error) });
    }
  }

  private _openSkillFolder(skillPath: string): void {
    if (fs.existsSync(skillPath)) {
      const uri = vscode.Uri.file(skillPath);
      vscode.commands.executeCommand('revealInExplorer', uri);
    }
  }

  private async _postMessage(message: { type: string; payload?: any }): Promise<void> {
    await this._webview.postMessage(message);
  }

  private _getHtmlForWebview(webview: vscode.Webview): string {
    const scriptPath = path.join(this._extensionUri.fsPath, 'out', 'webview', 'skillMarketplace.js');
    const scriptUri = webview.asWebviewUri(vscode.Uri.file(scriptPath));

    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Skill Marketplace</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { height: 100vh; overflow: auto; }
    #root { min-height: 100vh; }
  </style>
</head>
<body>
  <div id="root"></div>
  <script src="${scriptUri}"></script>
</body>
</html>`;
  }
}
