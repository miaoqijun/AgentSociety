import * as React from 'react';
import {
  ConfigProvider,
  Layout,
  Input,
  Button,
  Card,
  Typography,
  Tag,
  Space,
  Spin,
  Empty,
  message,
  Modal,
  Tooltip,
  List,
  Avatar,
  Radio,
} from 'antd';
import {
  SearchOutlined,
  DownloadOutlined,
  DeleteOutlined,
  FolderOpenOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  GlobalOutlined,
  AppstoreOutlined,
  BookOutlined,
  CodeOutlined,
  ToolOutlined,
  RocketOutlined,
  FileTextOutlined,
  SafetyOutlined,
  ApiOutlined,
  DesktopOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, SkillInfo, InstalledSkill, SkillRegistry, InstallLocation } from './types';
import { useVscodeTheme } from '../theme';
import 'antd/dist/reset.css';

const { Content, Sider } = Layout;
const { Title, Text, Paragraph } = Typography;
const { Search } = Input;

interface SkillMarketplaceAppProps {
  vscode: VSCodeAPI;
}

const categoryIcons: Record<string, React.ReactNode> = {
  document: <FileTextOutlined />,
  research: <SearchOutlined />,
  productivity: <RocketOutlined />,
  development: <CodeOutlined />,
  integration: <ApiOutlined />,
  security: <SafetyOutlined />,
  creative: <BookOutlined />,
  default: <ToolOutlined />,
};

export const SkillMarketplaceApp: React.FC<SkillMarketplaceAppProps> = ({ vscode }) => {
  const { t, i18n } = useTranslation();
  const { isDark, palette, themeConfig } = useVscodeTheme();

  const [registry, setRegistry] = React.useState<SkillRegistry | null>(null);
  const [installedSkills, setInstalledSkills] = React.useState<InstalledSkill[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [searchQuery, setSearchQuery] = React.useState('');
  const [selectedCategory, setSelectedCategory] = React.useState<string>('all');
  const [installLocation, setInstallLocation] = React.useState<InstallLocation>('workspace');
  const [installingSkills, setInstallingSkills] = React.useState<Set<string>>(new Set());

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const msg = event.data;
      if (!msg || !msg.type) return;

      switch (msg.type) {
        case 'registryLoaded':
          setRegistry(msg.payload);
          setIsLoading(false);
          break;
        case 'installedSkillsLoaded':
          setInstalledSkills(msg.payload || []);
          break;
        case 'installComplete':
          const installedSkill: InstalledSkill = msg.payload;
          setInstalledSkills(prev => [...prev, installedSkill]);
          setInstallingSkills(prev => {
            const next = new Set(prev);
            next.delete(installedSkill.id);
            return next;
          });
          message.success(t('skillMarketplace.installSuccess', { name: installedSkill.name }));
          break;
        case 'installFailed':
          const failed = msg.payload;
          setInstallingSkills(prev => {
            const next = new Set(prev);
            next.delete(failed.skillId);
            return next;
          });
          message.error(t('skillMarketplace.installFailed', { error: failed.error }));
          break;
        case 'uninstallComplete':
          const uninstalled = msg.payload;
          setInstalledSkills(prev => prev.filter(s => s.id !== uninstalled.skillId));
          message.success(t('skillMarketplace.uninstallSuccess'));
          break;
        case 'error':
          message.error(msg.payload || t('skillMarketplace.error'));
          setIsLoading(false);
          break;
      }
    };

    window.addEventListener('message', handleMessage);
    vscode.postMessage({ type: 'ready' });

    return () => window.removeEventListener('message', handleMessage);
  }, []);

  const isInstalled = (skillId: string) => installedSkills.some(s => s.id === skillId);
  const isInstalling = (skillId: string) => installingSkills.has(skillId);

  const handleInstall = (skill: SkillInfo) => {
    if (isInstalled(skill.id) || isInstalling(skill.id)) return;
    setInstallingSkills(prev => new Set(prev).add(skill.id));
    vscode.postMessage({
      type: 'installSkill',
      payload: { skill, installLocation }
    });
  };

  const handleUninstall = (skillId: string) => {
    Modal.confirm({
      title: t('skillMarketplace.uninstallConfirmTitle'),
      content: t('skillMarketplace.uninstallConfirmContent'),
      onOk: () => {
        vscode.postMessage({ type: 'uninstallSkill', payload: { skillId } });
      }
    });
  };

  const handleOpenFolder = (skillPath: string) => {
    vscode.postMessage({ type: 'openSkillFolder', payload: { path: skillPath } });
  };

  const handleRefresh = () => {
    setIsLoading(true);
    vscode.postMessage({ type: 'refreshRegistry' });
  };

  const handleInstallLocationChange = (loc: InstallLocation) => {
    setInstallLocation(loc);
    vscode.postMessage({ type: 'setInstallLocation', payload: { location: loc } });
  };

  const filteredSkills = React.useMemo(() => {
    if (!registry?.skills) return [];
    return registry.skills.filter(skill => {
      const matchesSearch = !searchQuery ||
        skill.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        skill.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        skill.tags.some(t => t.toLowerCase().includes(searchQuery.toLowerCase()));
      const matchesCategory = selectedCategory === 'all' || skill.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [registry?.skills, searchQuery, selectedCategory]);

  const skillCategories = React.useMemo(() => {
    if (!registry?.categories) return [];
    return [{ id: 'all', name: 'All', nameZh: '全部', icon: 'appstore' }, ...registry.categories];
  }, [registry?.categories]);

  const getName = (item: { name: string; nameZh?: string }) => {
    return i18n.language === 'zh-CN' && item.nameZh ? item.nameZh : item.name;
  };

  const renderSkillCard = (skill: SkillInfo) => {
    const installed = isInstalled(skill.id);
    const installing = isInstalling(skill.id);

    return (
      <Card
        key={skill.id}
        hoverable
        style={{
          marginBottom: 12,
          background: palette.surfaceMuted,
          border: `1px solid ${palette.panelBorder}`,
        }}
        styles={{ body: { padding: '16px' } }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1 }}>
            <Space align="start">
              <Avatar
                size={40}
                style={{ backgroundColor: palette.buttonBackground }}
                icon={categoryIcons[skill.category] || categoryIcons.default}
              />
              <div>
                <Space>
                  <Text strong style={{ fontSize: 15 }}>{skill.name}</Text>
                  {installed && (
                    <Tag color="success" icon={<CheckCircleOutlined />}>
                      {t('skillMarketplace.installed')}
                    </Tag>
                  )}
                </Space>
                <Paragraph
                  ellipsis={{ rows: 2 }}
                  style={{ margin: '4px 0 8px', color: palette.descriptionForeground }}
                >
                  {getName(skill)}
                </Paragraph>
                <Space size={4} wrap>
                  <Tag color="blue">{skill.author}</Tag>
                  {skill.tags.slice(0, 3).map(tag => (
                    <Tag key={tag} style={{ margin: 0 }}>{tag}</Tag>
                  ))}
                </Space>
              </div>
            </Space>
          </div>
          <Space direction="vertical" align="end">
            {installed ? (
              <Space>
                <Tooltip title={t('skillMarketplace.openFolder')}>
                  <Button
                    type="text"
                    icon={<FolderOpenOutlined />}
                    onClick={() => handleOpenFolder(installedSkills.find(s => s.id === skill.id)?.path || '')}
                  />
                </Tooltip>
                <Tooltip title={t('skillMarketplace.uninstall')}>
                  <Button
                    type="text"
                    danger
                    icon={<DeleteOutlined />}
                    onClick={() => handleUninstall(skill.id)}
                  />
                </Tooltip>
              </Space>
            ) : (
              <Button
                type="primary"
                icon={installing ? <Spin size="small" /> : <DownloadOutlined />}
                onClick={() => handleInstall(skill)}
                disabled={installing}
                loading={installing}
              >
                {installing ? t('skillMarketplace.installing') : t('skillMarketplace.install')}
              </Button>
            )}
          </Space>
        </div>
      </Card>
    );
  };

  return (
    <ConfigProvider theme={themeConfig}>
      <Layout style={{ minHeight: '100vh', background: 'transparent' }}>
        <Content style={{ padding: 20 }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <Title level={3} style={{ margin: 0 }}>
                <AppstoreOutlined style={{ marginRight: 8 }} />
                {t('skillMarketplace.title')}
              </Title>
              <Space>
                <Radio.Group
                  value={installLocation}
                  onChange={e => handleInstallLocationChange(e.target.value)}
                  optionType="button"
                  buttonStyle="solid"
                  size="small"
                >
                  <Radio.Button value="workspace">
                    <DesktopOutlined /> {t('skillMarketplace.workspace')}
                  </Radio.Button>
                  <Radio.Button value="global">
                    <GlobalOutlined /> {t('skillMarketplace.global')}
                  </Radio.Button>
                </Radio.Group>
                <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={isLoading}>
                  {t('skillMarketplace.refresh')}
                </Button>
              </Space>
            </div>

            <div style={{ display: 'flex', gap: 16, marginBottom: 20 }}>
              <Search
                placeholder={t('skillMarketplace.searchPlaceholder')}
                allowClear
                enterButton={<SearchOutlined />}
                size="large"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                style={{ flex: 1 }}
              />
            </div>

            <div style={{ display: 'flex', gap: 16 }}>
              <Sider
                width={200}
                theme={isDark ? 'dark' : 'light'}
                style={{
                  background: palette.surfaceMuted,
                  borderRadius: 8,
                  height: 'fit-content',
                }}
              >
                <div style={{ padding: 12 }}>
                  <Text type="secondary" style={{ fontSize: 12, textTransform: 'uppercase' }}>
                    {t('skillMarketplace.categories')}
                  </Text>
                </div>
                <List
                  dataSource={skillCategories}
                  renderItem={(cat) => (
                    <List.Item
                      onClick={() => setSelectedCategory(cat.id)}
                      style={{
                        padding: '8px 16px',
                        cursor: 'pointer',
                        background: selectedCategory === cat.id
                          ? palette.activeSelectionBackground
                          : 'transparent',
                        borderLeft: selectedCategory === cat.id 
                          ? `3px solid ${palette.buttonBackground}` 
                          : '3px solid transparent',
                      }}
                    >
                      <Space>
                        {categoryIcons[cat.id] || <AppstoreOutlined />}
                        <Text>{getName(cat)}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </Sider>

              <div style={{ flex: 1 }}>
                {isLoading ? (
                  <div style={{ textAlign: 'center', padding: 60 }}>
                    <Spin size="large" />
                    <Text type="secondary" style={{ display: 'block', marginTop: 16 }}>
                      {t('skillMarketplace.loading')}
                    </Text>
                  </div>
                ) : filteredSkills.length === 0 ? (
                  <Empty
                    description={t('skillMarketplace.noSkills')}
                    style={{ padding: 60 }}
                  />
                ) : (
                  <div>
                    <Text type="secondary" style={{ marginBottom: 12, display: 'block' }}>
                      {t('skillMarketplace.skillCount', { count: filteredSkills.length })}
                    </Text>
                    {filteredSkills.map(renderSkillCard)}
                  </div>
                )}
              </div>
            </div>
          </div>
        </Content>
      </Layout>
    </ConfigProvider>
  );
};
