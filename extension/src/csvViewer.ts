/**
 * CSV / TSV 表格预览（轻量，不做编辑）
 */

import * as vscode from 'vscode';
import * as fs from 'fs';

const MAX_FILE_BYTES = 6 * 1024 * 1024;
const MAX_ROWS = 5000;

function splitRow(line: string, delimiter: string): string[] {
  const out: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i]!;
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        cur += c;
      }
    } else if (c === '"') {
      inQuotes = true;
    } else if (c === delimiter) {
      out.push(cur);
      cur = '';
    } else {
      cur += c;
    }
  }
  out.push(cur);
  return out;
}

function parseDelimited(text: string, delimiter: string): string[][] {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter((l) => l.length > 0);
  return lines.map((line) => splitRow(line, delimiter));
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export class CsvViewer {
  private static currentPanel: vscode.WebviewPanel | undefined;

  public static async show(filePath: string): Promise<void> {
    const isZh = vscode.env.language.startsWith('zh');
    const lower = filePath.toLowerCase();
    const delim = lower.endsWith('.tsv') ? '\t' : ',';

    let rows: string[][] = [];
    let error: string | null = null;
    let truncated = false;

    try {
      const stat = fs.statSync(filePath);
      if (stat.size > MAX_FILE_BYTES) {
        error = isZh
          ? `文件过大（>${Math.floor(MAX_FILE_BYTES / 1024 / 1024)}MB），请用编辑器或外部工具打开`
          : `File too large (>${Math.floor(MAX_FILE_BYTES / 1024 / 1024)}MB); open in an external tool`;
      } else {
        const text = fs.readFileSync(filePath, 'utf-8');
        rows = parseDelimited(text, delim);
        if (rows.length > MAX_ROWS) {
          rows = rows.slice(0, MAX_ROWS);
          truncated = true;
        }
      }
    } catch (e: any) {
      error = e.message || String(e);
    }

    const fileName = filePath.split(/[/\\]/).pop() || 'data';

    if (this.currentPanel) {
      this.currentPanel.title = fileName;
      this.currentPanel.reveal(vscode.ViewColumn.One);
      this.currentPanel.webview.html = this.buildHtml(rows, error, truncated, filePath, isZh);
      return;
    }

    const panel = vscode.window.createWebviewPanel(
      'csvViewer',
      fileName,
      vscode.ViewColumn.One,
      { enableScripts: true, retainContextWhenHidden: true }
    );
    this.currentPanel = panel;
    panel.onDidDispose(() => {
      this.currentPanel = undefined;
    });
    panel.webview.html = this.buildHtml(rows, error, truncated, filePath, isZh);
  }

  private static buildHtml(
    rows: string[][],
    error: string | null,
    truncated: boolean,
    filePath: string,
    isZh: boolean
  ): string {
    const title = isZh ? '表格预览' : 'Table preview';
    const pathLabel = isZh ? '路径' : 'Path';

    if (error) {
      return `<!DOCTYPE html><html><head><meta charset="UTF-8"><title>${title}</title>
      <style>body{font-family:var(--vscode-font-family);padding:16px;color:var(--vscode-errorForeground);}</style></head>
      <body><p>${escapeHtml(error)}</p><p style="color:var(--vscode-descriptionForeground);font-size:12px;">${escapeHtml(filePath)}</p></body></html>`;
    }

    const head = rows[0] || [];
    const body = rows.slice(1);
    const th = head.map((c) => `<th>${escapeHtml(c)}</th>`).join('');
    const trs = body
      .map((r) => {
        const cells = head.map((_, i) => `<td>${escapeHtml(r[i] ?? '')}</td>`).join('');
        return `<tr>${cells}</tr>`;
      })
      .join('');

    const note = truncated
      ? (isZh ? `<p class="note">仅显示前 ${MAX_ROWS} 行。</p>` : `<p class="note">Showing first ${MAX_ROWS} rows only.</p>`)
      : '';

    return `<!DOCTYPE html>
<html lang="${isZh ? 'zh-CN' : 'en'}">
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { font-family: var(--vscode-font-family); background: var(--vscode-editor-background); color: var(--vscode-editor-foreground); margin: 0; padding: 12px 16px 24px; }
    h1 { font-size: 16px; margin: 0 0 8px; }
    .path { font-size: 11px; color: var(--vscode-descriptionForeground); word-break: break-all; margin-bottom: 12px; }
    .note { font-size: 12px; color: var(--vscode-editorWarning-foreground); margin: 8px 0; }
    .wrap { overflow: auto; max-height: calc(100vh - 120px); border: 1px solid var(--vscode-panel-border); border-radius: 6px; }
    table { border-collapse: collapse; min-width: 100%; font-size: 12px; }
    th { position: sticky; top: 0; background: var(--vscode-editorWidget-background); color: var(--vscode-editor-foreground); text-align: left; padding: 8px 10px; border-bottom: 2px solid var(--vscode-panel-border); white-space: nowrap; z-index: 1; }
    td { padding: 6px 10px; border-bottom: 1px solid var(--vscode-panel-border); vertical-align: top; max-width: 420px; }
    tr:nth-child(even) td { background: var(--vscode-editor-inactiveSelectionBackground, rgba(127,127,127,.08)); }
  </style>
</head>
<body>
  <h1>${title}</h1>
  <div class="path">${pathLabel}: ${escapeHtml(filePath)}</div>
  ${note}
  <div class="wrap"><table><thead><tr>${th}</tr></thead><tbody>${trs}</tbody></table></div>
</body>
</html>`;
  }
}
