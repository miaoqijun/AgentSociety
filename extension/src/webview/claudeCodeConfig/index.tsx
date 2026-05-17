import * as React from 'react';
import * as ReactDOM from 'react-dom/client';
import { ClaudeCodeConfigApp } from './ClaudeCodeConfigApp';
import type { VSCodeAPI } from './types';
import '../i18n';
import 'antd/dist/reset.css';

declare function acquireVsCodeApi(): VSCodeAPI;

const vscode: VSCodeAPI = acquireVsCodeApi();

const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(<ClaudeCodeConfigApp vscode={vscode} />);
} else {
  console.error('Root element not found');
}
