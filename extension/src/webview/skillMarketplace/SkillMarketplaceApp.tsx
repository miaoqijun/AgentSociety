import * as React from 'react';
import {
  ConfigProvider, Layout, Input, Button, Card, Typography, Tag, Space, Spin, Empty,
  message, Modal, Tooltip, Tabs, Switch, Collapse, Divider, Alert,
} from 'antd';
import {
  SearchOutlined, DownloadOutlined, DeleteOutlined, FolderOpenOutlined,
  ReloadOutlined, CheckCircleOutlined, AppstoreOutlined, BookOutlined,
  ToolOutlined, RobotOutlined, ThunderboltOutlined, ShopOutlined,
  SyncOutlined, ImportOutlined, InboxOutlined, CloudSyncOutlined, SettingOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type {
  VSCodeAPI, MarketplaceSkill, AgentSkill, ClaudeCodeSkill, BuiltinSkill, AgentSkillDetailPayload,
  MarketplaceLoadError, MarketplaceLoadPayload,
} from './types';
import { useVscodeTheme } from '../theme';
import 'antd/dist/reset.css';

const { Content } = Layout;
const { Title, Text } = Typography;
const { Search } = Input;
const { Panel } = Collapse;

interface SkillManagementAppProps { vscode: VSCodeAPI; }
type SkillTab = 'agent' | 'claudeCode';

type SkillDetailCollapseProps = {
  panelLabel: string;
  onPanelOpen?: () => void;
  loading: boolean;
  borderColor: string;
  children: React.ReactNode;
};

const SkillDetailCollapse: React.FC<SkillDetailCollapseProps> = ({
  panelLabel,
  onPanelOpen,
  loading,
  borderColor,
  children,
}) => (
  <Collapse
    ghost
    size="small"
    style={{ marginTop: 8, borderTop: `1px solid ${borderColor}`, paddingTop: 8 }}
    onChange={(keys) => {
      const arr = Array.isArray(keys) ? keys : keys != null ? [keys as string] : [];
      if (arr.includes('detail')) {
        onPanelOpen?.();
      }
    }}
    items={[
      {
        key: 'detail',
        forceRender: true,
        label: <span style={{ fontSize: 12 }}>{panelLabel}</span>,
        children: loading ? (
          <div style={{ padding: 8 }}>
            <Spin size="small" />
          </div>
        ) : (
          children
        ),
      },
    ]}
  />
);

export const SkillMarketplaceApp: React.FC<SkillManagementAppProps> = ({ vscode }) => {
  const { t, i18n } = useTranslation();
  const { palette, themeConfig } = useVscodeTheme();
  const [activeTab, setActiveTab] = React.useState<SkillTab>('agent');
  const [agentSkills, setAgentSkills] = React.useState<AgentSkill[]>([]);
  const [agentSkillsLoading, setAgentSkillsLoading] = React.useState(false);
  const [claudeCodeSkills, setClaudeCodeSkills] = React.useState<ClaudeCodeSkill[]>([]);
  const [claudeCodeSkillsLoading, setClaudeCodeSkillsLoading] = React.useState(false);
  const [builtinSkills, setBuiltinSkills] = React.useState<BuiltinSkill[]>([]);
  const [builtinSkillsLoading, setBuiltinSkillsLoading] = React.useState(false);
  const [marketplaceSkills, setMarketplaceSkills] = React.useState<MarketplaceSkill[]>([]);
  const [marketplaceLoading, setMarketplaceLoading] = React.useState(false);
  const [marketplaceLoadErrors, setMarketplaceLoadErrors] = React.useState<MarketplaceLoadError[]>([]);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [installingSkills, setInstallingSkills] = React.useState<Set<string>>(new Set());
  const [agentSkillDetails, setAgentSkillDetails] = React.useState<Record<string, AgentSkillDetailPayload>>({});
  const [agentDetailLoading, setAgentDetailLoading] = React.useState<Record<string, boolean>>({});
  const [localMdByPath, setLocalMdByPath] = React.useState<Record<string, string | null>>({});
  const [localMdLoading, setLocalMdLoading] = React.useState<Record<string, boolean>>({});

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const msg = event.data;
      if (!msg || !msg.type) return;
      switch (msg.type) {
        case 'agentSkillsLoaded':
          setAgentSkills(msg.payload || []);
          setAgentSkillsLoading(false);
          break;
        case 'agentSkillEnabled':
        case 'agentSkillDisabled':
        case 'agentSkillReloaded':
          message.success(msg.payload?.message || t('skillManagement.operationSuccess'));
          vscode.postMessage({ type: 'listAgentSkills' });
          break;
        case 'agentSkillImported':
          message.success(t('skillManagement.importSuccess'));
          vscode.postMessage({ type: 'listAgentSkills' });
          break;
        case 'agentSkillRemoved':
          message.success(msg.payload?.message || t('skillManagement.removeAgentSuccess'));
          break;
        case 'claudeCodeSkillImported':
          message.success(t('skillManagement.importClaudeSuccess'));
          break;
        case 'claudeCodeSkillsLoaded':
          setClaudeCodeSkills(msg.payload || []);
          setClaudeCodeSkillsLoading(false);
          break;
        case 'claudeCodeSkillDeleted':
          message.success(t('skillManagement.deleteSuccess'));
          break;
        case 'builtinSkillsLoaded':
          setBuiltinSkills(msg.payload || []);
          setBuiltinSkillsLoading(false);
          break;
        case 'agentSkillDetailLoaded': {
          const p = msg.payload as AgentSkillDetailPayload;
          setAgentDetailLoading((l) => {
            const n = { ...l };
            delete n[p.name];
            return n;
          });
          setAgentSkillDetails((d) => ({ ...d, [p.name]: p }));
          break;
        }
        case 'localSkillMarkdownLoaded': {
          const p = msg.payload as { path: string; content: string };
          setLocalMdLoading((l) => {
            const n = { ...l };
            delete n[p.path];
            return n;
          });
          setLocalMdByPath((d) => ({ ...d, [p.path]: p.content }));
          break;
        }
        case 'skillDetailError': {
          const p = msg.payload as { key: string; error: string };
          const { key } = p;
          if (key.startsWith('agent:')) {
            const name = key.slice('agent:'.length);
            setAgentDetailLoading((l) => {
              const n = { ...l };
              delete n[name];
              return n;
            });
          } else if (key.startsWith('path:')) {
            const dirPath = key.slice('path:'.length);
            setLocalMdLoading((l) => {
              const n = { ...l };
              delete n[dirPath];
              return n;
            });
          }
          message.error(p.error || t('skillManagement.detailLoadFailed'));
          break;
        }
        case 'marketplaceSkillsLoaded': {
          const p = msg.payload as MarketplaceLoadPayload;
          setMarketplaceSkills(p.skills ?? []);
          setMarketplaceLoadErrors(p.errors ?? []);
          setMarketplaceLoading(false);
          break;
        }
        case 'installProgress':
          if (msg.payload?.status === 'downloading' || msg.payload?.status === 'installing') {
            setInstallingSkills(prev => new Set(prev).add(msg.payload.skillId));
          }
          break;
        case 'installComplete':
          setInstallingSkills(prev => { const next = new Set(prev); next.delete(msg.payload.skillId); return next; });
          message.success(t('skillManagement.installSuccess', { name: msg.payload.name }));
          if (msg.payload.skillType === 'agent') {
            vscode.postMessage({ type: 'listAgentSkills' });
          } else {
            vscode.postMessage({ type: 'listClaudeCodeSkills' });
          }
          break;
        case 'installFailed':
          setInstallingSkills(prev => { const next = new Set(prev); next.delete(msg.payload.skillId); return next; });
          message.error(t('skillManagement.installFailed', { error: msg.payload.error }));
          break;
        case 'error':
          message.error(msg.payload || t('skillManagement.error'));
          setAgentSkillsLoading(false);
          setClaudeCodeSkillsLoading(false);
          setBuiltinSkillsLoading(false);
          setMarketplaceLoading(false);
          break;
      }
    };
    window.addEventListener('message', handleMessage);
    setMarketplaceLoading(true);
    vscode.postMessage({ type: 'ready' });
    vscode.postMessage({ type: 'listAgentSkills' });
    vscode.postMessage({ type: 'listClaudeCodeSkills' });
    vscode.postMessage({ type: 'listBuiltinSkills' });
    return () => window.removeEventListener('message', handleMessage);
  }, []);

  // Agent Skills 操作
  const handleToggleAgentSkill = (skill: AgentSkill) => {
    vscode.postMessage({ type: skill.enabled ? 'disableAgentSkill' : 'enableAgentSkill', payload: { name: skill.name } });
  };
  const handleReloadAgentSkill = (name: string) => vscode.postMessage({ type: 'reloadAgentSkill', payload: { name } });
  const handleRemoveAgentSkill = (name: string) => {
    Modal.confirm({
      title: t('skillManagement.deleteConfirmTitle'),
      content: t('skillManagement.deleteConfirmContent', { name }),
      okType: 'danger',
      onOk: () => vscode.postMessage({ type: 'removeAgentSkill', payload: { name } }),
    });
  };
  const handleImportAgentSkill = () => vscode.postMessage({ type: 'importAgentSkill' });
  const handleImportClaudeCodeSkill = () => vscode.postMessage({ type: 'importClaudeCodeSkill' });
  const handleScanAgentSkills = () => vscode.postMessage({ type: 'scanAgentSkills' });
  const handleRefreshAgentList = () => {
    setAgentSkillsLoading(true);
    vscode.postMessage({ type: 'listAgentSkills' });
  };
  const handleRefreshClaudeList = () => {
    setClaudeCodeSkillsLoading(true);
    vscode.postMessage({ type: 'listClaudeCodeSkills' });
  };
  const handleUpdateExtensionSkills = () => vscode.postMessage({ type: 'updateExtensionSkills' });
  const handleOpenAgentSkillDoc = (skill: AgentSkill) => {
    vscode.postMessage({
      type: 'openAgentSkillDoc',
      payload: { skillName: skill.name, skillPath: skill.path, isBuiltin: skill.source === 'builtin' }
    });
  };
  const handleOpenLocalSkillMarkdown = (skillDir: string) => {
    vscode.postMessage({ type: 'openLocalSkillMarkdown', payload: { skillDir } });
  };

  // Claude Code Skills 操作
  const handleDeleteClaudeCodeSkill = (name: string) => {
    Modal.confirm({
      title: t('skillManagement.deleteConfirmTitle'),
      content: t('skillManagement.deleteConfirmContent', { name }),
      onOk: () => vscode.postMessage({ type: 'deleteClaudeCodeSkill', payload: { name } }),
    });
  };

  // Marketplace
  const isInstalling = (id: string) => installingSkills.has(id);
  const handleInstall = (skill: MarketplaceSkill, target: 'agent' | 'claudeCode') => {
    if (isInstalling(skill.id)) return;
    setInstallingSkills(prev => new Set(prev).add(skill.id));
    vscode.postMessage({ type: target === 'agent' ? 'installAgentSkill' : 'installClaudeCodeSkill', payload: { skill } });
  };
  const handleOpenFolder = (path: string) => vscode.postMessage({ type: 'openSkillFolder', payload: { path } });
  const handleRefreshMarketplace = () => { setMarketplaceLoading(true); vscode.postMessage({ type: 'refreshMarketplace' }); };
  const handleOpenSkillSourcesSettings = () => {
    vscode.postMessage({ type: 'openSkillSourcesSettings' });
  };

  const formatMpError = (e: MarketplaceLoadError): string => {
    switch (e.code) {
      case 'NO_SKILL_SOURCES':
        return t('skillManagement.marketplaceErr.noSources');
      case 'NETWORK':
        return t('skillManagement.marketplaceErr.network', { message: e.message });
      case 'GITHUB_SOURCE_FAILED':
        return t('skillManagement.marketplaceErr.sourceFailed', { source: e.source, message: e.message });
    }
  };

  const ensureAgentDetail = (name: string) => {
    if (agentSkillDetails[name] || agentDetailLoading[name]) {
      return;
    }
    setAgentDetailLoading((l) => ({ ...l, [name]: true }));
    vscode.postMessage({ type: 'fetchAgentSkillDetail', payload: { name } });
  };

  const ensureLocalSkillMd = (skillDir: string) => {
    if (localMdByPath[skillDir] !== undefined || localMdLoading[skillDir]) {
      return;
    }
    setLocalMdLoading((l) => ({ ...l, [skillDir]: true }));
    vscode.postMessage({ type: 'fetchLocalSkillMarkdown', payload: { skillDir } });
  };

  const tabToolbar = (left: React.ReactNode, right: React.ReactNode) => (
    <div
      style={{
        marginBottom: 16,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 12,
      }}
    >
      <div style={{ flex: '1 1 220px', minWidth: 0 }}>{left}</div>
      <Space wrap size="small" style={{ flex: '0 0 auto', justifyContent: 'flex-end' }}>{right}</Space>
    </div>
  );

  const mdPreviewStyle = React.useMemo(
    (): React.CSSProperties => ({
      maxHeight: 260,
      overflow: 'auto',
      padding: '8px 10px',
      borderRadius: 8,
      background: palette.codeBlockBackground,
      border: `1px solid ${palette.panelBorder}`,
    }),
    [palette.codeBlockBackground, palette.panelBorder]
  );

  // 过滤
  const filteredAgentSkills = React.useMemo(() => {
    if (!searchQuery) return agentSkills;
    return agentSkills.filter(s => s.name.toLowerCase().includes(searchQuery.toLowerCase()) || s.description.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [agentSkills, searchQuery]);

  const filteredClaudeCodeSkills = React.useMemo(() => {
    if (!searchQuery) return claudeCodeSkills;
    const q = searchQuery.toLowerCase();
    return claudeCodeSkills.filter(
      s => s.name.toLowerCase().includes(q) || (s.description ?? '').toLowerCase().includes(q)
    );
  }, [claudeCodeSkills, searchQuery]);

  const filteredMarketplaceSkills = React.useMemo(() => {
    if (!searchQuery) return marketplaceSkills;
    return marketplaceSkills.filter(s => s.name.toLowerCase().includes(searchQuery.toLowerCase()) || s.description.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [marketplaceSkills, searchQuery]);

  const filteredExtensionBundledSkills = React.useMemo(() => {
    const q = searchQuery.toLowerCase();
    if (!q) return builtinSkills;
    return builtinSkills.filter(
      s => s.name.toLowerCase().includes(q) || (s.description ?? '').toLowerCase().includes(q)
    );
  }, [builtinSkills, searchQuery]);

  const agentEnabledCount = React.useMemo(() => agentSkills.filter(s => s.enabled).length, [agentSkills]);
  const agentCustomCount = React.useMemo(() => agentSkills.filter(s => s.source !== 'builtin').length, [agentSkills]);

  const getDescription = (skill: MarketplaceSkill) => {
    const zh = i18n.language === 'zh-CN' && skill.descriptionZh?.trim();
    const text = (zh || skill.description || '').trim();
    return text || t('skillManagement.noDescription');
  };

  const descStyle = React.useMemo(
    (): React.CSSProperties => ({
      margin: '8px 0 0',
      fontSize: 13,
      lineHeight: 1.55,
      whiteSpace: 'normal',
      wordBreak: 'break-word',
      overflowWrap: 'anywhere',
      color: palette.descriptionForeground,
    }),
    [palette.descriptionForeground]
  );

  const renderTabTitle = (icon: React.ReactNode, label: string, badge: string) => (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 10,
        maxWidth: '100%',
        flexWrap: 'wrap',
        lineHeight: 1.5,
      }}
    >
      <span style={{ display: 'inline-flex', alignItems: 'center', flexShrink: 0 }}>{icon}</span>
      <span style={{ flexShrink: 0 }}>{label}</span>
      <Tag style={{ margin: 0, fontSize: 11, lineHeight: '18px', borderRadius: 6 }}>{badge}</Tag>
    </span>
  );

  const cardShell = (key: string, children: React.ReactNode, hoverable?: boolean) => (
    <Card
      key={key}
      hoverable={hoverable}
      style={{
        marginBottom: 12,
        background: palette.surfaceMuted,
        border: `1px solid ${palette.panelBorder}`,
        borderRadius: 10,
        boxShadow: '0 1px 0 rgba(0,0,0,0.04)',
      }}
      styles={{ body: { padding: '14px 16px' } }}
    >
      {children}
    </Card>
  );

  const statPill = (label: string, value: string | number, accent?: string) => (
    <div
      style={{
        flex: '1 1 120px',
        minWidth: 108,
        padding: '10px 14px',
        borderRadius: 10,
        border: `1px solid ${palette.panelBorder}`,
        background: palette.surfaceBackground,
      }}
    >
      <div style={{ fontSize: 11, color: palette.descriptionForeground, marginBottom: 4, letterSpacing: 0.2 }}>{label}</div>
      <div
        style={{
          fontSize: 20,
          fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
          color: accent ?? palette.editorForeground,
          lineHeight: 1.2,
        }}
      >
        {value}
      </div>
    </div>
  );

  const renderAgentSkillCard = (skill: AgentSkill, isBuiltin: boolean) => {
    const detail = agentSkillDetails[skill.name];
    const dLoading = !!agentDetailLoading[skill.name];
    const scriptText = (detail?.script ?? skill.script ?? '').trim();
    const requiresList = (detail?.requires ?? skill.requires ?? []).filter(Boolean);
    const mdBody = (detail?.skill_md ?? '').trim();
    return cardShell(
      skill.name,
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: '1 1 220px', minWidth: 0 }}>
            <Space wrap size={[4, 4]}>
              <Tag color={isBuiltin ? 'blue' : 'green'}>
                {isBuiltin ? t('skillManagement.tagAgentBackend') : t('skillManagement.tagAgentRegistered')}
              </Tag>
              <Text strong style={{ wordBreak: 'break-word' }}>{skill.name}</Text>
              {skill.enabled && <Tag color="success" icon={<CheckCircleOutlined />}>{t('skillManagement.enabled')}</Tag>}
            </Space>
            <div style={descStyle}>{skill.description || t('skillManagement.noDescription')}</div>
          </div>
          <Space wrap style={{ flex: '0 0 auto', justifyContent: 'flex-end' }}>
            <Tooltip title={skill.enabled ? t('skillManagement.disable') : t('skillManagement.enable')}>
              <Switch checked={skill.enabled} onChange={() => handleToggleAgentSkill(skill)} size="small" />
            </Tooltip>
            {!isBuiltin && (
              <Tooltip title={t('skillManagement.reload')}>
                <Button type="text" size="small" icon={<SyncOutlined />} onClick={() => handleReloadAgentSkill(skill.name)} />
              </Tooltip>
            )}
            <Tooltip title={t('skillManagement.viewDocumentation')}>
              <Button type="text" size="small" icon={<BookOutlined />} onClick={() => handleOpenAgentSkillDoc(skill)} />
            </Tooltip>
            <Tooltip title={t('skillManagement.openFolder')}>
              <Button type="text" size="small" icon={<FolderOpenOutlined />} onClick={() => handleOpenFolder(skill.path)} />
            </Tooltip>
            {!isBuiltin && (
              <Tooltip title={t('skillManagement.delete')}>
                <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => handleRemoveAgentSkill(skill.name)} />
              </Tooltip>
            )}
          </Space>
        </div>
        <SkillDetailCollapse
          panelLabel={t('skillManagement.skillDetails')}
          onPanelOpen={() => ensureAgentDetail(skill.name)}
          loading={dLoading && !detail}
          borderColor={palette.panelBorder}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>{t('skillManagement.detailPath')}</Text>
              <div style={{ fontSize: 12, wordBreak: 'break-all', color: palette.editorForeground }}>
                {detail?.path ?? skill.path}
              </div>
            </div>
            {scriptText ? (
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>{t('skillManagement.detailScript')}</Text>
                <div
                  style={{
                    fontSize: 12,
                    fontFamily: 'var(--vscode-editor-font-family, monospace)',
                    wordBreak: 'break-all',
                    color: palette.editorForeground,
                  }}
                >
                  {scriptText}
                </div>
              </div>
            ) : null}
            {requiresList.length > 0 ? (
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                  {t('skillManagement.detailRequires')}
                </Text>
                <Space wrap size={[4, 4]}>
                  {requiresList.map((r) => (
                    <Tag key={r} style={{ margin: 0 }}>{r}</Tag>
                  ))}
                </Space>
              </div>
            ) : null}
            <div>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                {t('skillManagement.detailMarkdown')}
              </Text>
              <div style={mdPreviewStyle}>
                <pre
                  style={{
                    margin: 0,
                    fontSize: 11,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: palette.editorForeground,
                  }}
                >
                  {mdBody || t('skillManagement.detailNoMarkdownBody')}
                </pre>
              </div>
            </div>
          </div>
        </SkillDetailCollapse>
      </div>
    );
  };

  const renderClaudeCodeSkillCard = (skill: ClaudeCodeSkill) => {
    const mdKey = skill.path;
    const mdLoading = !!localMdLoading[mdKey];
    const mdText = localMdByPath[mdKey];
    return cardShell(
      skill.name,
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: '1 1 220px', minWidth: 0 }}>
            <Space wrap size={[4, 4]}>
              <Tag color={skill.origin === 'workspace' ? 'blue' : 'geekblue'}>
                {t(`skillManagement.claudeOrigin.${skill.origin}`)}
              </Tag>
              <Text strong style={{ wordBreak: 'break-word' }}>{skill.name}</Text>
            </Space>
            <div style={descStyle}>{skill.description || t('skillManagement.noDescription')}</div>
          </div>
          <Space wrap style={{ flex: '0 0 auto', justifyContent: 'flex-end' }}>
            {skill.hasSkillMd && (
              <Tooltip title={t('skillManagement.viewDocumentation')}>
                <Button type="text" size="small" icon={<BookOutlined />} onClick={() => handleOpenLocalSkillMarkdown(skill.path)} />
              </Tooltip>
            )}
            <Tooltip title={t('skillManagement.openFolder')}>
              <Button type="text" size="small" icon={<FolderOpenOutlined />} onClick={() => handleOpenFolder(skill.path)} />
            </Tooltip>
            <Tooltip title={t('skillManagement.delete')}>
              <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteClaudeCodeSkill(skill.name)} />
            </Tooltip>
          </Space>
        </div>
        <SkillDetailCollapse
          panelLabel={t('skillManagement.skillDetails')}
          onPanelOpen={() => ensureLocalSkillMd(skill.path)}
          loading={mdLoading && mdText === undefined}
          borderColor={palette.panelBorder}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>{t('skillManagement.detailPath')}</Text>
              <div style={{ fontSize: 12, wordBreak: 'break-all', color: palette.editorForeground }}>{skill.path}</div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                {t('skillManagement.detailFiles')}
              </Text>
              <Text style={{ fontSize: 12 }}>{skill.files.length ? skill.files.join(', ') : '—'}</Text>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                {t('skillManagement.detailMarkdown')}
              </Text>
              <div style={mdPreviewStyle}>
                <pre
                  style={{
                    margin: 0,
                    fontSize: 11,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    color: palette.editorForeground,
                  }}
                >
                  {mdText === undefined ? '' : ((mdText ?? '').trim() || t('skillManagement.detailNoMarkdownBody'))}
                </pre>
              </div>
            </div>
          </div>
        </SkillDetailCollapse>
      </div>
    );
  };

  const renderMarketplaceSkillCard = (skill: MarketplaceSkill) => {
    const installing = isInstalling(skill.id);
    const alreadyInstalledAgent = agentSkills.some(s => s.name === skill.id);
    const alreadyInstalledClaude = claudeCodeSkills.some(s => s.name === skill.id);
    return cardShell(
      skill.id,
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: '1 1 240px', minWidth: 0 }}>
            <Space wrap size={[4, 4]}>
              <Text strong style={{ wordBreak: 'break-word' }}>{skill.name}</Text>
              <Tag color="blue">{skill.author}</Tag>
            </Space>
            <div style={descStyle}>{getDescription(skill)}</div>
            <Space size={4} wrap style={{ marginTop: 8 }}>
              {(skill.tags ?? []).slice(0, 6).map(tag => <Tag key={tag} style={{ margin: 0, fontSize: 11 }}>{tag}</Tag>)}
            </Space>
          </div>
          <Space wrap style={{ flex: '0 0 auto' }}>
            <Button
              type="primary"
              size="small"
              icon={installing ? <Spin size="small" /> : <DownloadOutlined />}
              onClick={() => handleInstall(skill, 'agent')}
              disabled={installing || alreadyInstalledAgent}
              loading={installing}
            >
              {alreadyInstalledAgent ? t('skillManagement.installed') : t('skillManagement.installAgent')}
            </Button>
            <Button
              size="small"
              icon={installing ? <Spin size="small" /> : <DownloadOutlined />}
              onClick={() => handleInstall(skill, 'claudeCode')}
              disabled={installing || alreadyInstalledClaude}
            >
              {alreadyInstalledClaude ? t('skillManagement.installed') : t('skillManagement.installClaudeCode')}
            </Button>
          </Space>
        </div>
        <SkillDetailCollapse
          panelLabel={t('skillManagement.skillDetails')}
          loading={false}
          borderColor={palette.panelBorder}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 12 }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>{t('skillManagement.detailRepo')}</Text>
              <div style={{ wordBreak: 'break-all' }}>{skill.repo}</div>
            </div>
            {(skill.compatibility ?? []).length > 0 ? (
              <div>
                <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 4 }}>
                  {t('skillManagement.detailCompat')}
                </Text>
                <Space wrap size={[4, 4]}>
                  {(skill.compatibility ?? []).map((c) => (
                    <Tag key={c} style={{ margin: 0 }}>{c}</Tag>
                  ))}
                </Space>
              </div>
            ) : null}
            {skill.homepage ? (
              <Button
                type="link"
                size="small"
                style={{ padding: 0, height: 'auto' }}
                onClick={() => vscode.postMessage({ type: 'openExternal', payload: { url: skill.homepage } })}
              >
                {t('skillManagement.viewHomepage')}
              </Button>
            ) : null}
          </div>
        </SkillDetailCollapse>
      </div>,
      true
    );
  };

  const renderExtensionBundledSkillCard = (skill: BuiltinSkill) => {
    const mdKey = skill.path;
    const mdLoading = !!localMdLoading[mdKey];
    const mdText = localMdByPath[mdKey];
    return cardShell(
      skill.name,
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ flex: '1 1 220px', minWidth: 0 }}>
            <Space wrap size={[4, 4]}>
              <Tag color="purple">{t('skillManagement.vsixTemplateTag')}</Tag>
              <Text strong style={{ wordBreak: 'break-word' }}>{skill.name}</Text>
            </Space>
            <div style={descStyle}>{skill.description || t('skillManagement.noDescription')}</div>
          </div>
          <Space wrap style={{ flex: '0 0 auto', justifyContent: 'flex-end' }}>
            {skill.hasSkillMd && (
              <Tooltip title={t('skillManagement.viewDocumentation')}>
                <Button type="text" size="small" icon={<BookOutlined />} onClick={() => handleOpenLocalSkillMarkdown(skill.path)} />
              </Tooltip>
            )}
            <Tooltip title={t('skillManagement.openFolder')}>
              <Button type="text" size="small" icon={<FolderOpenOutlined />} onClick={() => handleOpenFolder(skill.path)} />
            </Tooltip>
          </Space>
        </div>
        <SkillDetailCollapse
          panelLabel={t('skillManagement.skillDetails')}
          onPanelOpen={() => ensureLocalSkillMd(skill.path)}
          loading={mdLoading && mdText === undefined}
          borderColor={palette.panelBorder}
        >
          <div style={mdPreviewStyle}>
            <pre
              style={{
                margin: 0,
                fontSize: 11,
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                color: palette.editorForeground,
              }}
            >
              {mdText === undefined ? '' : ((mdText ?? '').trim() || t('skillManagement.detailNoMarkdownBody'))}
            </pre>
          </div>
        </SkillDetailCollapse>
      </div>
    );
  };

  const sectionPanelHeader = (icon: React.ReactNode, label: string) => (
    <Text strong style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      {icon}
      {label}
    </Text>
  );

  const renderMarketplaceSection = () => (
    <Collapse ghost style={{ marginTop: 16 }}>
      <Panel header={sectionPanelHeader(<ShopOutlined />, t('skillManagement.marketplace'))} key="marketplace">
        <div style={{ marginBottom: 10 }}>
          <Space wrap align="center">
            <Button icon={<ReloadOutlined />} onClick={handleRefreshMarketplace} loading={marketplaceLoading} size="small">
              {t('skillManagement.refresh')}
            </Button>
            <Button icon={<SettingOutlined />} onClick={handleOpenSkillSourcesSettings} size="small">
              {t('skillManagement.openSkillSourcesSettings')}
            </Button>
            <Text type="secondary" style={{ fontSize: 12 }}>{t('skillManagement.marketplaceRefreshHint')}</Text>
          </Space>
        </div>
        {marketplaceLoadErrors.length > 0 && (
          <Alert
            type={filteredMarketplaceSkills.length === 0 ? 'warning' : 'info'}
            showIcon
            style={{ marginBottom: 12 }}
            message={t('skillManagement.marketplaceLoadIssues')}
            description={(
              <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                {marketplaceLoadErrors.map((e, i) => (
                  <li key={i} style={{ marginBottom: 4 }}>{formatMpError(e)}</li>
                ))}
              </ul>
            )}
          />
        )}
        {marketplaceLoading ? (
          <div style={{ textAlign: 'center', padding: 20 }}><Spin /></div>
        ) : filteredMarketplaceSkills.length === 0 ? (
          <Empty description={t('skillManagement.noMarketplaceSkills')}>
            <Button type="primary" size="small" icon={<SettingOutlined />} onClick={handleOpenSkillSourcesSettings}>
              {t('skillManagement.openSkillSourcesSettings')}
            </Button>
          </Empty>
        ) : (
          filteredMarketplaceSkills.map(renderMarketplaceSkillCard)
        )}
      </Panel>
    </Collapse>
  );

  const renderAgentTab = () => {
    const builtinAgentSkills = filteredAgentSkills.filter(s => s.source === 'builtin');
    const customSkills = filteredAgentSkills.filter(s => s.source !== 'builtin');
    return (
      <div>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={t('skillManagement.agentTabIntroTitle')}
          description={t('skillManagement.agentTabIntroBody')}
        />
        {tabToolbar(
          <Text type="secondary" style={{ fontSize: 13 }}>
            {t('skillManagement.agentSkillsCount', { count: filteredAgentSkills.length })}
          </Text>,
          <>
            <Button icon={<SearchOutlined />} onClick={handleScanAgentSkills} size="small">
              {t('skillManagement.scanAgentSkills')}
            </Button>
            <Button icon={<ReloadOutlined />} onClick={handleRefreshAgentList} size="small">
              {t('skillManagement.refreshList')}
            </Button>
            <Button type="primary" icon={<ImportOutlined />} onClick={handleImportAgentSkill} size="small">
              {t('skillManagement.importSkill')}
            </Button>
          </>
        )}
        {agentSkillsLoading ? <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div> : (
          <>
            {builtinAgentSkills.length > 0 && (
              <Collapse defaultActiveKey={['builtin']} ghost>
                <Panel
                  header={sectionPanelHeader(<InboxOutlined />, t('skillManagement.agentBackendSection'))}
                  key="builtin"
                >
                  {builtinAgentSkills.map(s => renderAgentSkillCard(s, true))}
                </Panel>
              </Collapse>
            )}
            {customSkills.length > 0 && (
              <Collapse defaultActiveKey={['custom']} ghost style={{ marginTop: builtinAgentSkills.length > 0 ? 8 : 0 }}>
                <Panel header={sectionPanelHeader(<ToolOutlined />, t('skillManagement.agentRegisteredSection'))} key="custom">
                  {customSkills.map(s => renderAgentSkillCard(s, false))}
                </Panel>
              </Collapse>
            )}
            {filteredAgentSkills.length === 0 && (
              <Empty description={t('skillManagement.noAgentSkills')} style={{ padding: 40 }} />
            )}
          </>
        )}
        {renderMarketplaceSection()}
      </div>
    );
  };

  const renderClaudeCodeTab = () => {
    const wsList = filteredClaudeCodeSkills.filter(s => s.origin === 'workspace');
    const gList = filteredClaudeCodeSkills.filter(s => s.origin === 'global');
    const hasDisk = wsList.length > 0 || gList.length > 0;
    const hasVsixList = filteredExtensionBundledSkills.length > 0;
    const showVsixBlock = hasVsixList || builtinSkillsLoading;
    const hasAnyClaude = hasDisk || showVsixBlock;

    const claudeSubsection = (
      titleKey: string,
      explainKey: string,
      body: React.ReactNode,
      addTopMargin: boolean
    ) => (
      <div style={{ marginTop: addTopMargin ? 20 : 0 }}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 4 }}>{t(titleKey)}</Text>
        <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 10, lineHeight: 1.55 }}>
          {t(explainKey)}
        </Text>
        {body}
      </div>
    );

    return (
      <div>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message={t('skillManagement.claudeTabIntroTitle')}
          description={t('skillManagement.claudeTabIntroBody')}
        />
        {tabToolbar(
          <Text type="secondary" style={{ fontSize: 13 }}>
            {t('skillManagement.claudeCodeSkillsCount', { count: filteredClaudeCodeSkills.length })}
          </Text>,
          <>
            <Button icon={<ReloadOutlined />} onClick={handleRefreshClaudeList} size="small">
              {t('skillManagement.refreshList')}
            </Button>
            <Button icon={<CloudSyncOutlined />} onClick={handleUpdateExtensionSkills} size="small">
              {t('skillManagement.syncExtensionSkills')}
            </Button>
            <Button type="primary" icon={<ImportOutlined />} onClick={handleImportClaudeCodeSkill} size="small">
              {t('skillManagement.importClaudeSkill')}
            </Button>
          </>
        )}
        {claudeCodeSkillsLoading ? <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div> : (
          <>
            {hasAnyClaude ? (
              <Collapse defaultActiveKey={['claudeMerge']} ghost>
                <Panel
                  header={sectionPanelHeader(<ThunderboltOutlined />, t('skillManagement.claudeMergedSection'))}
                  key="claudeMerge"
                >
                  {wsList.length > 0
                    ? claudeSubsection(
                      'skillManagement.claudeWorkspaceSection',
                      'skillManagement.claudeWorkspaceExplain',
                      <>{wsList.map(s => renderClaudeCodeSkillCard(s))}</>,
                      false
                    )
                    : null}
                  {gList.length > 0
                    ? claudeSubsection(
                      'skillManagement.claudeGlobalSection',
                      'skillManagement.claudeGlobalExplain',
                      <>{gList.map(s => renderClaudeCodeSkillCard(s))}</>,
                      wsList.length > 0
                    )
                    : null}
                  {showVsixBlock
                    ? claudeSubsection(
                      'skillManagement.vsixTemplateSection',
                      'skillManagement.vsixTemplateExplain',
                      builtinSkillsLoading ? (
                        <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>
                      ) : (
                        <>{filteredExtensionBundledSkills.map(renderExtensionBundledSkillCard)}</>
                      ),
                      wsList.length > 0 || gList.length > 0
                    )
                    : null}
                </Panel>
              </Collapse>
            ) : (
              <Empty description={t('skillManagement.noClaudeCodeSkills')} style={{ padding: 40 }} />
            )}
          </>
        )}
        {renderMarketplaceSection()}
      </div>
    );
  };

  const heroBorder = palette.panelBorder;
  const heroBg = palette.surfaceBackground;

  return (
    <ConfigProvider theme={themeConfig}>
      <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
        <Content style={{ padding: '20px 22px 28px' }}>
          <div style={{ maxWidth: 1180, margin: '0 auto' }}>
            <div
              style={{
                marginBottom: 20,
                padding: '20px 22px',
                borderRadius: 12,
                border: `1px solid ${heroBorder}`,
                background: heroBg,
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
                <div style={{ flex: '1 1 240px', minWidth: 0 }}>
                  <Title level={4} style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        width: 36,
                        height: 36,
                        borderRadius: 10,
                        background: palette.inactiveSelectionBackground,
                        color: palette.editorForeground,
                      }}
                    >
                      <AppstoreOutlined />
                    </span>
                    {t('skillManagement.title')}
                  </Title>
                  <Text type="secondary" style={{ display: 'block', marginTop: 8, fontSize: 13, lineHeight: 1.55 }}>
                    {t('skillManagement.subtitle')}
                  </Text>
                </div>
                <div style={{ flex: '1 1 320px', display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                  {statPill(t('skillManagement.statEnabledAgent'), agentEnabledCount, palette.successForeground)}
                  {statPill(t('skillManagement.statCustomAgent'), agentCustomCount)}
                  {statPill(t('skillManagement.statMarketplace'), marketplaceSkills.length, palette.linkForeground)}
                  {statPill(t('skillManagement.statClaude'), claudeCodeSkills.length)}
                </div>
              </div>
              <Divider style={{ margin: '16px 0 12px', borderColor: heroBorder }} />
              <Search
                placeholder={t('skillManagement.searchPlaceholder')}
                allowClear
                enterButton
                size="middle"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
            </div>
            <Tabs
              activeKey={activeTab}
              onChange={(key) => setActiveTab(key as SkillTab)}
              tabBarStyle={{ marginBottom: 12 }}
              items={[
                {
                  key: 'agent',
                  label: renderTabTitle(
                    <RobotOutlined />,
                    t('skillManagement.agentSkillsTab'),
                    `${agentEnabledCount}/${agentSkills.length}`
                  ),
                  children: renderAgentTab(),
                },
                {
                  key: 'claudeCode',
                  label: renderTabTitle(
                    <ThunderboltOutlined />,
                    t('skillManagement.claudeCodeSkillsTab'),
                    String(claudeCodeSkills.length)
                  ),
                  children: renderClaudeCodeTab(),
                },
              ]}
            />
          </div>
        </Content>
      </Layout>
    </ConfigProvider>
  );
};