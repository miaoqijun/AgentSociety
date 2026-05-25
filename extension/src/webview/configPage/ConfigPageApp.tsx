import * as React from 'react';
import {
  ConfigProvider,
  Layout,
  Form,
  Input,
  InputNumber,
  Button,
  Card,
  Typography,
  Alert,
  Space,
  notification,
  Collapse,
  Tooltip,
  Tag,
} from 'antd';
import { SaveOutlined, KeyOutlined, CheckCircleOutlined, RocketOutlined, ReloadOutlined, SettingOutlined, LinkOutlined, StopOutlined, CodeOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { ClaudeCodeCliStatus, ClaudeCodeConfigValues } from './claudeCodeTypes';
import { DEFAULT_CLAUDE_BASE_URL } from './claudeBaseUrlPresets';
import type { VSCodeAPI, ConfigValues, WorkspaceInfo, BackendStatus, ValidationState, EasyPaperConfigValues } from './types';
import { AdvancedConfigSection, type AdvancedTopTab } from './AdvancedConfigSection';
import { advancedPanelInnerStyle, glassCardStyle } from './configPageStyles';
import { ValidationAction } from './ValidationAction';
import {
  ADVANCED_VALIDATION_KEYS,
  type AdvancedValidationKey,
  getAdvancedItemVisualStatus,
  getAdvancedKeyFingerprint,
  getAdvancedValidationLabel,
  statusColor,
} from './advancedValidation';
import { useVscodeTheme } from '../theme';
import 'antd/dist/reset.css';

const { Content } = Layout;
const { Title, Text } = Typography;

const DEFAULT_VALUES: ConfigValues = {
  llmApiKey: '',
  backendHost: '127.0.0.1',
  backendPort: 8001,
  pythonPath: '/usr/local/bin/python3',
  llmApiBase: 'https://api.openai.com/v1',
  llmModel: 'gpt-5.4',
  backendLogLevel: 'info',
  coderLlmApiKey: '',
  coderLlmApiBase: 'https://api.openai.com/v1',
  coderLlmModel: '',
  nanoLlmApiKey: '',
  nanoLlmApiBase: 'https://api.openai.com/v1',
  nanoLlmModel: '',
  analysisLlmApiKey: '',
  analysisLlmApiBase: 'https://api.openai.com/v1',
  analysisLlmModel: '',
  embeddingApiKey: '',
  embeddingApiBase: 'https://api.openai.com/v1',
  embeddingModel: 'text-embedding-3-large',
  embeddingDims: 1024,
  literatureSearchMcpUrl: 'https://llmapi.fiblab.net/mcp/',
  literatureSearchApiKey: '',
};

const DEFAULT_CLAUDE_VALUES: ClaudeCodeConfigValues = {
  apiKey: '',
  baseUrl: DEFAULT_CLAUDE_BASE_URL,
  model: '',
  sonnetModel: '',
  opusModel: '',
  haikuModel: '',
  permissionMode: '',
};

const DEFAULT_EASYPAPER_VALUES: EasyPaperConfigValues = {
  llmModelName: '',
  llmApiKey: '',
  llmBaseUrl: '',
  vlmEnabled: false,
  vlmModel: '',
  vlmApiKey: '',
  vlmBaseUrl: '',
};

interface ConfigPageAppProps {
  vscode: VSCodeAPI;
}

export const ConfigPageApp: React.FC<ConfigPageAppProps> = ({ vscode }) => {
  const { t } = useTranslation();
  const { isDark, palette, themeConfig } = useVscodeTheme();
  const [form] = Form.useForm<ConfigValues>();
  const [claudeForm] = Form.useForm<ClaudeCodeConfigValues>();
  const [easyPaperForm] = Form.useForm<EasyPaperConfigValues>();
  const watchedValues = Form.useWatch([], form) as Partial<ConfigValues> | undefined;
  const watchedClaudeValues = Form.useWatch([], claudeForm) as Partial<ClaudeCodeConfigValues> | undefined;
  const currentValues = watchedValues || {};
  const claudeValues = watchedClaudeValues || {};
  const [savedEnvConfig, setSavedEnvConfig] = React.useState<Partial<ConfigValues>>({});
  const [savedClaudeConfig, setSavedClaudeConfig] = React.useState<Partial<ClaudeCodeConfigValues>>({});
  const hasText = (value?: string) => Boolean(value && value.trim());

  const effectiveConfigValues = React.useMemo(
    (): ConfigValues =>
      ({
        ...DEFAULT_VALUES,
        ...savedEnvConfig,
        ...form.getFieldsValue(),
        ...currentValues,
      }) as ConfigValues,
    [currentValues, form, savedEnvConfig]
  );

  const effectiveClaudeValues = React.useMemo(
    (): ClaudeCodeConfigValues =>
      ({
        ...DEFAULT_CLAUDE_VALUES,
        ...savedClaudeConfig,
        ...claudeForm.getFieldsValue(),
        ...claudeValues,
      }) as ClaudeCodeConfigValues,
    [claudeForm, claudeValues, savedClaudeConfig]
  );

  const getConfigValuesForValidation = React.useCallback((): ConfigValues => effectiveConfigValues, [effectiveConfigValues]);

  const getClaudeValuesForValidation = React.useCallback(
    (): ClaudeCodeConfigValues => effectiveClaudeValues,
    [effectiveClaudeValues]
  );
  const defaultLlmModel = (effectiveConfigValues.llmModel || DEFAULT_VALUES.llmModel || '').trim();
  const defaultLlmApiBase = (effectiveConfigValues.llmApiBase || DEFAULT_VALUES.llmApiBase || '').trim();
  const hasDefaultLlmKey = hasText(effectiveConfigValues.llmApiKey);

  const getEffectiveApiKey = (values: Partial<ConfigValues>, llmType: string): string => {
    switch (llmType) {
      case 'coder':
        return (values.coderLlmApiKey || values.llmApiKey || '').trim();
      case 'nano':
        return (values.nanoLlmApiKey || values.llmApiKey || '').trim();
      case 'analysis':
        return (values.analysisLlmApiKey || values.llmApiKey || '').trim();
      case 'embedding':
        return (values.embeddingApiKey || values.llmApiKey || '').trim();
      default:
        return (values.llmApiKey || '').trim();
    }
  };

  const getEffectiveApiBase = (values: Partial<ConfigValues>, llmType: string): string => {
    switch (llmType) {
      case 'coder':
        return (values.coderLlmApiBase || values.llmApiBase || '').trim();
      case 'nano':
        return (values.nanoLlmApiBase || values.llmApiBase || '').trim();
      case 'analysis':
        return (values.analysisLlmApiBase || values.llmApiBase || '').trim();
      case 'embedding':
        return (values.embeddingApiBase || values.llmApiBase || '').trim();
      default:
        return (values.llmApiBase || '').trim();
    }
  };

  const getValidationDisabledReason = (llmType: string, values: Partial<ConfigValues>): string | null => {
    if (llmType === 'default') {
      if (!hasText(values.llmApiKey)) {
        return t('configPage.notifications.apiKeyMissing');
      }
      if (!hasText(values.llmApiBase)) {
        return t('configPage.notifications.apiBaseMissing');
      }
      return null;
    }

    if (llmType === 'literature') {
      return hasText(values.literatureSearchMcpUrl) ? null : t('configPage.validation.literatureUrlRequired');
    }

    const apiKey = getEffectiveApiKey(values, llmType);
    if (!hasText(apiKey)) {
      return t('configPage.validation.needsApiKey');
    }

    const apiBase = getEffectiveApiBase(values, llmType);
    if (!hasText(apiBase)) {
      return t('configPage.validation.needsApiBase');
    }

    return null;
  };

  const defaultValidateDisabledReason = getValidationDisabledReason('default', effectiveConfigValues);
  const coderValidateDisabledReason = getValidationDisabledReason('coder', effectiveConfigValues);
  const nanoValidateDisabledReason = getValidationDisabledReason('nano', effectiveConfigValues);
  const analysisValidateDisabledReason = getValidationDisabledReason('analysis', effectiveConfigValues);
  const embeddingValidateDisabledReason = getValidationDisabledReason('embedding', effectiveConfigValues);
  const pythonValidateDisabledReason = null;
  const literatureValidateDisabledReason = getValidationDisabledReason('literature', effectiveConfigValues);
  const claudeValidateDisabledReason = !hasText(effectiveClaudeValues.apiKey)
    ? t('claudeCodeConfig.apiKeyRequired')
    : !hasText(effectiveClaudeValues.baseUrl)
      ? t('claudeCodeConfig.baseUrlRequired')
      : null;
  const [loading, setLoading] = React.useState(false);
  const [startingBackend, setStartingBackend] = React.useState(false);
  const [workspaceInfo, setWorkspaceInfo] = React.useState<WorkspaceInfo>({ hasWorkspace: false });

  // Validation status for each LLM type
  const [validationState, setValidationState] = React.useState<Record<string, ValidationState>>({
    default: { validating: false, valid: null, error: null },
    coder: { validating: false, valid: null, error: null },
    nano: { validating: false, valid: null, error: null },
    analysis: { validating: false, valid: null, error: null },
    embedding: { validating: false, valid: null, error: null },
    python: { validating: false, valid: null, error: null },
    literature: { validating: false, valid: null, error: null },
  });

  const [backendStatus, setBackendStatus] = React.useState<BackendStatus>({ isRunning: false });
  const [claudeCliStatus, setClaudeCliStatus] = React.useState<ClaudeCodeCliStatus>({ installed: false });
  const [claudeSettingsPath, setClaudeSettingsPath] = React.useState('~/.claude/settings.json');
  const [claudeCodeCustomized, setClaudeCodeCustomized] = React.useState(false);
  const [advancedTopTab, setAdvancedTopTab] = React.useState<AdvancedTopTab>('models');
  const advancedSectionRef = React.useRef<HTMLDivElement>(null);
  const pythonSectionRef = React.useRef<HTMLDivElement>(null);
  const literatureSectionRef = React.useRef<HTMLDivElement>(null);
  const claudeSectionRef = React.useRef<HTMLDivElement>(null);
  const actionsSectionRef = React.useRef<HTMLDivElement>(null);
  const pendingSaveClaudeRef = React.useRef(false);
  const literatureValidateManualRef = React.useRef(false);
  const pendingStartBackendRef = React.useRef(false);
  const advancedKeyPrevFingerprintRef = React.useRef<Partial<Record<AdvancedValidationKey, string>>>({});
  const advancedKeyValidFingerprintRef = React.useRef<Partial<Record<AdvancedValidationKey, string>>>({});
  const defaultValidFingerprintRef = React.useRef<string | null>(null);
  const advancedKeyValidateTimersRef = React.useRef<
    Partial<Record<AdvancedValidationKey, ReturnType<typeof setTimeout>>>
  >({});
  const ADVANCED_CHANGE_VALIDATE_DELAY_MS = 1500;

  const getDefaultLlmFingerprint = React.useCallback(
    () =>
      JSON.stringify({
        llmApiKey: effectiveConfigValues.llmApiKey,
        llmApiBase: effectiveConfigValues.llmApiBase,
        llmModel: effectiveConfigValues.llmModel,
      }),
    [effectiveConfigValues.llmApiBase, effectiveConfigValues.llmApiKey, effectiveConfigValues.llmModel]
  );

  const markValidFingerprint = React.useCallback(
    (kind: string) => {
      if (kind === 'default') {
        defaultValidFingerprintRef.current = getDefaultLlmFingerprint();
        return;
      }
      if ((ADVANCED_VALIDATION_KEYS as readonly string[]).includes(kind)) {
        const key = kind as AdvancedValidationKey;
        advancedKeyValidFingerprintRef.current[key] = getAdvancedKeyFingerprint(
          key,
          effectiveConfigValues
        );
      }
    },
    [effectiveConfigValues, getDefaultLlmFingerprint]
  );

  const isStillValid = React.useCallback(
    (kind: string): boolean => {
      const state = validationState[kind];
      if (state?.valid !== true) {
        return false;
      }
      if (kind === 'default') {
        return defaultValidFingerprintRef.current === getDefaultLlmFingerprint();
      }
      if ((ADVANCED_VALIDATION_KEYS as readonly string[]).includes(kind)) {
        const key = kind as AdvancedValidationKey;
        return (
          advancedKeyValidFingerprintRef.current[key] ===
          getAdvancedKeyFingerprint(key, effectiveConfigValues)
        );
      }
      return false;
    },
    [effectiveConfigValues, getDefaultLlmFingerprint, validationState]
  );

  const scrollToRef = (ref: React.RefObject<HTMLDivElement | null>) => {
    ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  const expandAdvancedConfig = (
    tab: AdvancedTopTab = 'models',
    scrollTarget?: React.RefObject<HTMLDivElement | null>
  ) => {
    setAdvancedTopTab(tab);
    window.setTimeout(() => {
      scrollToRef(scrollTarget ?? advancedSectionRef);
    }, 200);
  };

  const jumpToAdvanced = (tab: AdvancedTopTab = 'models') => {
    const scrollTarget =
      tab === 'python'
        ? pythonSectionRef
        : tab === 'literature'
          ? literatureSectionRef
          : tab === 'claude'
            ? claudeSectionRef
            : advancedSectionRef;
    expandAdvancedConfig(tab, scrollTarget);
  };

  const advancedBlockedByKind = React.useMemo(
    (): Record<AdvancedValidationKey, string | null> => ({
      coder: coderValidateDisabledReason,
      nano: nanoValidateDisabledReason,
      analysis: analysisValidateDisabledReason,
      embedding: embeddingValidateDisabledReason,
      python: pythonValidateDisabledReason,
      literature: literatureValidateDisabledReason,
    }),
    [
      analysisValidateDisabledReason,
      coderValidateDisabledReason,
      embeddingValidateDisabledReason,
      literatureValidateDisabledReason,
      nanoValidateDisabledReason,
      pythonValidateDisabledReason,
    ]
  );

  const claudeCredentialsReady =
    hasText(effectiveClaudeValues.apiKey) && hasText(effectiveClaudeValues.baseUrl);

  const advancedOverview = React.useMemo(() => {
    const totalCount = ADVANCED_VALIDATION_KEYS.length;
    const itemStatuses = ADVANCED_VALIDATION_KEYS.map((key) => ({
      key,
      visual: getAdvancedItemVisualStatus(validationState[key], advancedBlockedByKind[key]),
    }));
    const validCount = itemStatuses.filter((item) => item.visual === 'ok').length;
    const checkedCount = itemStatuses.filter(
      (item) => item.visual === 'ok' || item.visual === 'error'
    ).length;
    const validating = itemStatuses.some((item) => item.visual === 'validating');
    const hasError = itemStatuses.some((item) => item.visual === 'error');

    const summary = validating
      ? t('configPage.advancedValidation.checkingShort', { done: validCount, total: totalCount })
      : checkedCount === 0
        ? t('configPage.advancedValidation.notCheckedShort')
        : t('configPage.advancedValidation.passedShort', { done: validCount, total: totalCount });

    let accent: string | undefined;
    if (validating) {
      accent = palette.linkForeground;
    } else if (validCount >= totalCount) {
      accent = palette.successForeground;
    } else if (hasError) {
      accent = palette.errorForeground;
    } else if (checkedCount === 0) {
      accent = palette.descriptionForeground;
    } else {
      accent = palette.warningForeground;
    }

    const issueItems = itemStatuses.filter(
      (item) => item.visual === 'error' || item.visual === 'blocked'
    );

    const tooltip =
      issueItems.length === 0 ? undefined : (
        <div style={{ maxWidth: 240 }}>
          {issueItems.map((item) => {
            const color = statusColor(item.visual, palette);
            const label = getAdvancedValidationLabel(item.key, t);
            const detail =
              item.visual === 'error'
                ? t('configPage.advancedValidation.statusErrorShort')
                : t('configPage.advancedValidation.statusBlockedShort');
            return (
              <div
                key={item.key}
                style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    background: color,
                    flexShrink: 0,
                  }}
                />
                <Text style={{ color: palette.editorForeground, whiteSpace: 'nowrap' }}>{label}</Text>
                <Text style={{ color }}>{detail}</Text>
              </div>
            );
          })}
        </div>
      );

    return { summary, accent, tooltip };
  }, [advancedBlockedByKind, palette, t, validationState]);

  const claudeOverview = React.useMemo(() => {
    const configured = claudeCredentialsReady || claudeCodeCustomized;
    if (configured) {
      return {
        value: t('configPage.status.configured'),
        accent: palette.successForeground,
        tooltip: t('configPage.overview.claudeConfiguredHint'),
      };
    }
    if (claudeValidateDisabledReason) {
      return {
        value: t('configPage.status.notConfigured'),
        accent: palette.descriptionForeground,
        tooltip: claudeValidateDisabledReason,
      };
    }
    return {
      value: t('configPage.status.default'),
      accent: undefined,
      tooltip: t('configPage.overview.jumpToClaudeCode'),
    };
  }, [
    claudeCodeCustomized,
    claudeCredentialsReady,
    claudeValidateDisabledReason,
    palette,
    t,
  ]);

  const saveDisabledReason = React.useMemo((): string | null => {
    if (!workspaceInfo.hasWorkspace) {
      return t('configPage.noWorkspaceHint');
    }
    if (!hasText(effectiveConfigValues.llmApiKey)) {
      return t('configPage.notifications.apiKeyMissing');
    }
    if (!hasText(effectiveConfigValues.llmApiBase)) {
      return t('configPage.notifications.apiBaseMissing');
    }
    return null;
  }, [effectiveConfigValues.llmApiBase, effectiveConfigValues.llmApiKey, t, workspaceInfo.hasWorkspace]);

  const canSave = !saveDisabledReason;
  const canSaveAndStart = canSave && !startingBackend;

  const resetWorkspaceValidationState = () => {
    for (const key of ADVANCED_VALIDATION_KEYS) {
      const timer = advancedKeyValidateTimersRef.current[key];
      if (timer) {
        clearTimeout(timer);
      }
    }
    advancedKeyValidateTimersRef.current = {};
    advancedKeyPrevFingerprintRef.current = {};
    advancedKeyValidFingerprintRef.current = {};
    defaultValidFingerprintRef.current = null;
    setValidationState({
      default: { validating: false, valid: null, error: null },
      coder: { validating: false, valid: null, error: null },
      nano: { validating: false, valid: null, error: null },
      analysis: { validating: false, valid: null, error: null },
      embedding: { validating: false, valid: null, error: null },
      python: { validating: false, valid: null, error: null },
      literature: { validating: false, valid: null, error: null },
    });
  };

  const handleResetWorkspaceDefaults = () => {
    resetWorkspaceValidationState();
    setSavedEnvConfig({});
    form.setFieldsValue(DEFAULT_VALUES);
    notification.info({
      message: t('configPage.resetWorkspaceDefaults'),
      placement: 'top',
    });
  };

  const handleResetClaudeDefaults = () => {
    setSavedClaudeConfig({});
    claudeForm.setFieldsValue(DEFAULT_CLAUDE_VALUES);
    notification.info({
      message: t('configPage.resetClaudeDefaults'),
      placement: 'top',
    });
  };

  const submitValidation = React.useCallback(
    (llmType: string, values: ConfigValues, options?: { silent?: boolean }) => {
      const silent = options?.silent ?? false;
      const failLocal = (error: string) => {
        setValidationState((prev) => ({
          ...prev,
          [llmType]: { validating: false, valid: false, error },
        }));
        if (!silent) {
          notification.warning({
            message: t('configPage.validationFailed'),
            description: error,
            placement: 'top',
          });
        }
      };

      if (llmType === 'python') {
        setValidationState((prev) => ({
          ...prev,
          python: { validating: true, valid: null, error: null },
        }));
        vscode.postMessage({ command: 'validatePython', config: values });
        return;
      }

      if (['coder', 'nano', 'analysis', 'embedding'].includes(llmType)) {
        const effectiveApiKey = getEffectiveApiKey(values, llmType);
        if (!effectiveApiKey) {
          failLocal(t('configPage.validation.needsApiKey'));
          return;
        }
        const effectiveApiBase = getEffectiveApiBase(values, llmType);
        if (!effectiveApiBase) {
          failLocal(t('configPage.validation.needsApiBase'));
          return;
        }
        setValidationState((prev) => ({
          ...prev,
          [llmType]: { validating: true, valid: null, error: null },
        }));
        vscode.postMessage({ command: 'validateConfig', config: values, llmType });
        return;
      }

      if (llmType === 'default') {
        const missingField = !values.llmApiKey
          ? t('configPage.notifications.apiKeyMissing')
          : !values.llmApiBase
            ? t('configPage.notifications.apiBaseMissing')
            : '';
        if (missingField) {
          failLocal(missingField);
          return;
        }
        setValidationState((prev) => ({
          ...prev,
          default: { validating: true, valid: null, error: null },
        }));
        vscode.postMessage({ command: 'validateConfig', config: values, llmType });
        return;
      }

      if (llmType === 'literature') {
        if (!hasText(values.literatureSearchMcpUrl)) {
          failLocal(t('configPage.validation.literatureUrlRequired'));
          return;
        }
        setValidationState((prev) => ({
          ...prev,
          literature: { validating: true, valid: null, error: null },
        }));
        vscode.postMessage({ command: 'validateLiteratureSearch', config: values });
      }
    },
    [t, vscode]
  );

  const validateAdvancedItem = React.useCallback(
    (key: AdvancedValidationKey, options?: { silent?: boolean; manual?: boolean }) => {
      const silent = options?.silent ?? !options?.manual;
      const manual = options?.manual ?? false;
      if (!manual && isStillValid(key)) {
        return;
      }
      const configValues = getConfigValuesForValidation();
      if (key === 'literature' && manual) {
        literatureValidateManualRef.current = true;
      }
      submitValidation(key, configValues, { silent });
    },
    [getConfigValuesForValidation, isStillValid, submitValidation]
  );

  const validateAllAdvanced = React.useCallback(
    (options?: { manual?: boolean }) => {
      const manual = options?.manual ?? false;
      if (manual) {
        literatureValidateManualRef.current = true;
      }
      for (const key of ADVANCED_VALIDATION_KEYS) {
        if (!manual && isStillValid(key)) {
          continue;
        }
        validateAdvancedItem(key, { silent: true, manual });
      }
    },
    [isStillValid, validateAdvancedItem]
  );

  const handleValidate = (llmType: string) => {
    const configValues = getConfigValuesForValidation();
    if (llmType === 'literature') {
      literatureValidateManualRef.current = true;
    }
    if (ADVANCED_VALIDATION_KEYS.includes(llmType as AdvancedValidationKey)) {
      validateAdvancedItem(llmType as AdvancedValidationKey, { silent: false, manual: true });
      return;
    }
    submitValidation(llmType, configValues, { silent: false });
  };

  const saveClaudeConfig = () => {
    vscode.postMessage({
      command: 'saveClaudeConfig',
      config: getClaudeValuesForValidation(),
    });
  };

  const saveEasyPaperConfig = () => {
    easyPaperForm.validateFields().then((values) => {
      vscode.postMessage({
        command: 'saveEasyPaperConfig',
        config: values,
      });
    }).catch(() => {
      notification.error({
        message: t('easyPaperConfig.validationFailed'),
        placement: 'top',
      });
    });
  };

  const persistClaudeSettingsIfReady = (): boolean => {
    const claude = getClaudeValuesForValidation();
    const hasKey = hasText(claude.apiKey);
    const hasBase = hasText(claude.baseUrl);
    if (!hasKey && !hasBase) {
      pendingSaveClaudeRef.current = false;
      return true;
    }
    if (hasKey && hasBase) {
      pendingSaveClaudeRef.current = true;
      saveClaudeConfig();
      return true;
    }
    pendingSaveClaudeRef.current = false;
    notification.warning({
      message: t('configPage.notifications.saveFailed'),
      description: t('configPage.notifications.claudePartial'),
      placement: 'top',
    });
    return false;
  };

  React.useEffect(() => {
    if (!workspaceInfo.hasWorkspace) {
      return;
    }

    const envValues = getConfigValuesForValidation();

    for (const key of ADVANCED_VALIDATION_KEYS) {
      const fingerprint = getAdvancedKeyFingerprint(key, envValues);
      const prev = advancedKeyPrevFingerprintRef.current[key];
      const validFingerprint = advancedKeyValidFingerprintRef.current[key];

      if (prev === undefined) {
        advancedKeyPrevFingerprintRef.current[key] = fingerprint;
        continue;
      }
      if (prev === fingerprint) {
        continue;
      }

      advancedKeyPrevFingerprintRef.current[key] = fingerprint;

      if (fingerprint === validFingerprint) {
        setValidationState((prevState) => {
          const cur = prevState[key];
          if (cur?.valid === true && !cur.validating && !cur.error) {
            return prevState;
          }
          return {
            ...prevState,
            [key]: { validating: false, valid: true, error: null },
          };
        });
        continue;
      }

      setValidationState((prevState) => {
        const cur = prevState[key];
        if (cur?.valid === null && cur?.validating === false && !cur?.error) {
          return prevState;
        }
        return {
          ...prevState,
          [key]: { validating: false, valid: null, error: null },
        };
      });

      const existingTimer = advancedKeyValidateTimersRef.current[key];
      if (existingTimer) {
        clearTimeout(existingTimer);
      }
      advancedKeyValidateTimersRef.current[key] = setTimeout(() => {
        validateAdvancedItem(key, { silent: true });
      }, ADVANCED_CHANGE_VALIDATE_DELAY_MS);
    }
  }, [
    getConfigValuesForValidation,
    validateAdvancedItem,
    workspaceInfo.hasWorkspace,
  ]);

  React.useEffect(() => {
    return () => {
      for (const key of ADVANCED_VALIDATION_KEYS) {
        const timer = advancedKeyValidateTimersRef.current[key];
        if (timer) {
          clearTimeout(timer);
        }
      }
    };
  }, []);

  React.useEffect(() => {
    vscode.postMessage({ command: 'requestConfig' });
  }, [vscode]);

  React.useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data as { command: string;[key: string]: any };

      if (message.command === 'initialConfig') {
        const config = message.config || {};
        setSavedEnvConfig(config);
        form.setFieldsValue({
          ...DEFAULT_VALUES,
          ...config,
        });
      } else if (message.command === 'initialClaudeConfig') {
        const msg = message as {
          config?: Partial<ClaudeCodeConfigValues>;
          settingsPath?: string;
          cliStatus?: ClaudeCodeCliStatus;
        };
        setSavedClaudeConfig(msg.config || {});
        claudeForm.setFieldsValue({
          ...DEFAULT_CLAUDE_VALUES,
          ...msg.config,
        });
        if (msg.settingsPath) {
          setClaudeSettingsPath(msg.settingsPath);
        }
        if (msg.cliStatus) {
          setClaudeCliStatus(msg.cliStatus);
        }
      } else if (message.command === 'navigateAdvanced') {
        const tab = (message as { tab?: AdvancedTopTab }).tab ?? 'models';
        jumpToAdvanced(tab);
      } else if (message.command === 'workspaceInfo') {
        setWorkspaceInfo(message.workspaceInfo || { hasWorkspace: false });
      } else if (message.command === 'backendStatus') {
        setBackendStatus(message.backendStatus || { isRunning: false });
        if (typeof message.claudeCodeCustomized === 'boolean') {
          setClaudeCodeCustomized(message.claudeCodeCustomized);
        }
      } else if (message.command === 'claudeSaveResult') {
        const msg = message as { success?: boolean; error?: string };
        if (msg.success) {
          setClaudeCodeCustomized(true);
        } else if (msg.error) {
          notification.error({
            message: t('claudeCodeConfig.saveFailed'),
            description: msg.error,
            placement: 'top',
          });
        }
      } else if (message.command === 'initialEasyPaperConfig') {
        const msg = message as { config?: EasyPaperConfigValues };
        easyPaperForm.setFieldsValue({
          ...DEFAULT_EASYPAPER_VALUES,
          ...msg.config,
        });
      } else if (message.command === 'easyPaperSaveResult') {
        const msg = message as { success?: boolean; error?: string };
        if (msg.success) {
          notification.success({
            message: t('easyPaperConfig.saveSuccess'),
            placement: 'top',
          });
        } else if (msg.error) {
          notification.error({
            message: t('easyPaperConfig.saveFailed'),
            description: msg.error,
            placement: 'top',
          });
        }
      } else if (message.command === 'saveResult') {
        const msg = message as { success?: boolean; error?: string };
        setLoading(false);
        if (msg.success) {
          if (pendingStartBackendRef.current) {
            pendingStartBackendRef.current = false;
            vscode.postMessage({
              command: 'startBackend',
              config: form.getFieldsValue(),
            });
          } else {
            notification.success({
              message: t('configPage.notifications.saveSuccess'),
              description: pendingSaveClaudeRef.current
                ? t('configPage.notifications.saveSuccessDescWithClaude')
                : t('configPage.notifications.saveSuccessDesc'),
              placement: 'top',
            });
          }
        } else {
          pendingStartBackendRef.current = false;
          setStartingBackend(false);
          if (msg.error) {
            notification.error({
              message: t('configPage.notifications.saveFailed'),
              description: msg.error,
              placement: 'top',
            });
          }
        }
      } else if (message.command === 'startBackendResult') {
        const msg = message as { success?: boolean; error?: string };
        setStartingBackend(false);
        if (msg.success) {
          notification.success({
            message: t('configPage.notifications.backendStarted', { defaultValue: 'Backend started successfully' }),
            placement: 'top',
          });
          setTimeout(() => {
            vscode.postMessage({ command: 'closeConfigPage' });
          }, 1500);
        } else if (msg.error) {
          notification.error({
            message: t('configPage.notifications.backendStartFailed', { defaultValue: 'Failed to start backend' }),
            description: msg.error,
            placement: 'top',
            duration: 6,
          });
        }
      } else if (message.command === 'validationResult') {
        const msg = message as unknown as { llmType: string; success?: boolean; error?: string };
        setValidationState(prev => ({
          ...prev,
          [msg.llmType]: { validating: false, valid: msg.success ?? false, error: msg.error || null },
        }));
        if (msg.success) {
          markValidFingerprint(msg.llmType);
        }
      } else if (message.command === 'literatureValidationResult') {
        const msg = message as { success?: boolean; error?: string; sources?: Record<string, unknown> };
        setValidationState(prev => ({
          ...prev,
          literature: { validating: false, valid: msg.success ?? false, error: msg.error || null },
        }));
        if (msg.success) {
          markValidFingerprint('literature');
        }
        if (msg.success && msg.sources && literatureValidateManualRef.current) {
          notification.success({
            message: t('configPage.validation.literatureValidateSuccess'),
            description: t('configPage.validation.literatureValidateSuccessDesc', {
              sources: Object.keys(msg.sources).join(', '),
            }),
            placement: 'top',
          });
        }
        literatureValidateManualRef.current = false;
      }
    };

    window.addEventListener('message', handleMessage);
    return () => window.removeEventListener('message', handleMessage);
  }, [claudeForm, form, jumpToAdvanced, markValidFingerprint, t, vscode]);

  const handleSave = async () => {
    if (!workspaceInfo.hasWorkspace) {
      notification.warning({
        message: t('configPage.noWorkspace'),
        description: t('configPage.noWorkspaceHint'),
      });
      return;
    }

    const values = form.getFieldsValue();

    // Require LLM API key/base to save
    if (!values.llmApiKey) {
      notification.warning({
        message: t('configPage.notifications.llmKeyRequired'),
        description: t('configPage.notifications.llmKeyRequiredDesc'),
      });
      return;
    }
    if (!values.llmApiBase) {
      notification.warning({
        message: t('configPage.validationFailed'),
        description: t('configPage.notifications.apiBaseMissing'),
        placement: 'top',
      });
      return;
    }

    setLoading(true);
    if (!persistClaudeSettingsIfReady()) {
      setLoading(false);
      return;
    }
    vscode.postMessage({
      command: 'saveConfig',
      config: values,
    });
  };

  const handleSaveAndStart = async () => {
    if (!workspaceInfo.hasWorkspace) {
      notification.warning({
        message: t('configPage.noWorkspace'),
        description: t('configPage.noWorkspaceHint'),
      });
      return;
    }

    const values = form.getFieldsValue();

    // Require LLM API key
    if (!values.llmApiKey) {
      notification.warning({
        message: t('configPage.notifications.llmKeyRequired'),
        description: t('configPage.notifications.llmKeyRequiredDesc'),
      });
      return;
    }
    if (!values.llmApiBase) {
      notification.warning({
        message: t('configPage.validationFailed'),
        description: t('configPage.notifications.apiBaseMissing'),
        placement: 'top',
      });
      return;
    }

    pendingStartBackendRef.current = true;
    setLoading(true);
    setStartingBackend(true);
    if (!persistClaudeSettingsIfReady()) {
      pendingStartBackendRef.current = false;
      setLoading(false);
      setStartingBackend(false);
      return;
    }
    vscode.postMessage({
      command: 'saveConfig',
      config: values,
    });
  };

  const handleOverviewStartBackend = () => {
    if (backendStatus.isRunning || startingBackend || !canSaveAndStart) {
      return;
    }
    void handleSaveAndStart();
  };

  // 玻璃态样式常量
  const glassStyle = {
    background: isDark
      ? 'rgba(37, 37, 38, 0.75)'
      : 'rgba(255, 255, 255, 0.72)',
    backdropFilter: 'blur(20px)',
    WebkitBackdropFilter: 'blur(20px)',
  };

  // 统计卡片
  const statPill = (
    label: string,
    value: string | number,
    icon: React.ReactNode,
    accent?: string,
    onClick?: () => void,
    tooltipTitle?: React.ReactNode
  ) => {
    const pill = (
      <div
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onClick={onClick}
        onKeyDown={
          onClick
            ? (event) => {
              if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                onClick();
              }
            }
            : undefined
        }
        style={{
          flex: '1 1 100px',
          minWidth: 90,
          padding: '12px 16px',
          borderRadius: 10,
          border: `1px solid ${palette.panelBorder}`,
          background: isDark
            ? 'rgba(37, 37, 38, 0.6)'
            : 'rgba(255, 255, 255, 0.55)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          transition: 'all 0.2s ease',
          cursor: onClick ? 'pointer' : undefined,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <span style={{ color: accent ?? palette.linkForeground }}>{icon}</span>
          <span style={{ fontSize: 11, color: palette.descriptionForeground, fontWeight: 500 }}>{label}</span>
        </div>
        <div style={{ fontSize: 20, fontWeight: 700, color: accent ?? palette.editorForeground, lineHeight: 1 }}>
          {value}
        </div>
      </div>
    );
    if (!tooltipTitle) {
      return pill;
    }
    return <Tooltip title={tooltipTitle}>{pill}</Tooltip>;
  };

  return (
    <ConfigProvider theme={themeConfig}>
      <Layout style={{ minHeight: '100vh', background: palette.editorBackground }}>
        <Content
          style={{
            padding: '20px 24px',
            maxWidth: 920,
            margin: '0 auto',
            width: '100%',
            color: palette.editorForeground,
          }}
        >
          {/* 头部区域 - 玻璃态 */}
          <div
            style={{
              marginBottom: 20,
              padding: '20px 24px',
              borderRadius: 16,
              border: `1px solid ${palette.panelBorder}`,
              background: isDark
                ? 'rgba(37, 37, 38, 0.7)'
                : 'rgba(255, 255, 255, 0.65)',
              backdropFilter: 'blur(24px)',
              WebkitBackdropFilter: 'blur(24px)',
              boxShadow: isDark
                ? '0 4px 16px rgba(0,0,0,0.2)'
                : '0 4px 16px rgba(0,0,0,0.08)',
            }}
          >
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 40,
                    height: 40,
                    borderRadius: 12,
                    background: `linear-gradient(135deg, ${palette.linkForeground}20 0%, ${palette.linkForeground}10 100%)`,
                    color: palette.linkForeground,
                  }}
                >
                  <SettingOutlined style={{ fontSize: 18 }} />
                </span>
                <div>
                  <Title level={4} style={{ margin: 0 }}>{t('configPage.title')}</Title>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
                    {workspaceInfo.envFilePath
                      ? t('configPage.envFileLoaded', { path: workspaceInfo.envFilePath })
                      : t('configPage.subtitle')}
                  </Text>
                </div>
              </div>
            </div>

            {/* 统计卡片 - 显示后端状态和配置概览 */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
              {/* 后端状态卡片 */}
              <Tooltip
                title={
                  backendStatus.isRunning
                    ? undefined
                    : (saveDisabledReason ?? t('configPage.overview.startBackendOnClick'))
                }
              >
                <div
                  role={!backendStatus.isRunning ? 'button' : undefined}
                  tabIndex={!backendStatus.isRunning && canSaveAndStart ? 0 : undefined}
                  onClick={!backendStatus.isRunning ? handleOverviewStartBackend : undefined}
                  onKeyDown={
                    !backendStatus.isRunning
                      ? (event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault();
                          handleOverviewStartBackend();
                        }
                      }
                      : undefined
                  }
                  style={{
                    flex: '1 1 140px',
                    minWidth: 120,
                    padding: '12px 16px',
                    borderRadius: 10,
                    border: `1px solid ${palette.panelBorder}`,
                    background: backendStatus.isRunning
                      ? (isDark ? 'rgba(34, 139, 34, 0.15)' : 'rgba(34, 139, 34, 0.08)')
                      : (isDark ? 'rgba(37, 37, 38, 0.6)' : 'rgba(255, 255, 255, 0.55)'),
                    backdropFilter: 'blur(16px)',
                    WebkitBackdropFilter: 'blur(16px)',
                    boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                    transition: 'all 0.2s ease',
                    cursor: !backendStatus.isRunning
                      ? (canSaveAndStart && !startingBackend ? 'pointer' : 'not-allowed')
                      : undefined,
                    opacity: !backendStatus.isRunning && !canSaveAndStart ? 0.65 : 1,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                    <span style={{ color: backendStatus.isRunning ? palette.successForeground : palette.descriptionForeground }}>
                      {backendStatus.isRunning ? <CheckCircleOutlined /> : <StopOutlined />}
                    </span>
                    <span style={{ fontSize: 11, color: palette.descriptionForeground, fontWeight: 500 }}>
                      {t('configPage.overview.backend')}
                    </span>
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 700, color: backendStatus.isRunning ? palette.successForeground : palette.editorForeground, lineHeight: 1 }}>
                    {backendStatus.isRunning
                      ? t('configPage.overview.backendRunning', { port: backendStatus.port ?? '' })
                      : startingBackend
                        ? t('configPage.starting')
                        : t('configPage.overview.backendStopped')}
                  </div>
                  {!backendStatus.isRunning && !startingBackend && (
                    <Tooltip title={t('configPage.overview.backendStoppedDetail')}>
                      <div style={{ marginTop: 4, fontSize: 11, color: palette.descriptionForeground, width: 'fit-content' }}>
                        {t('configPage.overview.backendStoppedHint')}
                      </div>
                    </Tooltip>
                  )}
                  {backendStatus.isRunning && backendStatus.url && (
                    <div
                      style={{ marginTop: 4, fontSize: 11, color: palette.linkForeground, cursor: 'pointer' }}
                      onClick={(event) => {
                        event.stopPropagation();
                        if (backendStatus.url) {
                          vscode.postMessage({ command: 'openUrl', url: backendStatus.url });
                        }
                      }}
                    >
                      <LinkOutlined style={{ marginRight: 4 }} />{backendStatus.url}
                    </div>
                  )}
                </div>
              </Tooltip>
              {/* LLM 配置状态 */}
              {statPill(
                t('configPage.overview.advanced'),
                advancedOverview.summary,
                <SettingOutlined />,
                advancedOverview.accent,
                () => {
                  jumpToAdvanced('models');
                  validateAllAdvanced({ manual: true });
                },
                advancedOverview.tooltip
              )}
              {statPill(
                t('configPage.overview.claudeCode'),
                claudeOverview.value,
                <CodeOutlined />,
                claudeOverview.accent,
                () => jumpToAdvanced('claude'),
                claudeOverview.tooltip
              )}
            </div>
          </div>

          {!workspaceInfo.hasWorkspace && (
            <Alert
              message={t('configPage.noWorkspace')}
              description={t('configPage.noWorkspaceHint')}
              type="warning"
              showIcon
              style={{ marginBottom: 16, borderRadius: 10 }}
            />
          )}

          <Form form={form} style={{ marginBottom: 20 }}>
            {/* ========== 默认 LLM（必填）========== */}
            <Card
              title={
                <Space>
                  <KeyOutlined style={{ color: palette.errorForeground }} />
                  <span>{t('configPage.llm.cardTitle')}</span>
                  <Tag color="red" style={{ marginLeft: 4 }}>{t('configPage.llm.requiredTag')}</Tag>
                </Space>
              }
              style={glassCardStyle(isDark, palette)}
              styles={{ body: { padding: '16px 20px' } }}
            >
              <Form.Item
                name="llmApiKey"
                label={t('configPage.llm.apiKeyRequired')}
                rules={[{ required: true, message: t('configPage.notifications.apiKeyMissing') }]}
                tooltip={t('configPage.llm.apiKeyRequiredHint')}
              >
                <Input.Password placeholder={t('configPage.llm.apiKeyPlaceholder')} autoComplete="off" />
              </Form.Item>
              <Form.Item name="llmApiBase" label={t('configPage.llm.apiBase')}>
                <Input placeholder={t('configPage.llm.apiBasePlaceholder')} />
              </Form.Item>
              <Form.Item name="llmModel" label={t('configPage.llm.modelName')}>
                <Input placeholder={t('configPage.llm.modelPlaceholder')} />
              </Form.Item>
              <ValidationAction
                t={t}
                palette={palette}
                state={validationState.default}
                disabledReason={defaultValidateDisabledReason}
                onValidate={() => handleValidate('default')}
              />
            </Card>

            {/* ========== 高级配置（折叠）========== */}
            <div ref={advancedSectionRef}>
              <Collapse
                bordered={false}
                activeKey={['advanced']}
                style={{ marginBottom: 16, background: 'transparent' }}
                expandIcon={() => null}
                items={[
                  {
                    key: 'advanced',
                    forceRender: true,
                    collapsible: 'disabled',
                    label: (
                      <span style={{ fontWeight: 500, color: palette.editorForeground }}>
                        {t('configPage.advancedConfig')}
                      </span>
                    ),
                    style: {
                      marginBottom: 8,
                      borderRadius: 10,
                      border: `1px solid ${palette.panelBorder}`,
                      background: isDark ? 'rgba(37, 37, 38, 0.45)' : 'rgba(255, 255, 255, 0.4)',
                      overflow: 'hidden',
                    },
                    children: (
                      <div style={advancedPanelInnerStyle(isDark, palette)}>
                        <AdvancedConfigSection
                          t={t}
                          palette={palette}
                          hasDefaultLlmKey={hasDefaultLlmKey}
                          defaultLlmApiBase={defaultLlmApiBase}
                          defaultLlmModel={defaultLlmModel}
                          activeTopTab={advancedTopTab}
                          onActiveTopTabChange={setAdvancedTopTab}
                          validationState={validationState}
                          validateDisabledByKind={{
                            coder: coderValidateDisabledReason,
                            nano: nanoValidateDisabledReason,
                            analysis: analysisValidateDisabledReason,
                            embedding: embeddingValidateDisabledReason,
                          }}
                          pythonValidateDisabledReason={pythonValidateDisabledReason}
                          literatureValidateDisabledReason={literatureValidateDisabledReason}
                          claudeValidateDisabledReason={claudeValidateDisabledReason}
                          onValidate={handleValidate}
                          pythonSectionRef={pythonSectionRef}
                          literatureSectionRef={literatureSectionRef}
                          claudeSectionRef={claudeSectionRef}
                          claudeForm={claudeForm}
                          claudeCliStatus={claudeCliStatus}
                          claudeSettingsPath={claudeSettingsPath}
                          onResetClaude={handleResetClaudeDefaults}
                          easyPaperForm={easyPaperForm}
                          defaultLlmApiKey={effectiveConfigValues.llmApiKey}
                          onSaveEasyPaper={saveEasyPaperConfig}
                        />
                      </div>
                    ),
                  },
                ]}
              />
            </div>

            {/* ========== 操作按钮 - 玻璃态 ========== */}
            <div
              ref={actionsSectionRef}
              style={{
                position: 'sticky',
                bottom: 16,
                zIndex: 10,
                textAlign: 'center',
                padding: '14px 16px',
                borderRadius: 12,
                border: `1px solid ${palette.panelBorder}`,
                background: isDark
                  ? 'rgba(37, 37, 38, 0.72)'
                  : 'rgba(255, 255, 255, 0.72)',
                backdropFilter: 'blur(20px)',
                WebkitBackdropFilter: 'blur(20px)',
                boxShadow: isDark
                  ? '0 10px 30px rgba(0,0,0,0.25)'
                  : '0 10px 30px rgba(0,0,0,0.12)',
              }}
            >
              <Space size="middle" wrap direction="vertical" style={{ width: '100%' }}>
                <Space size="middle" wrap style={{ justifyContent: 'center' }}>
                  <Button
                    size="large"
                    icon={<ReloadOutlined />}
                    onClick={handleResetWorkspaceDefaults}
                  >
                    {t('configPage.resetWorkspaceDefaults')}
                  </Button>
                  <Tooltip title={saveDisabledReason || ''}>
                    <Button
                      size="large"
                      icon={<SaveOutlined />}
                      onClick={handleSave}
                      disabled={!canSave}
                      loading={loading}
                    >
                      {t('configPage.save')}
                    </Button>
                  </Tooltip>
                  <Tooltip title={saveDisabledReason || ''}>
                    <Button
                      type="primary"
                      size="large"
                      icon={<RocketOutlined />}
                      onClick={handleSaveAndStart}
                      loading={startingBackend}
                      disabled={!canSaveAndStart}
                    >
                      {startingBackend ? t('configPage.starting') : t('configPage.saveAndStart')}
                    </Button>
                  </Tooltip>
                </Space>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', textAlign: 'center' }}>
                  {t('configPage.saveHint')}
                </Text>
              </Space>
            </div>
          </Form>
        </Content>
      </Layout>
    </ConfigProvider>
  );
};
