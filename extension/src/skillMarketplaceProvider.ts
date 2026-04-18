/**
 * 技能市场 Provider
 * 负责加载技能注册表、安装/卸载技能、与 webview 通信
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { execSync } from 'child_process';
import type { SkillInfo, SkillRegistry, InstalledSkill, InstallLocation } from './webview/skillMarketplace/types';

// 默认技能仓库配置
const DEFAULT_SKILL_SOURCES = [
  {
    owner: 'anthropics',
    repo: 'skills',
    branch: 'main',
    skillsPath: 'skills',
    name: 'Anthropic Official Skills',
    nameZh: 'Anthropic 官方技能'
  }
];

// 分类映射
const CATEGORY_MAP: Record<string, { id: string; name: string; nameZh: string }> = {
  'pdf': { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  'docx': { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  'xlsx': { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  'pptx': { id: 'document', name: 'Document Processing', nameZh: '文档处理' },
  'artifacts-builder': { id: 'development', name: 'Development Tools', nameZh: '开发工具' },
  'canvas-design': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'algorithmic-art': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'mcp-builder': { id: 'integration', name: 'Integrations', nameZh: '集成工具' },
  'webapp-testing': { id: 'development', name: 'Development Tools', nameZh: '开发工具' },
  'skill-creator': { id: 'development', name: 'Development Tools', nameZh: '开发工具' },
  'internal-comms': { id: 'productivity', name: 'Productivity', nameZh: '效率工具' },
  'slack-gif-creator': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'brand-guidelines': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
  'theme-factory': { id: 'creative', name: 'Creative Tools', nameZh: '创意工具' },
};

export class SkillMarketplaceProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = 'skillMarketplace';

  private _view?: vscode.WebviewView;
  private readonly _extensionUri: vscode.Uri;
  private readonly _outputChannel: vscode.OutputChannel;
  private _installLocation: InstallLocation = 'workspace';
  private _registry: SkillRegistry | null = null;

  constructor(extensionUri: vscode.Uri, outputChannel: vscode.OutputChannel) {
    this._extensionUri = extensionUri;
    this._outputChannel = outputChannel;
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri]
    };

    webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

    webviewView.webview.onDidReceiveMessage(async (data) => {
      if (!data) return;

      switch (data.type) {
        case 'ready':
          await this._loadRegistry();
          await this._loadInstalledSkills();
          break;
        case 'installSkill':
          await this._installSkill(data.payload.skill, data.payload.installLocation);
          break;
        case 'uninstallSkill':
          await this._uninstallSkill(data.payload.skillId);
          break;
        case 'openSkillFolder':
          this._openSkillFolder(data.payload.path);
          break;
        case 'openExternal':
          vscode.env.openExternal(vscode.Uri.parse(data.payload.url));
          break;
        case 'refreshRegistry':
          this._registry = null;
          await this._loadRegistry();
          break;
        case 'setInstallLocation':
          this._installLocation = data.payload.location;
          break;
      }
    });
  }

  private async _loadRegistry(): Promise<void> {
    try {
      const config = vscode.workspace.getConfiguration('agentSkills');
      const skillSources = config.get<any[]>('skillSources', DEFAULT_SKILL_SOURCES);

      const allSkills: SkillInfo[] = [];
      const categoryMap = new Map<string, { id: string; name: string; nameZh: string }>();

      for (const source of skillSources) {
        const skills = await this._fetchSkillsFromGitHub(source);
        for (const skill of skills) {
          allSkills.push(skill);
          if (skill.category && !categoryMap.has(skill.category)) {
            const catInfo = CATEGORY_MAP[skill.id] || { id: skill.category, name: skill.category, nameZh: skill.category };
            categoryMap.set(skill.category, catInfo);
          }
        }
      }

      // 构建分类列表
      const categories = Array.from(categoryMap.values()).map(cat => ({
        ...cat,
        icon: cat.id === 'document' ? 'file-text' : 
              cat.id === 'development' ? 'code' : 
              cat.id === 'creative' ? 'palette' : 
              cat.id === 'integration' ? 'api' : 'rocket'
      }));

      this._registry = {
        version: '1.0',
        updated: new Date().toISOString().split('T')[0],
        categories,
        skills: allSkills
      };

      await this._postMessage({
        type: 'registryLoaded',
        payload: this._registry
      });
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillMarketplace] Failed to load registry: ${error.message}`);
      
      // Fallback to bundled registry
      const bundledRegistry = await this._loadBundledRegistry();
      if (bundledRegistry) {
        this._registry = bundledRegistry;
        await this._postMessage({
          type: 'registryLoaded',
          payload: bundledRegistry
        });
      } else {
        await this._postMessage({
          type: 'error',
          payload: `Failed to load skill registry: ${error.message}`
        });
      }
    }
  }

  private async _fetchSkillsFromGitHub(source: any): Promise<SkillInfo[]> {
    const { owner, repo, branch, skillsPath } = source;
    const apiUrl = `https://api.github.com/repos/${owner}/${repo}/contents/${skillsPath}?ref=${branch}`;
    
    this._outputChannel.appendLine(`[SkillMarketplace] Fetching skills from: ${apiUrl}`);
    
    const response = await fetch(apiUrl, {
      headers: {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'VSCode-Extension'
      }
    });
    
    if (!response.ok) {
      throw new Error(`GitHub API error: ${response.status} ${response.statusText}`);
    }
    
    const contents = await response.json() as Array<{name: string; type: string; path: string}>;
    const skills: SkillInfo[] = [];
    
    for (const item of contents) {
      if (item.type === 'dir') {
        // 尝试获取 SKILL.md 来读取技能信息
        const skillInfo = await this._fetchSkillInfo(owner, repo, branch, item.path, item.name);
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
  ): Promise<SkillInfo | null> {
    try {
      const skillMdUrl = `https://raw.githubusercontent.com/${owner}/${repo}/${branch}/${skillPath}/SKILL.md`;
      const response = await fetch(skillMdUrl);
      
      if (!response.ok) {
        this._outputChannel.appendLine(`[SkillMarketplace] No SKILL.md for ${skillName}`);
        return null;
      }
      
      const content = await response.text();
      const frontmatter = this._parseFrontmatter(content);
      
      const catInfo = CATEGORY_MAP[skillName] || { id: 'other', name: 'Other', nameZh: '其他' };
      
      return {
        id: skillName,
        name: frontmatter.name || this._formatSkillName(skillName),
        description: frontmatter.description || `Skill for ${skillName}`,
        descriptionZh: frontmatter.descriptionZh || frontmatter.description || `技能：${skillName}`,
        category: catInfo.id,
        author: frontmatter.author || owner,
        repo: `https://github.com/${owner}/${repo}`,
        branch,
        path: skillPath,
        tags: frontmatter.tags || [skillName],
        compatibility: ['claude', 'copilot', 'cursor'],
        version: frontmatter.version || '1.0.0'
      };
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillMarketplace] Error fetching skill info for ${skillName}: ${error.message}`);
      return null;
    }
  }

  private _parseFrontmatter(content: string): Record<string, any> {
    const result: Record<string, any> = {};
    const frontmatterMatch = content.match(/^---\n([\s\S]*?)\n---/);
    
    if (frontmatterMatch) {
      const lines = frontmatterMatch[1].split('\n');
      for (const line of lines) {
        const match = line.match(/^(\w+):\s*(.+)$/);
        if (match) {
          const key = match[1];
          let value: any = match[2].trim();
          
          // 处理数组
          if (value.startsWith('[') && value.endsWith(']')) {
            value = value.slice(1, -1).split(',').map((s: string) => s.trim().replace(/['"]/g, ''));
          } else if (value.startsWith('"') && value.endsWith('"')) {
            value = value.slice(1, -1);
          }
          
          result[key] = value;
        }
      }
    }
    
    return result;
  }

  private _formatSkillName(name: string): string {
    return name
      .split('-')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  private async _loadBundledRegistry(): Promise<SkillRegistry | null> {
    try {
      const registryPath = path.join(this._extensionUri.fsPath, 'resources', 'skill-registry.json');
      if (fs.existsSync(registryPath)) {
        const content = fs.readFileSync(registryPath, 'utf-8');
        return JSON.parse(content);
      }
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillMarketplace] Failed to load bundled registry: ${error.message}`);
    }
    return null;
  }

  private async _loadInstalledSkills(): Promise<void> {
    const installed = this._getInstalledSkills();
    await this._postMessage({
      type: 'installedSkillsLoaded',
      payload: installed
    });
  }

  private _getInstalledSkills(): InstalledSkill[] {
    const skills: InstalledSkill[] = [];
    const workspaceFolder = vscode.workspace.workspaceFolders?.[0];

    // Check workspace skills
    if (workspaceFolder) {
      const workspaceSkillsPath = path.join(workspaceFolder.uri.fsPath, '.claude', 'skills');
      this._scanSkillsDirectory(workspaceSkillsPath, skills);
    }

    // Check global skills
    const globalSkillsPath = path.join(process.env.HOME || process.env.USERPROFILE || '', '.claude', 'skills');
    this._scanSkillsDirectory(globalSkillsPath, skills);

    return skills;
  }

  private _scanSkillsDirectory(dirPath: string, skills: InstalledSkill[]): void {
    if (!fs.existsSync(dirPath)) return;

    try {
      const entries = fs.readdirSync(dirPath, { withFileTypes: true });
      for (const entry of entries) {
        if (entry.isDirectory()) {
          const skillPath = path.join(dirPath, entry.name);
          const skillMdPath = path.join(skillPath, 'SKILL.md');

          if (fs.existsSync(skillMdPath)) {
            const stat = fs.statSync(skillPath);
            skills.push({
              id: entry.name,
              name: entry.name,
              path: skillPath,
              installedAt: stat.birthtime.toISOString()
            });
          }
        }
      }
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillMarketplace] Failed to scan ${dirPath}: ${error.message}`);
    }
  }

  private async _installSkill(skill: SkillInfo, location: InstallLocation): Promise<void> {
    try {
      await this._postMessage({
        type: 'installProgress',
        payload: { skillId: skill.id, status: 'downloading' }
      });

      const targetDir = location === 'workspace'
        ? path.join(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath || '', '.claude', 'skills', skill.id)
        : path.join(process.env.HOME || process.env.USERPROFILE || '', '.claude', 'skills', skill.id);

      if (fs.existsSync(targetDir)) {
        fs.rmSync(targetDir, { recursive: true, force: true });
      }

      fs.mkdirSync(path.dirname(targetDir), { recursive: true });

      await this._postMessage({
        type: 'installProgress',
        payload: { skillId: skill.id, status: 'installing' }
      });

      // Clone the repository
      const repoUrl = skill.repo;
      const branch = skill.branch || 'main';
      const tempDir = path.join(process.env.TMP || '/tmp', `skill-${skill.id}-${Date.now()}`);

      try {
        execSync(`git clone --depth 1 --branch ${branch} ${repoUrl} "${tempDir}"`, {
          encoding: 'utf-8',
          timeout: 60000
        });
      } catch (gitError: any) {
        // Fallback: try to download as zip
        this._outputChannel.appendLine(`[SkillMarketplace] Git clone failed, trying download: ${gitError.message}`);
        await this._downloadSkill(repoUrl, branch, skill.path, tempDir);
      }

      // Copy the skill directory
      const sourcePath = path.join(tempDir, skill.path);
      if (fs.existsSync(sourcePath)) {
        fs.cpSync(sourcePath, targetDir, { recursive: true });
      } else {
        // If path is the root of repo, copy the entire temp dir
        if (skill.path === '.' || skill.path === '' || skill.path === skill.id) {
          fs.cpSync(tempDir, targetDir, { recursive: true });
        } else {
          throw new Error(`Skill path not found: ${sourcePath}`);
        }
      }

      // Cleanup temp directory
      fs.rmSync(tempDir, { recursive: true, force: true });

      const installedSkill: InstalledSkill = {
        id: skill.id,
        name: skill.name,
        path: targetDir,
        installedAt: new Date().toISOString()
      };

      await this._postMessage({
        type: 'installComplete',
        payload: installedSkill
      });

      this._outputChannel.appendLine(`[SkillMarketplace] Successfully installed: ${skill.name}`);
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillMarketplace] Failed to install ${skill.name}: ${error.message}`);

      await this._postMessage({
        type: 'installFailed',
        payload: { skillId: skill.id, error: error.message }
      });
    }
  }

  private async _downloadSkill(repoUrl: string, branch: string, skillPath: string, targetDir: string): Promise<void> {
    const https = require('https');

    // Convert GitHub URL to archive URL
    const archiveUrl = repoUrl.replace('github.com', 'codeload.github.com') + `/tar.gz/${branch}`;

    return new Promise((resolve, reject) => {
      // This is a simplified download - in production you'd want proper tar extraction
      reject(new Error('Download fallback not implemented. Please install git.'));
    });
  }

  private async _uninstallSkill(skillId: string): Promise<void> {
    try {
      const installed = this._getInstalledSkills().find(s => s.id === skillId);
      if (!installed) {
        throw new Error('Skill not found');
      }

      if (fs.existsSync(installed.path)) {
        fs.rmSync(installed.path, { recursive: true, force: true });
      }

      await this._postMessage({
        type: 'uninstallComplete',
        payload: { skillId }
      });

      this._outputChannel.appendLine(`[SkillMarketplace] Successfully uninstalled: ${skillId}`);
    } catch (error: any) {
      this._outputChannel.appendLine(`[SkillMarketplace] Failed to uninstall ${skillId}: ${error.message}`);

      await this._postMessage({
        type: 'uninstallFailed',
        payload: { skillId, error: error.message }
      });
    }
  }

  private _openSkillFolder(skillPath: string): void {
    if (fs.existsSync(skillPath)) {
      const uri = vscode.Uri.file(skillPath);
      vscode.commands.executeCommand('revealInExplorer', uri);
    }
  }

  private async _postMessage(message: { type: string; payload?: any }): Promise<void> {
    if (this._view) {
      await this._view.webview.postMessage(message);
    }
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
