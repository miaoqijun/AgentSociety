import * as React from 'react';
import {
  Form,
  Input,
  InputNumber,
  Tabs,
  Typography,
} from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import type { FormInstance } from 'antd';
import type { TFunction } from 'i18next';
import type { VscodeThemePalette } from '../theme';
import type { ClaudeCodeCliStatus, ClaudeCodeConfigValues } from './claudeCodeTypes';
import type { ValidationState, EasyPaperConfigValues } from './types';
import { ClaudeCodeConfigSection } from './ClaudeCodeConfigSection';
import { EasyPaperConfigSection } from './EasyPaperConfigSection';
import { ValidationAction } from './ValidationAction';
import { tabBodyStyle } from './configPageStyles';
import {
  type AdvancedValidationKey,
  getAdvancedItemVisualStatus,
  getClaudeConfigVisualStatus,
  statusColor,
} from './advancedValidation';

const { Text } = Typography;

export type AdvancedTopTab = 'models' | 'python' | 'literature' | 'claude' | 'easypaper';

type SpecializedLlmKind = 'coder' | 'nano' | 'analysis' | 'embedding';

export interface AdvancedConfigSectionProps {
  t: TFunction;
  palette: VscodeThemePalette;
  hasDefaultLlmKey: boolean;
  defaultLlmApiBase: string;
  defaultLlmModel: string;
  activeTopTab: AdvancedTopTab;
  onActiveTopTabChange: (tab: AdvancedTopTab) => void;
  validationState: Record<string, ValidationState>;
  validateDisabledByKind: Record<SpecializedLlmKind, string | null>;
  pythonValidateDisabledReason: string | null;
  literatureValidateDisabledReason: string | null;
  claudeValidateDisabledReason: string | null;
  onValidate: (llmType: string) => void;
  pythonSectionRef: React.RefObject<HTMLDivElement | null>;
  literatureSectionRef: React.RefObject<HTMLDivElement | null>;
  claudeSectionRef: React.RefObject<HTMLDivElement | null>;
  claudeForm: FormInstance<ClaudeCodeConfigValues>;
  claudeCliStatus: ClaudeCodeCliStatus;
  claudeSettingsPath: string;
  onResetClaude: () => void;
  // EasyPaper
  easyPaperForm: FormInstance<EasyPaperConfigValues>;
  defaultLlmApiKey: string;
  onSaveEasyPaper: () => void;
}

const MODEL_TAB_KEYS: SpecializedLlmKind[] = ['coder', 'nano', 'analysis', 'embedding'];

export const AdvancedConfigSection: React.FC<AdvancedConfigSectionProps> = ({
  t,
  palette,
  hasDefaultLlmKey,
  defaultLlmApiBase,
  defaultLlmModel,
  activeTopTab,
  onActiveTopTabChange,
  validationState,
  validateDisabledByKind,
  pythonValidateDisabledReason,
  literatureValidateDisabledReason,
  claudeValidateDisabledReason,
  onValidate,
  pythonSectionRef,
  literatureSectionRef,
  claudeSectionRef,
  claudeForm,
  claudeCliStatus,
  claudeSettingsPath,
  onResetClaude,
  easyPaperForm,
  defaultLlmApiKey,
  onSaveEasyPaper,
}) => {
  const linkedKeyPlaceholder = t('configPage.linkedPlaceholders.apiKey', {
    status: hasDefaultLlmKey
      ? t('configPage.linkedPlaceholders.configured')
      : t('configPage.linkedPlaceholders.notConfigured'),
  });
  const linkedBasePlaceholder = t('configPage.linkedPlaceholders.apiBase', {
    base: defaultLlmApiBase,
  });

  const blockedByKind: Record<AdvancedValidationKey, string | null> = {
    coder: validateDisabledByKind.coder,
    nano: validateDisabledByKind.nano,
    analysis: validateDisabledByKind.analysis,
    embedding: validateDisabledByKind.embedding,
    python: pythonValidateDisabledReason,
    literature: literatureValidateDisabledReason,
  };

  const tabLabelWithStatus = (label: string, kind: AdvancedValidationKey) => {
    const blocked = blockedByKind[kind];
    const visual = getAdvancedItemVisualStatus(validationState[kind], blocked);
    const dotColor = statusColor(visual, palette);
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: dotColor,
            flexShrink: 0,
          }}
        />
        {label}
      </span>
    );
  };

  const getDisabledReason = (kind: AdvancedValidationKey) => blockedByKind[kind];

  const getValidateLabel = (kind: AdvancedValidationKey) => {
    if (kind === 'literature') {
      return t('configPage.literature.validateConfig');
    }
    return t('configPage.validate');
  };

  const renderValidationAction = (kind: AdvancedValidationKey) => (
    <ValidationAction
      t={t}
      palette={palette}
      state={validationState[kind] ?? { validating: false, valid: null, error: null }}
      disabledReason={getDisabledReason(kind)}
      onValidate={() => onValidate(kind)}
      label={getValidateLabel(kind)}
      size="small"
      primary={false}
    />
  );

  const renderLlmFields = (
    kind: 'coder' | 'nano' | 'analysis',
    hintKey: string,
    fields: { key: string; label: string; placeholder?: string }[]
  ) => (
    <div style={tabBodyStyle}>
      <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
        {t(hintKey)}
      </Text>
      {fields.map((field) => (
        <Form.Item key={field.key} name={field.key} label={field.label} style={{ marginBottom: 12 }}>
          {field.key.includes('ApiKey') ? (
            <Input.Password placeholder={field.placeholder ?? linkedKeyPlaceholder} autoComplete="off" />
          ) : (
            <Input placeholder={field.placeholder} />
          )}
        </Form.Item>
      ))}
      {renderValidationAction(kind)}
    </div>
  );

  const modelsTabVisual = (): ReturnType<typeof getAdvancedItemVisualStatus> => {
    const statuses = MODEL_TAB_KEYS.map((key) =>
      getAdvancedItemVisualStatus(validationState[key], blockedByKind[key])
    );
    if (statuses.some((s) => s === 'validating')) {
      return 'validating';
    }
    if (statuses.every((s) => s === 'ok')) {
      return 'ok';
    }
    if (statuses.some((s) => s === 'error')) {
      return 'error';
    }
    if (statuses.some((s) => s === 'blocked')) {
      return 'blocked';
    }
    return 'idle';
  };

  const modelTabItems = [
    {
      key: 'coder',
      label: tabLabelWithStatus(t('configPage.coder.shortTitle'), 'coder'),
      children: renderLlmFields('coder', 'configPage.coder.hint', [
        { key: 'coderLlmApiKey', label: t('configPage.coder.apiKey') },
        { key: 'coderLlmApiBase', label: t('configPage.coder.apiBase'), placeholder: linkedBasePlaceholder },
        {
          key: 'coderLlmModel',
          label: t('configPage.coder.model'),
          placeholder: t('configPage.coder.modelPlaceholder', { model: defaultLlmModel }),
        },
      ]),
    },
    {
      key: 'nano',
      label: tabLabelWithStatus(t('configPage.advanced.nano.shortTitle'), 'nano'),
      children: renderLlmFields('nano', 'configPage.advanced.nano.hint', [
        { key: 'nanoLlmApiKey', label: t('configPage.advanced.nano.apiKey') },
        { key: 'nanoLlmApiBase', label: t('configPage.advanced.nano.apiBase'), placeholder: linkedBasePlaceholder },
        {
          key: 'nanoLlmModel',
          label: t('configPage.advanced.nano.model'),
          placeholder: t('configPage.advanced.nano.modelPlaceholder', { model: defaultLlmModel }),
        },
      ]),
    },
    {
      key: 'analysis',
      label: tabLabelWithStatus(t('configPage.analysis.shortTitle'), 'analysis'),
      children: renderLlmFields('analysis', 'configPage.analysis.hint', [
        { key: 'analysisLlmApiKey', label: t('configPage.analysis.apiKey') },
        { key: 'analysisLlmApiBase', label: t('configPage.analysis.apiBase'), placeholder: linkedBasePlaceholder },
        {
          key: 'analysisLlmModel',
          label: t('configPage.analysis.model'),
          placeholder: t('configPage.analysis.modelPlaceholder', { model: defaultLlmModel }),
        },
      ]),
    },
    {
      key: 'embedding',
      label: tabLabelWithStatus(t('configPage.advanced.embedding.shortTitle'), 'embedding'),
      children: (
        <div style={tabBodyStyle}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 12, fontSize: 12 }}>
            {t('configPage.advanced.embedding.hint')}
          </Text>
          <Form.Item name="embeddingApiKey" label={t('configPage.advanced.embedding.apiKey')}>
            <Input.Password placeholder={linkedKeyPlaceholder} autoComplete="off" />
          </Form.Item>
          <Form.Item name="embeddingApiBase" label={t('configPage.advanced.embedding.apiBase')}>
            <Input placeholder={linkedBasePlaceholder} />
          </Form.Item>
          <Form.Item name="embeddingModel" label={t('configPage.advanced.embedding.model')}>
            <Input placeholder={t('configPage.advanced.embedding.modelPlaceholder')} />
          </Form.Item>
          <Form.Item name="embeddingDims" label={t('configPage.advanced.embedding.dims')}>
            <InputNumber
              min={64}
              max={4096}
              style={{ width: '100%' }}
              placeholder={t('configPage.advanced.embedding.dimsPlaceholder')}
            />
          </Form.Item>
          {renderValidationAction('embedding')}
        </div>
      ),
    },
  ];

  const topTabItems = [
    {
      key: 'models',
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: statusColor(modelsTabVisual(), palette),
            }}
          />
          {t('configPage.sections.specializedModels')}
        </span>
      ),
      children: (
        <>
          <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 8 }}>
            {t('configPage.sections.inheritHintShort')}
          </Text>
          <Tabs size="small" destroyInactiveTabPane={false} items={modelTabItems} />
        </>
      ),
    },
    {
      key: 'python',
      label: tabLabelWithStatus(t('configPage.python.title'), 'python'),
      children: (
        <div ref={pythonSectionRef} style={tabBodyStyle}>
          <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 12 }}>
            {t('configPage.python.hint')}
          </Text>
          <Form.Item name="pythonPath" label={t('configPage.python.path')}>
            <Input placeholder={t('configPage.python.pathPlaceholder')} />
          </Form.Item>
          {renderValidationAction('python')}
        </div>
      ),
    },
    {
      key: 'literature',
      label: tabLabelWithStatus(t('configPage.literature.title'), 'literature'),
      children: (
        <div ref={literatureSectionRef} style={tabBodyStyle}>
          <Text type="secondary" style={{ display: 'block', fontSize: 12, marginBottom: 12 }}>
            {t('configPage.literature.hint')}
          </Text>
          <Form.Item name="literatureSearchMcpUrl" label={t('configPage.advanced.literature.apiUrl')}>
            <Input placeholder={t('configPage.advanced.literature.apiUrlPlaceholder')} />
          </Form.Item>
          <Form.Item name="literatureSearchApiKey" label={t('configPage.advanced.literature.apiKey')}>
            <Input.Password placeholder={t('configPage.advanced.literature.apiKeyPlaceholder')} autoComplete="off" />
          </Form.Item>
          {renderValidationAction('literature')}
        </div>
      ),
    },
    {
      key: 'claude',
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: '50%',
              background: statusColor(getClaudeConfigVisualStatus(claudeValidateDisabledReason), palette),
            }}
          />
          {t('configPage.overview.claudeCode')}
        </span>
      ),
      children: (
        <div ref={claudeSectionRef}>
          <ClaudeCodeConfigSection
            t={t}
            palette={palette}
            form={claudeForm}
            cliStatus={claudeCliStatus}
            settingsPath={claudeSettingsPath}
            onReset={onResetClaude}
          />
        </div>
      ),
    },
    {
      key: 'easypaper',
      label: (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <FileTextOutlined />
          EasyPaper
        </span>
      ),
      children: (
        <EasyPaperConfigSection
          t={t}
          palette={palette}
          form={easyPaperForm}
          defaultLlmApiKey={defaultLlmApiKey}
          defaultLlmApiBase={defaultLlmApiBase}
          defaultLlmModel={defaultLlmModel}
          onSave={onSaveEasyPaper}
        />
      ),
    },
  ];

  return (
    <Tabs
      activeKey={activeTopTab}
      onChange={(key) => onActiveTopTabChange(key as AdvancedTopTab)}
      items={topTabItems}
      size="middle"
      destroyInactiveTabPane={false}
    />
  );
};
