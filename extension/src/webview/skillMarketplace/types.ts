/**
 * 技能管理 Webview 类型定义
 * 
 * 两种 Skill 类型：
 * 1. Agent Skills - Agent 运行时使用，安装到 {workspace}/custom/skills/
 * 2. Claude Code Skills - Claude Code IDE 使用，安装到 .claude/skills/
 */

export interface VSCodeAPI {
  postMessage(message: unknown): void;
  getState(): unknown;
  setState(state: unknown): void;
}

// ============ Agent Skills（后端管理，Agent 运行时） ============

export interface AgentSkill {
  name: string;
  description: string;
  source: 'builtin' | 'custom' | string; // builtin | custom | env:xxx
  enabled: boolean;
  path: string;
  has_skill_md: boolean;
  script: string;
  requires: string[];
}

// ============ Claude Code Skills（IDE 使用） ============

export interface ClaudeCodeSkill {
  name: string;
  path: string;
  hasSkillMd: boolean;
  description?: string;
  files: string[];
  origin: 'workspace' | 'global';
  /** false：目录在 .agentsociety-disabled-skills 保管区，Claude 不会当技能加载 */
  active?: boolean;
}

// ============ Built-in Skills（插件自带，只读） ============

export interface BuiltinSkill {
  name: string;
  path: string;
  hasSkillMd: boolean;
  description?: string;
}

// ============ Marketplace Skills（从 GitHub 仓库获取） ============

export interface SkillCategory {
  id: string;
  name: string;
  nameZh: string;
  icon: string;
}

export interface MarketplaceSkill {
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
  installTarget: 'agent' | 'claudeCode';
}

export type MarketplaceLoadError =
  | { code: 'NO_SKILL_SOURCES'; channel: 'agent' | 'claude' }
  | { code: 'NETWORK'; message: string }
  | { code: 'GITHUB_SOURCE_FAILED'; source: string; message: string };

export interface MarketplaceLoadPayload {
  skills: MarketplaceSkill[];
  errors: MarketplaceLoadError[];
}

export interface MarketplaceChannelsPayload {
  agent: MarketplaceLoadPayload;
  claude: MarketplaceLoadPayload;
}

export interface SkillSource {
  name: string;
  owner: string;
  repo: string;
  branch?: string;
  path?: string;
  skillType: 'agent' | 'claudeCode';
}

// ============ 安装相关 ============

export interface InstalledSkill {
  id: string;
  name: string;
  path: string;
  installedAt: string;
  source?: 'marketplace' | 'local';
  skillType?: 'agent' | 'claudeCode';
}

export interface InstallProgress {
  skillId: string;
  status: 'pending' | 'downloading' | 'installing' | 'completed' | 'failed';
  message?: string;
  error?: string;
}

export interface AgentSkillDetailPayload {
  success: boolean;
  name: string;
  description: string;
  source: string;
  enabled: boolean;
  path: string;
  script: string;
  requires: string[];
  skill_md: string;
}

// ============ 整体状态 ============

export interface SkillManagementState {
  activeTab: 'agent' | 'agentMarketplace' | 'claudeCode' | 'builtin';
  // Agent Skills（后端管理）
  agentSkills: AgentSkill[];
  agentSkillsLoading: boolean;
  // Claude Code Skills
  claudeCodeSkills: ClaudeCodeSkill[];
  claudeCodeSkillsLoading: boolean;
  // Built-in Skills
  builtinSkills: BuiltinSkill[];
  builtinSkillsLoading: boolean;
  // Marketplace
  agentMarketplaceSkills: MarketplaceSkill[];
  claudeCodeMarketplaceSkills: MarketplaceSkill[];
  marketplaceLoading: boolean;
  marketplaceError: string | null;
  // 通用
  isLoading: boolean;
  error: string | null;
}

// ============ 消息类型 ============

export interface ExtensionMessage {
  type:
  | 'ready'
  // Agent Skills
  | 'listAgentSkills'
  | 'enableAgentSkill'
  | 'disableAgentSkill'
  | 'reloadAgentSkill'
  | 'removeAgentSkill'
  | 'fetchAgentSkillDetail'
  | 'fetchLocalSkillMarkdown'
  | 'importAgentSkill'
  | 'importClaudeCodeSkill'
  // Claude Code Skills
  | 'listClaudeCodeSkills'
  | 'openClaudeCodeSkill'
  | 'deleteClaudeCodeSkill'
  // Built-in Skills
  | 'listBuiltinSkills'
  | 'scanAgentSkills'
  | 'refreshMarketplace'
  | 'updateExtensionSkills'
  | 'openAgentSkillDoc'
  | 'openLocalSkillMarkdown'
  // Marketplace
  | 'installAgentSkill'
  | 'installClaudeCodeSkill'
  | 'openSkillFolder'
  | 'openExternal'
  | 'openSkillSourcesSettings'
  | 'openClaudeSkillSourcesSettings'
  | 'syncOneClaudeSkillFromVsix'
  | 'setClaudeSkillActive'
  | 'purgeClaudeCodeSkill';
  payload?: unknown;
}

export interface WebviewMessage {
  type:
  // Agent Skills
  | 'agentSkillsLoaded'
  | 'agentSkillEnabled'
  | 'agentSkillDisabled'
  | 'agentSkillReloaded'
  | 'agentSkillRemoved'
  | 'agentSkillImported'
  | 'agentSkillDetailLoaded'
  | 'localSkillMarkdownLoaded'
  | 'skillDetailError'
  // Claude Code Skills
  | 'claudeCodeSkillsLoaded'
  | 'claudeCodeSkillImported'
  | 'claudeCodeSkillDeleted'
  // Built-in Skills
  | 'builtinSkillsLoaded'
  // Marketplace
  | 'marketplaceSkillsLoaded'
  | 'installProgress'
  | 'installComplete'
  | 'installFailed'
  // 通用
  | 'error';
  payload?: unknown;
}
