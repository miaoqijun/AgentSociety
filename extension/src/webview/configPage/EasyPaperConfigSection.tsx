import * as React from 'react';
import { Alert, Button, Collapse, Form, Input, Switch, Typography } from 'antd';
import { CopyOutlined, SaveOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../theme';
import type { EasyPaperConfigValues } from './types';
import { tabBodyStyle } from './configPageStyles';

const { Text } = Typography;

const AGENT_NAMES = [
  'paper_parser',
  'template_parser',
  'commander',
  'writer',
  'typesetter',
  'metadata',
  'reviewer',
  'planner',
];

export interface EasyPaperConfigSectionProps {
  t: TFunction;
  palette: VscodeThemePalette;
  form: FormInstance<EasyPaperConfigValues>;
  defaultLlmApiKey: string;
  defaultLlmApiBase: string;
  defaultLlmModel: string;
  onSave: () => void;
}

export const EasyPaperConfigSection: React.FC<EasyPaperConfigSectionProps> = ({
  t,
  palette,
  form,
  defaultLlmApiKey,
  defaultLlmApiBase,
  defaultLlmModel,
  onSave,
}) => {
  const vlmEnabled = Form.useWatch('vlmEnabled', form) ?? false;

  const handleCopyFromAgentSociety = () => {
    form.setFieldsValue({
      llmModelName: defaultLlmModel || '',
      llmApiKey: defaultLlmApiKey || '',
      llmBaseUrl: defaultLlmApiBase || '',
    });
  };

  return (
    <div style={tabBodyStyle}>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16, fontSize: 12 }}
        message={t('easyPaperConfig.infoTitle')}
        description={t('easyPaperConfig.infoDescription')}
      />

      <Form form={form} layout="vertical" component={false}>
        {/* LLM Config */}
        <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 8 }}>
          {t('easyPaperConfig.llmSection')}
          <Text type="secondary" style={{ fontWeight: 400, marginLeft: 8, fontSize: 12 }}>
            {t('easyPaperConfig.llmSectionHint')}
          </Text>
        </Text>

        <div style={{ marginBottom: 12 }}>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={handleCopyFromAgentSociety}
            disabled={!defaultLlmApiKey}
          >
            {t('easyPaperConfig.copyFromAgentSociety')}
          </Button>
          {!defaultLlmApiKey && (
            <Text type="secondary" style={{ fontSize: 11, marginLeft: 8 }}>
              {t('easyPaperConfig.copyDisabled')}
            </Text>
          )}
        </div>

        <Form.Item
          name="llmModelName"
          label={t('easyPaperConfig.modelName')}
          style={{ marginBottom: 10 }}
        >
          <Input placeholder={t('easyPaperConfig.modelNamePlaceholder')} autoComplete="off" />
        </Form.Item>
        <Form.Item
          name="llmApiKey"
          label="API Key"
          style={{ marginBottom: 10 }}
        >
          <Input.Password placeholder={t('easyPaperConfig.apiKeyPlaceholder')} autoComplete="off" />
        </Form.Item>
        <Form.Item
          name="llmBaseUrl"
          label="Base URL"
          style={{ marginBottom: 16 }}
        >
          <Input placeholder={t('easyPaperConfig.baseUrlPlaceholder')} autoComplete="off" />
        </Form.Item>

        {/* VLM Config (optional) */}
        <Collapse
          ghost
          size="small"
          activeKey={vlmEnabled ? ['vlm'] : []}
          onChange={(keys) => {
            form.setFieldValue('vlmEnabled', keys.includes('vlm'));
          }}
          items={[{
            key: 'vlm',
            label: (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                <Switch size="small" checked={vlmEnabled} onChange={(v) => form.setFieldValue('vlmEnabled', v)} />
                <Text strong style={{ fontSize: 13 }}>{t('easyPaperConfig.vlmSection')}</Text>
                <Text type="secondary" style={{ fontSize: 11, fontWeight: 400 }}>
                  {t('easyPaperConfig.vlmOptional')}
                </Text>
              </span>
            ),
            children: (
              <>
                <Form.Item
                  name="vlmModel"
                  label={t('easyPaperConfig.vlmModel')}
                  style={{ marginBottom: 10 }}
                >
                  <Input placeholder={t('easyPaperConfig.vlmModelPlaceholder')} autoComplete="off" />
                </Form.Item>
                <Form.Item
                  name="vlmApiKey"
                  label="API Key"
                  style={{ marginBottom: 10 }}
                >
                  <Input.Password placeholder={t('easyPaperConfig.apiKeyPlaceholder')} autoComplete="off" />
                </Form.Item>
                <Form.Item
                  name="vlmBaseUrl"
                  label="Base URL"
                  style={{ marginBottom: 10 }}
                >
                  <Input placeholder={t('easyPaperConfig.baseUrlPlaceholder')} autoComplete="off" />
                </Form.Item>
              </>
            ),
          }]}
        />

        {/* Save */}
        <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
          <Button type="primary" icon={<SaveOutlined />} onClick={onSave}>
            {t('easyPaperConfig.save')}
          </Button>
          <Text type="secondary" style={{ fontSize: 11, alignSelf: 'center' }}>
            {t('easyPaperConfig.saveHint')}
          </Text>
        </div>
      </Form>
    </div>
  );
};
