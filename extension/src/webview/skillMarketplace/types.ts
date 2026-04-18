/**
 * 技能市场 Webview 类型定义
 */

export interface VSCodeAPI {
  postMessage(message: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
}

export interface SkillCategory {
  id: string;
  name: string;
  nameZh: string;
  icon: string;
}

export interface SkillInfo {
  id: string;
  name: string;
  description: string;
  descriptionZh?: string;
  category: string;
  author: string;
  repo: string;
  branch?: string;
  path: string;
  tags: string[];
  compatibility: string[];
  version?: string;
  homepage?: string;
}

export interface SkillRegistry {
  version: string;
  updated: string;
  categories: SkillCategory[];
  skills: SkillInfo[];
}

export interface InstalledSkill {
  id: string;
  name: string;
  path: string;
  installedAt: string;
}

export interface InstallProgress {
  skillId: string;
  status: 'pending' | 'downloading' | 'installing' | 'completed' | 'failed';
  message?: string;
  error?: string;
}

export type InstallLocation = 'workspace' | 'global';

export interface SkillMarketplaceState {
  registry: SkillRegistry | null;
  installedSkills: InstalledSkill[];
  installLocation: InstallLocation;
  isLoading: boolean;
  error: string | null;
}

export interface ExtensionMessage {
  type: 'ready' | 'installSkill' | 'uninstallSkill' | 'openSkillFolder' | 'openExternal' | 'refreshRegistry' | 'setInstallLocation';
  payload?: unknown;
}

export interface WebviewMessage {
  type: 'registryLoaded' | 'installedSkillsLoaded' | 'installProgress' | 'installComplete' | 'installFailed' | 'uninstallComplete' | 'uninstallFailed' | 'error';
  payload?: unknown;
}
