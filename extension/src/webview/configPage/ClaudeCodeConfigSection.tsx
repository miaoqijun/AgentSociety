import * as React from 'react';
import { Form, Input, Select, Space, Tag, Tooltip, Typography, Button } from 'antd';
import { QuestionCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../theme';
import type { ClaudeCodeCliStatus, ClaudeCodeConfigValues } from './claudeCodeTypes';
import { CLAUDE_BASE_URL_PRESETS } from './claudeBaseUrlPresets';
import { tabBodyStyle } from './configPageStyles';

const { Text } = Typography;

const MODEL_FIELDS = [
  { key: 'model' as const, envVar: 'ANTHROPIC_MODEL', labelKey: 'claudeCodeConfig.defaultModel' },
  { key: 'sonnetModel' as const, envVar: 'ANTHROPIC_DEFAULT_SONNET_MODEL', labelKey: 'claudeCodeConfig.sonnetModel' },
  { key: 'opusModel' as const, envVar: 'ANTHROPIC_DEFAULT_OPUS_MODEL', labelKey: 'claudeCodeConfig.opusModel' },
  { key: 'haikuModel' as const, envVar: 'ANTHROPIC_DEFAULT_HAIKU_MODEL', labelKey: 'claudeCodeConfig.haikuModel' },
];

export interface ClaudeCodeConfigSectionProps {
  t: TFunction;
  palette: VscodeThemePalette;
  form: FormInstance<ClaudeCodeConfigValues>;
  cliStatus: ClaudeCodeCliStatus;
  settingsPath: string;
  onReset: () => void;
}

const CUSTOM_BASE_URL_PRESET = 'custom';

export const ClaudeCodeConfigSection: React.FC<ClaudeCodeConfigSectionProps> = ({
  t,
  palette,
  form,
  cliStatus,
  settingsPath,
  onReset,
}) => {
  const baseUrlValue = Form.useWatch('baseUrl', form);

  const matchedPresetId = React.useMemo(() => {
    const normalized = (baseUrlValue ?? '').trim();
    return CLAUDE_BASE_URL_PRESETS.find((preset) => preset.url === normalized)?.id ?? CUSTOM_BASE_URL_PRESET;
  }, [baseUrlValue]);

  const presetOptions = React.useMemo(
    () => [
      ...CLAUDE_BASE_URL_PRESETS.map((preset) => ({
        value: preset.id,
        label: t(`claudeCodeConfig.baseUrlPresets.${preset.id}`),
      })),
      { value: CUSTOM_BASE_URL_PRESET, label: t('claudeCodeConfig.baseUrlCustom') },
    ],
    [t],
  );

  const handlePresetChange = (presetId: string) => {
    if (presetId === CUSTOM_BASE_URL_PRESET) {
      form.setFieldValue('baseUrl', '');
      return;
    }
    const preset = CLAUDE_BASE_URL_PRESETS.find((item) => item.id === presetId);
    if (preset) {
      form.setFieldValue('baseUrl', preset.url);
    }
  };

  const baseUrlPlaceholder =
    matchedPresetId === CUSTOM_BASE_URL_PRESET
      ? t('claudeCodeConfig.baseUrlCustomPlaceholder')
      : t('claudeCodeConfig.baseUrlPresetPlaceholder');

  return (
    <div style={tabBodyStyle}>
      <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 12 }}>
        {t('claudeCodeConfig.subtitle')}
      </Text>
      <Space size={8} wrap style={{ marginBottom: 12 }}>
        {cliStatus.installed ? (
          <Tag color="success" style={{ margin: 0 }}>
            {t('claudeCodeConfig.cliDetected', { version: cliStatus.version })}
          </Tag>
        ) : (
          <Tag color="warning" style={{ margin: 0 }}>
            {t('claudeCodeConfig.cliNotInstalled')}
          </Tag>
        )}
      </Space>
      <Text type="secondary" style={{ display: 'block', fontSize: 11, marginBottom: 14 }}>
        {t('claudeCodeConfig.savePath')}:{' '}
        <code
          style={{
            background: palette.codeBlockBackground,
            padding: '2px 6px',
            borderRadius: 4,
            fontSize: 11,
          }}
        >
          {settingsPath}
        </code>
      </Text>

      <Form form={form} layout="vertical" component={false}>
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
          {t('claudeCodeConfig.apiConfig')}
          <Tag color="red" style={{ marginLeft: 8, fontSize: 11 }}>
            {t('claudeCodeConfig.required')}
          </Tag>
        </Text>
        <Form.Item
          name="apiKey"
          label={
            <Space size={4}>
              <span>API Key</span>
              <Tooltip title="ANTHROPIC_AUTH_TOKEN">
                <QuestionCircleOutlined style={{ color: palette.descriptionForeground, fontSize: 12 }} />
              </Tooltip>
            </Space>
          }
          rules={[{ required: true, message: t('claudeCodeConfig.apiKeyRequired') }]}
          style={{ marginBottom: 12 }}
        >
          <Input.Password placeholder={t('claudeCodeConfig.apiKeyPlaceholder')} autoComplete="off" />
        </Form.Item>
        <Form.Item
          label={
            <Space size={4}>
              <span>Base URL</span>
              <Tooltip title="ANTHROPIC_BASE_URL">
                <QuestionCircleOutlined style={{ color: palette.descriptionForeground, fontSize: 12 }} />
              </Tooltip>
            </Space>
          }
          required
          style={{ marginBottom: 16 }}
        >
          <Space.Compact style={{ width: '100%' }}>
            <Select
              value={matchedPresetId}
              options={presetOptions}
              onChange={handlePresetChange}
              style={{ width: 148, flexShrink: 0 }}
              popupMatchSelectWidth={false}
            />
            <Form.Item
              name="baseUrl"
              noStyle
              rules={[{ required: true, message: t('claudeCodeConfig.baseUrlRequired') }]}
              style={{ flex: 1, minWidth: 0 }}
            >
              <Input placeholder={baseUrlPlaceholder} />
            </Form.Item>
          </Space.Compact>
        </Form.Item>

        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
          {t('claudeCodeConfig.modelMapping')}
          <Tooltip title={t('claudeCodeConfig.modelMappingTip')}>
            <QuestionCircleOutlined
              style={{ color: palette.descriptionForeground, fontSize: 12, marginLeft: 6 }}
            />
          </Tooltip>
        </Text>
        {MODEL_FIELDS.map((field) => (
          <Form.Item
            key={field.key}
            name={field.key}
            label={
              <Space size={4}>
                <span>{t(field.labelKey)}</span>
                <Tooltip title={field.envVar}>
                  <QuestionCircleOutlined style={{ color: palette.descriptionForeground, fontSize: 11 }} />
                </Tooltip>
              </Space>
            }
            extra={
              <Text type="secondary" style={{ fontSize: 11 }}>
                {t('claudeCodeConfig.leaveEmpty')}
              </Text>
            }
            style={{ marginBottom: 10 }}
          >
            <Input placeholder={t('claudeCodeConfig.selectOrManual')} />
          </Form.Item>
        ))}
      </Form>
      <Button icon={<ReloadOutlined />} onClick={onReset} style={{ marginTop: 8 }}>
        {t('configPage.resetClaudeDefaults')}
      </Button>
    </div>
  );
};
