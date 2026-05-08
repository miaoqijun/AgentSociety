/**
 * HelpPageViewProvider - Help Page Webview Provider
 *
 * Embeds ReadTheDocs documentation as the primary help source,
 * with local HELP.md as offline fallback.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

const RTD_BASE_URL = 'https://agentsociety2.readthedocs.io';

export class HelpPageViewProvider {
  private readonly panel: vscode.WebviewPanel;
  private readonly extensionUri: vscode.Uri;
  private readonly extensionPath: string;
  private disposables: vscode.Disposable[] = [];

  public static currentPanel: HelpPageViewProvider | undefined;

  /**
   * Create a new help page panel or reveal the existing one.
   */
  public static createOrShow(context: vscode.ExtensionContext, viewColumn: vscode.ViewColumn = vscode.ViewColumn.One): HelpPageViewProvider {
    if (HelpPageViewProvider.currentPanel) {
      HelpPageViewProvider.currentPanel.panel.reveal(viewColumn);
      return HelpPageViewProvider.currentPanel;
    }

    const locale = vscode.env.language;
    const title = locale.startsWith('zh') ? '使用指南 - AI Social Scientist' : 'User Guide - AI Social Scientist';

    const panel = vscode.window.createWebviewPanel(
      'aiSocialScientistHelp',
      title,
      viewColumn,
      {
        enableScripts: true,
        retainContextWhenHidden: true,
        localResourceRoots: [context.extensionUri],
      }
    );

    HelpPageViewProvider.currentPanel = new HelpPageViewProvider(panel, context);
    return HelpPageViewProvider.currentPanel;
  }

  private constructor(panel: vscode.WebviewPanel, context: vscode.ExtensionContext) {
    this.panel = panel;
    this.extensionUri = context.extensionUri;
    this.extensionPath = context.extensionPath;

    this.updateWebviewContent();

    this.panel.onDidDispose(() => this.dispose(), null, this.disposables);

    this.panel.webview.onDidReceiveMessage(
      async (message: { command: string; commandId?: string; url?: string }) => {
        switch (message.command) {
          case 'openCommand':
            if (message.commandId) {
              await vscode.commands.executeCommand(message.commandId);
            }
            break;
          case 'openUrl':
            if (message.url) {
              await vscode.env.openExternal(vscode.Uri.parse(message.url));
            }
            break;
        }
      },
      null,
      this.disposables
    );
  }

  /**
   * Read fallback help content from local HELP.md based on locale
   */
  private readHelpContent(): string {
    const locale = vscode.env.language;

    const localeSpecificPath = path.join(this.extensionPath, `HELP.${locale}.md`);
    if (fs.existsSync(localeSpecificPath)) {
      try {
        return fs.readFileSync(localeSpecificPath, 'utf-8');
      } catch (error) {
        console.error(`Failed to read HELP.${locale}.md:`, error);
      }
    }

    const baseLocale = locale.split('-')[0];
    if (baseLocale !== locale) {
      const baseLocalePath = path.join(this.extensionPath, `HELP.${baseLocale}.md`);
      if (fs.existsSync(baseLocalePath)) {
        try {
          return fs.readFileSync(baseLocalePath, 'utf-8');
        } catch (error) {
          console.error(`Failed to read HELP.${baseLocale}.md:`, error);
        }
      }
    }

    const defaultPath = path.join(this.extensionPath, 'HELP.md');
    try {
      if (fs.existsSync(defaultPath)) {
        return fs.readFileSync(defaultPath, 'utf-8');
      }
    } catch (error) {
      console.error('Failed to read HELP.md:', error);
    }

    const isZh = locale.startsWith('zh');
    if (isZh) {
      return `# AI Social Scientist 使用指南

帮助文档加载失败，请查看 [README.md](https://github.com/tsinghua-fib-lab/agentsociety) 获取更多信息。

## 快速入口

- [打开配置页面](command:aiSocialScientist.openConfigPage)
- [打开技能市场](command:aiSocialScientist.openSkillMarketplace)
- [后端状态菜单](command:aiSocialScientist.backendStatusMenu)
`;
    }
    return `# AI Social Scientist User Guide

Failed to load help documentation. Please visit [README.md](https://github.com/tsinghua-fib-lab/agentsociety) for more information.

## Quick Links

- [Open Configuration Page](command:aiSocialScientist.openConfigPage)
- [Open Skill Marketplace](command:aiSocialScientist.openSkillMarketplace)
- [Backend Status Menu](command:aiSocialScientist.backendStatusMenu)
`;
  }

  /**
   * Get ReadTheDocs URL based on locale
   */
  private getRtdUrl(): string {
    const locale = vscode.env.language;
    const isZh = locale.startsWith('zh');
    return isZh ? `${RTD_BASE_URL}/zh_CN/latest/` : `${RTD_BASE_URL}/en/latest/`;
  }

  /**
   * Update webview content
   */
  private updateWebviewContent(): void {
    const helpContent = this.readHelpContent();
    const rtdUrl = this.getRtdUrl();
    this.panel.webview.html = this.getHtmlForWebview(helpContent, rtdUrl);
  }

  /**
   * Generate HTML for webview
   */
  private getHtmlForWebview(helpContent: string, rtdUrl: string): string {
    const scriptUri = this.panel.webview.asWebviewUri(
      vscode.Uri.file(path.join(this.extensionUri.fsPath, 'out', 'webview', 'helpPage.js'))
    );

    const nonce = Math.random().toString(36).slice(2);
    const csp = [
      "default-src 'none'",
      `style-src ${this.panel.webview.cspSource} 'unsafe-inline' https://assets.readthedocs.org https://cdnjs.cloudflare.com`,
      `script-src ${this.panel.webview.cspSource} 'nonce-${nonce}'`,
      `font-src ${this.panel.webview.cspSource} https://assets.readthedocs.org https://cdnjs.cloudflare.com`,
      `frame-src ${RTD_BASE_URL} https://readthedocs.org`,
      `img-src ${this.panel.webview.cspSource} https://assets.readthedocs.org https://cdnjs.cloudflare.com data:`,
      `connect-src ${RTD_BASE_URL} https://assets.readthedocs.org`,
    ].join('; ');

    const locale = vscode.env.language;
    const htmlLang = locale.startsWith('zh') ? 'zh-CN' : 'en-US';
    const title = locale.startsWith('zh') ? '使用指南 - AI Social Scientist' : 'User Guide - AI Social Scientist';

    const jsonHelpContent = JSON.stringify(helpContent);
    const jsonRtdUrl = JSON.stringify(rtdUrl);

    return `<!DOCTYPE html>
<html lang="${htmlLang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="${csp}">
    <title>${title}</title>
    <style>
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        html,
        body {
            height: 100%;
            width: 100%;
        }

        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            background-color: var(--vscode-editor-background);
            color: var(--vscode-editor-foreground);
        }

        #root {
            height: 100%;
            width: 100%;
        }
    </style>
</head>
<body>
    <div id="root"></div>
    <script nonce="${nonce}">window.HELP_CONTENT = ${jsonHelpContent};</script>
    <script nonce="${nonce}">window.RTD_URL = ${jsonRtdUrl};</script>
    <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }

  /**
   * Dispose the webview panel and resources
   */
  public dispose(): void {
    HelpPageViewProvider.currentPanel = undefined;
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
  }
}
