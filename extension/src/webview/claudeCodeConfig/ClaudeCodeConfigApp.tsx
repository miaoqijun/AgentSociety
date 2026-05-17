import * as React from 'react';
import {
  ConfigProvider,
  Layout,
  Form,
  Input,
  Button,
  Card,
  Typography,
  Space,
  notification,
  Tooltip,
  Tag,
} from 'antd';
import {
  SaveOutlined,
  ReloadOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { VSCodeAPI, ClaudeCodeConfigValues, ClaudeCodeCliStatus } from './types';
import { useVscodeTheme } from '../theme';

const { Content } = Layout;
const { Title, Text } = Typography;

const MODEL_FIELDS = [
  { key: 'model' as const, envVar: 'ANTHROPIC_MODEL', labelKey: 'claudeCodeConfig.defaultModel' },
  { key: 'sonnetModel' as const, envVar: 'ANTHROPIC_DEFAULT_SONNET_MODEL', labelKey: 'claudeCodeConfig.sonnetModel' },
  { key: 'opusModel' as const, envVar: 'ANTHROPIC_DEFAULT_OPUS_MODEL', labelKey: 'claudeCodeConfig.opusModel' },
  { key: 'haikuModel' as const, envVar: 'ANTHROPIC_DEFAULT_HAIKU_MODEL', labelKey: 'claudeCodeConfig.haikuModel' },
];

const DEFAULT_VALUES: ClaudeCodeConfigValues = {
  apiKey: '',
  baseUrl: '',
  model: '',
  sonnetModel: '',
  opusModel: '',
  haikuModel: '',
};

interface ClaudeCodeConfigAppProps {
  vscode: VSCodeAPI;
}

export const ClaudeCodeConfigApp: React.FC<ClaudeCodeConfigAppProps> = ({ vscode }) => {
  const { t } = useTranslation();
  const { palette, isDark, themeConfig } = useVscodeTheme();

  const [form] = Form.useForm<ClaudeCodeConfigValues>();
  const [cliStatus, setCliStatus] = React.useState<ClaudeCodeCliStatus>({ installed: false });
  const [savePath, setSavePath] = React.useState<string>('~/.claude/settings.json');

  // Request initial config on mount
  React.useEffect(() => {
    vscode.postMessage({ command: 'requestConfig' });
  }, [vscode]);

  // Handle messages from the extension
  React.useEffect(() => {
    const handler = (event: MessageEvent) => {
      const message = event.data;
      if (!message || !message.command) return;

      switch (message.command) {
        case 'initialConfig': {
          if (message.config) {
            form.setFieldsValue({
              ...DEFAULT_VALUES,
              ...message.config,
            });
          }
          if (message.settingsPath) {
            setSavePath(message.settingsPath);
          }
          break;
        }
        case 'cliStatus': {
          const status = message.status as ClaudeCodeCliStatus | undefined;
          setCliStatus(status ?? { installed: false });
          break;
        }
        case 'saveResult': {
          if (message.success) {
            notification.success({
              message: t('claudeCodeConfig.saveSuccess'),
              description: t('claudeCodeConfig.saveSuccessDesc'),
            });
          } else {
            notification.error({
              message: t('claudeCodeConfig.saveFailed'),
              description: message.error || '',
            });
          }
          break;
        }
      }
    };

    window.addEventListener('message', handler);
    return () => window.removeEventListener('message', handler);
  }, [form, t]);

  const handleSave = () => {
    form.validateFields().then((values) => {
      if (!values.apiKey) {
        notification.warning({
          message: t('claudeCodeConfig.saveFailed'),
          description: t('claudeCodeConfig.apiKeyRequired'),
        });
        return;
      }
      if (!values.baseUrl) {
        notification.warning({
          message: t('claudeCodeConfig.saveFailed'),
          description: t('claudeCodeConfig.baseUrlRequired'),
        });
        return;
      }
      vscode.postMessage({
        command: 'saveConfig',
        config: values,
      });
    });
  };

  const handleResetDefaults = () => {
    form.setFieldsValue(DEFAULT_VALUES);
  };

  const glassmorphismCard: React.CSSProperties = {
    background: isDark
      ? 'rgba(255, 255, 255, 0.04)'
      : 'rgba(255, 255, 255, 0.6)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    borderRadius: 12,
    border: `1px solid ${isDark ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.06)'}`,
    marginBottom: 16,
  };

  const headerBg = isDark
    ? 'linear-gradient(135deg, rgba(22, 119, 255, 0.12) 0%, rgba(114, 46, 209, 0.12) 100%)'
    : 'linear-gradient(135deg, rgba(22, 119, 255, 0.06) 0%, rgba(114, 46, 209, 0.06) 100%)';

  return (
    <ConfigProvider theme={themeConfig}>
      <Layout style={{ minHeight: '100vh', background: palette.editorBackground }}>
        {/* Header */}
        <div
          style={{
            background: headerBg,
            padding: '20px 24px 16px',
            borderBottom: `1px solid ${palette.panelBorder}`,
          }}
        >
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
            <Title level={3} style={{ color: palette.editorForeground, marginBottom: 4, marginTop: 0 }}>
              {t('claudeCodeConfig.title')}
            </Title>
            <Text style={{ color: palette.descriptionForeground, fontSize: 13 }}>
              {t('claudeCodeConfig.subtitle')}
            </Text>

            {/* CLI Status */}
            <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {cliStatus.installed ? (
                <Tag color="success">
                  {t('claudeCodeConfig.cliDetected', { version: cliStatus.version })}
                </Tag>
              ) : (
                <Tag color="warning">
                  {t('claudeCodeConfig.cliNotInstalled')}
                </Tag>
              )}
            </div>

            {/* Save path */}
            <div style={{ marginTop: 8 }}>
              <Text style={{ color: palette.descriptionForeground, fontSize: 12 }}>
                {t('claudeCodeConfig.savePath')}: <code style={{
                  background: palette.codeBlockBackground,
                  padding: '2px 6px',
                  borderRadius: 4,
                  fontSize: 11,
                }}>{savePath}</code>
              </Text>
            </div>
          </div>
        </div>

        {/* Content */}
        <Content style={{ padding: '20px 24px', maxWidth: 720, margin: '0 auto', width: '100%' }}>
          {/* API Configuration Card */}
          <Card
            title={
              <Space>
                <span style={{ fontSize: 15, fontWeight: 600 }}>{t('claudeCodeConfig.apiConfig')}</span>
                <Tag color="red" style={{ fontSize: 11 }}>{t('claudeCodeConfig.required')}</Tag>
              </Space>
            }
            style={glassmorphismCard}
            styles={{ header: { borderBottom: `1px solid ${palette.panelBorder}` } }}
          >
            <Form form={form} layout="vertical" initialValues={DEFAULT_VALUES}>
              <Form.Item
                name="apiKey"
                label={
                  <Space>
                    <span>{t('claudeCodeConfig.apiConfig')} - API Key</span>
                    <Tooltip title="ANTHROPIC_API_KEY">
                      <QuestionCircleOutlined style={{ color: palette.descriptionForeground }} />
                    </Tooltip>
                  </Space>
                }
                rules={[{ required: true, message: t('claudeCodeConfig.apiKeyRequired') }]}
              >
                <Input.Password
                  placeholder="sk-ant-..."
                  style={{ background: palette.inputBackground, color: palette.inputForeground, borderColor: palette.inputBorder }}
                />
              </Form.Item>

              <Form.Item
                name="baseUrl"
                label={
                  <Space>
                    <span>Base URL</span>
                    <Tooltip title="ANTHROPIC_BASE_URL">
                      <QuestionCircleOutlined style={{ color: palette.descriptionForeground }} />
                    </Tooltip>
                  </Space>
                }
                rules={[{ required: true, message: t('claudeCodeConfig.baseUrlRequired') }]}
              >
                <Input
                  placeholder="https://api.anthropic.com"
                  style={{ background: palette.inputBackground, color: palette.inputForeground, borderColor: palette.inputBorder }}
                />
              </Form.Item>
            </Form>
          </Card>

          {/* Model Mapping Card */}
          <Card
            title={
              <Space>
                <span style={{ fontSize: 15, fontWeight: 600 }}>{t('claudeCodeConfig.modelMapping')}</span>
                <Tag style={{ fontSize: 11 }}>{t('claudeCodeConfig.optional')}</Tag>
                <Tooltip title={t('claudeCodeConfig.modelMappingTip')}>
                  <QuestionCircleOutlined style={{ color: palette.descriptionForeground }} />
                </Tooltip>
              </Space>
            }
            style={glassmorphismCard}
            styles={{ header: { borderBottom: `1px solid ${palette.panelBorder}` } }}
          >
            <Form form={form} layout="vertical">
              {MODEL_FIELDS.map((field) => (
                <Form.Item
                  key={field.key}
                  name={field.key}
                  label={
                    <Space>
                      <span>{t(field.labelKey)}</span>
                      <Tooltip title={field.envVar}>
                        <QuestionCircleOutlined style={{ color: palette.descriptionForeground, fontSize: 12 }} />
                      </Tooltip>
                    </Space>
                  }
                  extra={
                    <Text style={{ color: palette.descriptionForeground, fontSize: 11 }}>
                      {t('claudeCodeConfig.leaveEmpty')}
                    </Text>
                  }
                >
                  <Input
                    placeholder={t('claudeCodeConfig.selectOrManual')}
                    style={{ background: palette.inputBackground, color: palette.inputForeground, borderColor: palette.inputBorder }}
                  />
                </Form.Item>
              ))}
            </Form>
          </Card>

          {/* Spacer for sticky bottom bar */}
          <div style={{ height: 72 }} />
        </Content>

        {/* Sticky Bottom Action Bar */}
        <div
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0,
            right: 0,
            background: isDark
              ? 'rgba(30, 30, 30, 0.85)'
              : 'rgba(255, 255, 255, 0.85)',
            backdropFilter: 'blur(12px)',
            WebkitBackdropFilter: 'blur(12px)',
            borderTop: `1px solid ${palette.panelBorder}`,
            padding: '12px 24px',
            display: 'flex',
            justifyContent: 'center',
            gap: 12,
            zIndex: 100,
          }}
        >
          <Button
            icon={<ReloadOutlined />}
            onClick={handleResetDefaults}
          >
            {t('claudeCodeConfig.resetDefaults')}
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            style={{ minWidth: 120 }}
          >
            {t('claudeCodeConfig.save')}
          </Button>
        </div>
      </Layout>
    </ConfigProvider>
  );
};
