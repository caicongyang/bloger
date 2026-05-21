# OpenCLI 架构：网站如何被 CLI 化

这篇文档从源码出发，回答一个根本问题：

> **OpenCLI 到底是怎么把一个网站（或 Electron 应用）变成可以在终端里跑的命令的？**

涉及到的不只是「写个爬虫包装一下」，而是一整套**注册表 → 发现 → 执行 → 浏览器通道 → 输出**的运行时。读完这篇你能：

- 自己回答"`opencli bilibili hot --limit 5` 一共走了多少层"
- 区分 **Browser Bridge 通道**和 **CDP 通道**的责任边界
- 看懂 `clis/<site>/<command>.js` 一行 `cli({...})` 背后真正发生了什么
- 知道想做扩展时该插哪一层

下文所有源码引用都来自当前仓库，可对照阅读。

## 顶层视图

整个系统由 6 层组成，自上而下：

```
┌─────────────────────────────────────────────────────────────────┐
│  1. 用户命令     opencli bilibili hot --limit 5                  │
├─────────────────────────────────────────────────────────────────┤
│  2. 入口快路径   src/main.ts                                     │
│                  - --version / completion / 启动校验             │
│                  - rewriteBrowserArgv 参数预处理                  │
├─────────────────────────────────────────────────────────────────┤
│  3. 发现 + 注册  discovery.ts → registry.ts                     │
│                  - 优先 cli-manifest.json 快路径                  │
│                  - 否则文件系统扫描 clis/<site>/*.js              │
│                  - 全部塞进 globalThis.__opencli_registry__       │
├─────────────────────────────────────────────────────────────────┤
│  4. Commander    commanderAdapter.ts                            │
│                  - 把注册表转成 commander 子命令树                 │
│                  - --format / --trace / --window 等通用选项       │
├─────────────────────────────────────────────────────────────────┤
│  5. 执行         execution.ts                                    │
│                  - 参数校验 + 类型 coerce                         │
│                  - capability routing（要不要浏览器）              │
│                  - 预导航 + 超时 + trace 记录                      │
├─────────────────────────────────────────────────────────────────┤
│  6. 浏览器通道   browser/page.ts (Bridge)  ┐                     │
│                  browser/cdp.ts (CDP)      ┴── 共享 BasePage      │
│                                                                   │
│  浏览器侧：                                                       │
│   - Bridge: chrome 扩展 (extension/) + daemon (daemon.ts)         │
│   - CDP:    直连 Electron / 远程 Chrome 的 WebSocket               │
└─────────────────────────────────────────────────────────────────┘
```

后面把每一层拆开讲。

## 第 1 层：命令的形状

每个网站的命令在 `clis/<site>/<command>.js` 里通过**一次 `cli({...})` 调用**完成自描述：

```12:24:clis/bilibili/search.js
cli({
    site: 'bilibili', name: 'search', access: 'read', description: 'Search Bilibili videos or users', domain: 'www.bilibili.com', strategy: Strategy.COOKIE,
    args: [
        { name: 'query', required: true, positional: true, help: 'Search keyword' },
        ...
    ],
    columns: ['rank', 'title', 'author', 'score', 'url'],
    func: async (page, kwargs) => {
        const { query: keyword, ... } = kwargs;
        const payload = await apiGet(page, '/x/web-interface/wbi/search/type', { params: { ... } });
        return payload?.data?.result?.slice(0, limit).map(...);
    },
});
```

每个字段都对应一个明确的运行时行为：

| 字段                | 谁会读它                                  | 作用                                                       |
| ------------------- | ----------------------------------------- | ---------------------------------------------------------- |
| `site`/`name`       | `registry.ts/fullName`                    | 全局唯一键 `bilibili/search`                              |
| `description`/`example` | `help.ts`                              | `opencli list` 和 `--help` 的展示文本                      |
| `access: 'read'\|'write'` | `registry.ts/assertCommandAccess`    | 必须显式声明，便于 agent / 审计区分副作用                  |
| `domain`            | `execution.ts/resolvePreNav`              | COOKIE 策略下用于自动 `goto('https://${domain}')` 预导航   |
| `strategy`          | `registry.ts/normalizeCommand`            | 决定要不要浏览器、要不要预导航                             |
| `args`              | `commanderAdapter.ts` + `execution.ts`    | 注册 commander 选项、类型 coerce、required 校验            |
| `columns`           | `output.ts/renderTable`                   | 表格输出的列顺序                                           |
| `func`              | `execution.ts/runCommandFunc`             | 实际执行的逻辑（接收 page + kwargs）                       |
| `pipeline`          | `pipeline/executor.ts`                    | 替代 func 的声明式步骤数组                                 |
| `siteSession`       | `execution.ts/resolveAdapterBrowserSession` | `ephemeral`/`persistent`，决定 tab 是否复用              |

也就是说，**每条命令都是一个"自带元数据 + 执行体"的小对象**。框架要做的不是给它写代码，而是把它装到合适的运行时位置上。

## 第 2 层：注册表

`src/registry.ts` 是整个项目的"中央花名册"。

### 2.1 全局唯一的 Map

```115:120:src/registry.ts
declare global { var __opencli_registry__: Map<string, CliCommand> | undefined; }
const _registry: Map<string, CliCommand> =
  globalThis.__opencli_registry__ ??= new Map<string, CliCommand>();
```

挂在 `globalThis` 是为了对付 **npm link / peerDependency** 场景下 ESM 多实例问题：plugin 的 `import { cli } from '@jackwener/opencli/registry'` 可能解析到一份独立的模块拷贝，但仍要写入同一个 Map。

### 2.2 normalize：把 strategy 翻译成执行字段

`cli({...})` 注册时会跑一遍 `normalizeCommand`，把 `strategy` 翻译成执行路径真正会读的两个字段 `browser` 和 `navigateBefore`：

```172:194:src/registry.ts
function normalizeCommand(cmd: RawCliCommand): CliCommand {
  ...
  const strategy = cmd.strategy ?? (cmd.browser === false ? Strategy.PUBLIC : Strategy.COOKIE);
  const browser = cmd.browser ?? (strategy !== Strategy.PUBLIC && strategy !== Strategy.LOCAL);

  let navigateBefore = cmd.navigateBefore;
  if (navigateBefore === undefined) {
    if (strategy === Strategy.COOKIE && cmd.domain) {
      navigateBefore = `https://${cmd.domain}`;
    } else if (strategy !== Strategy.PUBLIC && strategy !== Strategy.LOCAL) {
      navigateBefore = true; // 需要登录态但无具体 URL
    }
  }
  ...
}
```

这是个关键设计：**`strategy` 只是给人看的元数据，执行路径只看翻译后的 `browser` + `navigateBefore`**。这样新增 strategy 不会修改执行逻辑，只要 normalize 一处加翻译规则就行。

### 2.3 五种 Strategy 语义

```7:13:src/registry.ts
export enum Strategy {
  PUBLIC = 'public',
  LOCAL = 'local',
  COOKIE = 'cookie',
  INTERCEPT = 'intercept',
  UI = 'ui',
}
```

| Strategy    | 翻译结果                                | 典型场景                                       |
| ----------- | --------------------------------------- | ---------------------------------------------- |
| `PUBLIC`    | `browser: false`                        | 纯 API（HackerNews、arXiv），不需要浏览器       |
| `LOCAL`     | `browser: false`                        | 本机操作（管理类命令）                         |
| `COOKIE`    | `browser: true` + `goto(https://domain)` | 需要登录态（B站、知乎、Twitter）              |
| `INTERCEPT` | `browser: true` + 抓真实请求            | 站点用了复杂签名/加密，反编译成本高            |
| `UI`        | `browser: true` + 真实 UI 操作          | Electron 应用（Codex/Cursor）或没有 API 的站点 |

## 第 3 层：发现机制（双轨）

`src/discovery.ts` 提供两条加载路径，构造的目的是**冷启动尽可能快**。

### 3.1 快路径：从 `cli-manifest.json` 加载

构建期 `npm run build-manifest` 会扫描所有 `clis/<site>/*.js`，把 `cli({...})` 的元数据序列化成一个 700KB 的 JSON。运行期只读这个 JSON 注册元数据，不 `import` 任何 adapter 源码：

```114:149:src/discovery.ts
async function loadFromManifest(manifestPath: string, clisDir: string): Promise<boolean> {
  ...
  for (const entry of manifest) {
    if (!entry.modulePath) continue;
    const modulePath = path.resolve(clisDir, entry.modulePath);
    const cmd: InternalCliCommand = {
      site: entry.site, name: entry.name, ...,
      _lazy: true,
      _modulePath: modulePath,
    };
    registerCommand(cmd);
  }
}
```

`_lazy: true` 是关键：注册的时候 `func` 是空的，**只有命令真正被执行时才会 `import(modulePath)` 把 `func` 注入回来**。`execution.ts` 里的对应分支：

```104:135:src/execution.ts
if (internal._lazy && internal._modulePath) {
  ...
  if (!_loadedModules.has(modulePath)) {
    const loadPromise = import(importUrl).then(...);
    _loadedModules.set(modulePath, loadPromise);
  }
  await _loadedModules.get(modulePath);
  const updated = getRegistry().get(fullName(cmd));
  if (updated?.func) return runCommandFunc(updated, page, kwargs, debug);
  ...
}
```

效果是：**`opencli list` 列出 1300+ 命令几乎瞬完成；只有命中的那一个 adapter 才会被加载**。

### 3.2 慢路径：文件系统扫描（开发态）

开发模式下没有 manifest，回落到扫描 `clis/<site>/*.js`：

```154:182:src/discovery.ts
async function discoverClisFromFs(dir: string): Promise<void> {
  const entries = await fs.promises.readdir(dir, { withFileTypes: true });
  const sitePromises = entries.filter(entry => entry.isDirectory()).map(async (entry) => {
    const site = entry.name;
    const siteDir = path.join(dir, site);
    const files = await fs.promises.readdir(siteDir);
    await Promise.all(files.map(async (file) => {
      ...
      if (file.endsWith('.js') && !file.endsWith('.test.js')) {
        if (!(await isCliModule(filePath))) return;
        await import(pathToFileURL(filePath).href).catch(...);
      }
    }));
  });
}
```

其中 `isCliModule` 用一个正则 `/\b(?:cli|onStartup|onBeforeExecute|onAfterExecute)\s*\(/` 先粗筛文件，避免把工具类 `utils.js` 也 import 进来。

### 3.3 三个发现源（按 override 顺序）

```111:122:src/main.ts
if (skipUserDiscovery) {
  await discoverClis(BUILTIN_CLIS);
} else {
  const [, ,] = await Promise.all([
    ensureUserCliCompatShims(),
    ensureUserAdapters(),
    discoverClis(BUILTIN_CLIS),
  ]);
  await discoverClis(USER_CLIS);
  await discoverPlugins();
}
```

加载顺序固定：

```
内置 clis/  →  用户 ~/.opencli/clis/  →  插件 ~/.opencli/plugins/
                  └ 同名 site/name 会覆盖前者
```

这是 `opencli adapter eject <site>` 能临时改本地命令的根本机制——后注册的覆盖先注册的。

## 第 4 层：注册表 → Commander

`src/commanderAdapter.ts` 把抽象的 `CliCommand` 翻译成 commander 的 `Command` 子命令：

```46:69:src/commanderAdapter.ts
const subCmd = siteCmd.command(cmd.name).description(formatSiteCommandDescription(cmd));
if (cmd.aliases?.length) subCmd.aliases(cmd.aliases);

const positionalArgs: typeof cmd.args = [];
for (const arg of cmd.args) {
  if (arg.positional) {
    const bracket = arg.required ? `<${arg.name}>` : `[${arg.name}]`;
    subCmd.argument(bracket, arg.help ?? '');
    positionalArgs.push(arg);
  } else {
    const expectsValue = arg.required || arg.valueRequired;
    const flag = expectsValue ? `--${arg.name} <value>` : `--${arg.name} [value]`;
    if (arg.required) subCmd.requiredOption(flag, arg.help ?? '');
    else if (arg.default != null) subCmd.option(flag, arg.help ?? '', String(arg.default));
    else subCmd.option(flag, arg.help ?? '');
  }
}
subCmd
  .option('-f, --format <fmt>', 'Output format: table, plain, json, yaml, md, csv', 'table')
  .option('--trace <mode>', 'Trace capture: off, on, retain-on-failure', 'off')
  .option('-v, --verbose', 'Debug output', false);
if (cmd.browser) {
  subCmd
    .option('--window <mode>', ...)
    .option('--site-session <mode>', ...)
    .option('--keep-tab <bool>', ...);
}
```

每个子命令统一带上四类**通用选项**：`-f` 输出格式、`--trace` 观察轨迹、`-v` 调试、（浏览器命令额外）`--window`/`--site-session`/`--keep-tab`。

action 回调里完成 kwargs 收集、调用 `executeCommand`、`renderOutput`：

```81:151:src/commanderAdapter.ts
subCmd.action(async (...actionArgs: unknown[]) => {
  ...
  const rawKwargs: Record<string, unknown> = {};
  for (let i = 0; i < positionalArgs.length; i++) { ... }
  for (const arg of cmd.args) { ... }
  const kwargs = prepareCommandArgs(cmd, rawKwargs);

  const result = await executeCommand(cmd, kwargs, verbose, { ... });
  renderOutput(result, { fmt, columns: resolved.columns, title: ..., elapsed: ..., footerExtra: ... });
});
```

## 第 5 层：执行流水线

`src/execution.ts/executeCommand` 是单一执行入口。完整流程：

```
executeCommand
  ├─ coerceAndValidateArgs        参数类型校验 + 默认值
  ├─ readUserTimeoutSeconds       --timeout 的隐式协议
  ├─ emitHook('onBeforeExecute')  生命周期钩子
  │
  ├─ if shouldUseBrowserSession(cmd):
  │   ├─ Electron? → resolveElectronEndpoint / probeCDP
  │   ├─ 非Electron? → 走 BrowserBridge
  │   ├─ browserSession(...) 开 IPage
  │   │   ├─ ObservationSession 开始（trace 模式）
  │   │   ├─ startNetworkCapture（trace 模式）
  │   │   ├─ resolvePreNav → goto(预导航 URL)
  │   │   ├─ runWithTimeout(runCommand)
  │   │   │   ├─ if _lazy: import(modulePath) 注入 func
  │   │   │   ├─ runCommandFunc(cmd, page, kwargs)  ← 命令本体
  │   │   │   └─ 或 executePipeline(...)            ← 声明式步骤
  │   │   ├─ trace 模式收 snapshot/network/console/screenshot
  │   │   └─ closeWindow（除非 keepTab）
  │   └─ end
  │
  ├─ else（非浏览器）:
  │   └─ runCommand(cmd, null, kwargs)
  │
  └─ emitHook('onAfterExecute')
```

### 5.1 是否需要浏览器：capability routing

```46:55:src/capabilityRouting.ts
export function shouldUseBrowserSession(cmd: CliCommand): boolean {
  if (!cmd.browser) return false;
  if (cmd.func) return true;
  if (!cmd.pipeline || cmd.pipeline.length === 0) return true;
  if (cmd.navigateBefore) return true;
  return pipelineNeedsBrowserSession(cmd.pipeline as Record<string, unknown>[]);
}
```

具体来说：

- 显式 `browser: false`（PUBLIC/LOCAL）→ 不开浏览器，直接调 `func`
- 否则有 `func` → 开浏览器
- 只有 pipeline → 看 pipeline 里是否含 `navigate / click / type / wait / evaluate ...` 这些 BROWSER_ONLY 步骤

### 5.2 预导航的小心机

```189:194:src/execution.ts
async function shouldRunPreNav(cmd: CliCommand, page: IPage, siteSession: SiteSessionMode, preNavUrl: string): Promise<boolean> {
  if (siteSession !== 'persistent' || !cmd.domain) return true;
  if (!isDomainRootPreNav(preNavUrl, cmd.domain)) return true;
  const currentUrl = await page.getCurrentUrl?.().catch(() => null);
  return !urlMatchesDomain(currentUrl, cmd.domain);
}
```

`siteSession: 'persistent'` 时**如果当前 tab 已经在同域**，不重复 `goto`。这是避免连续命令把会话状态打回首页的细节。

### 5.3 一次性 vs 持久会话

```500:503:src/execution.ts
function resolveAdapterBrowserSession(cmd: CliCommand, siteSession: SiteSessionMode): string {
  if (siteSession === 'persistent') return `site:${cmd.site}`;
  return `site:${cmd.site}:${crypto.randomUUID()}`;
}
```

- `ephemeral`（默认）：每次执行一个 UUID 后缀的 session，跑完立刻释放
- `persistent`（如 `opencli yuanbao ask`）：固定 `site:yuanbao` 一个 session，多次命令共享 tab + 状态

## 第 6 层：浏览器通道（两条路）

OpenCLI 有两条相互独立但接口一致的浏览器通道，决策代码在：

```10:14:src/runtime.ts
export function getBrowserFactory(site?: string): new () => IBrowserFactory {
  if (site && isElectronApp(site)) return CDPBridge;
  return BrowserBridge;
}
```

```
                          IBrowserFactory
                       ┌────────┴────────┐
                       │                 │
                BrowserBridge        CDPBridge
                       │                 │
                       ▼                 ▼
                  daemon.ts        WebSocket 直连
                       │                 │
                       ▼                 │
              chrome 扩展 (extension/)   │
                       │                 │
                       ▼                 ▼
                       chrome.debugger / CDP
                              │
                              ▼
                          目标页面
```

两个通道的 `Page` 类都继承自 `BasePage`，**所有 DOM 操作 (`click/type/snapshot/...`) 共享同一份实现**，所以适配器代码完全不用知道走的是哪条通道。

### 6.1 BrowserBridge 通道（默认）

适合普通网站，需要利用本机已登录的 Chrome profile。链路：

```
opencli → HTTP POST localhost:19825/command → daemon.ts
         → WebSocket → chrome 扩展 background.js
         → chrome.debugger.sendCommand (CDP)
         → 页面 JS / DOM
```

daemon 是一个常驻 Node 微服务，第一次执行浏览器命令时自动起：

```17:21:src/daemon.ts
 * Lifecycle:
 *   - Auto-spawned by opencli on first browser command
 *   - Persistent — stays alive until explicit shutdown, SIGTERM, or uninstall
 *   - Listens on localhost:19825
```

协议很薄，只有 14 种 action：

```7:23:extension/src/protocol.ts
export type Action =
  | 'exec' | 'navigate' | 'tabs' | 'cookies' | 'screenshot'
  | 'close-window' | 'sessions' | 'set-file-input' | 'insert-text'
  | 'bind' | 'network-capture-start' | 'network-capture-read'
  | 'wait-download' | 'cdp' | 'frames';
```

**其他一切（点击、输入、读 DOM、等待元素）都靠 `exec` 把一段 JS 字符串扔进页面执行**。这就是 `BasePage` 大量调 `this.evaluate(xxxJs(...))` 的原因——把"做什么"全部下沉到生成的 JS 里。

### 6.2 CDP 通道（Electron / 远端服务器）

适合：

1. 本机的 Electron 应用（带 `--remote-debugging-port` 启动）
2. 远端无 GUI 服务器，通过 SSH/ngrok 接到本地 Chrome 的 CDP 端口

链路最短：

```
opencli → WebSocket 直连 → CDP 协议 → 页面 JS / DOM
```

无 daemon、无扩展。代码在 `src/browser/cdp.ts`，详见 [Chrome DevTools Protocol](../advanced/cdp.md)。

### 6.3 共享的元素查找（BasePage）

不论走哪条通道，元素定位都在 `target-resolver.ts` 的一段生成 JS 里完成：

- 数字 ref（snapshot 编号）→ `data-opencli-ref` + fingerprint，三级容错 `exact / stable / reidentified`
- 任意 CSS 字符串 → 直接 `document.querySelectorAll`，多匹配报 `selector_ambiguous`

详见 docs/zh/advanced/cdp 中的"如何查找元素"讨论。

## 适配器三种写法

`cli({...})` 的执行体可以是三种形态之一：

### 形态 A：`func` + 纯 API

绕过 DOM，复用页面 cookies 通过 `page.evaluate` 在浏览器里发 `fetch`。`bilibili/search.js` 是典型：

```12:23:clis/bilibili/search.js
func: async (page, kwargs) => {
    const { query: keyword, ... } = kwargs;
    const payload = await apiGet(page, '/x/web-interface/wbi/search/type', { params: { ... }, signed: true });
    const results = payload?.data?.result ?? [];
    return results.slice(0, Number(limit)).map((item, i) => ({ ... }));
},
```

特点：**速度快、字段完整、对 UI 改版免疫**。要求站点 API 能在浏览器上下文里被调到（带 cookie、签名能复现）。`bilibili/utils.js` 的 `wbiSign` 就是反编译出来的签名算法。

### 形态 B：`func` + 真实 UI 操作

API 不可用（要登录态、反爬重、签名极复杂）时直接驱动页面：

```17:50:clis/zhihu/follow.js
func: async (page, kwargs) => {
    ...
    await page.goto('https://www.zhihu.com');
    await page.wait(2);
    const apiResult = await page.evaluate(`(async () => {
        var url = 'https://www.zhihu.com/api/v4/members/' + targetId + '/followers';
        var resp = await fetch(url, { method: 'POST', credentials: 'include' });
        ...
    })()`);
    ...
}
```

或者用 BasePage 的 `click/typeText/snapshot` 系列直接操作 DOM。

### 形态 C：纯 `pipeline` 声明式

不写函数，用 YAML 风的步骤数组拼装：

```12:39:clis/bilibili/hot.js
pipeline: [
    { navigate: 'https://www.bilibili.com' },
    { evaluate: `(async () => {
        const res = await fetch('https://api.bilibili.com/x/web-interface/popular?ps=\${{ args.limit }}&pn=1', {
          credentials: 'include'
        });
        return (await res.json())?.data?.list || [];
    })()` },
    { map: {
        rank: '${{ index + 1 }}',
        title: '${{ item.title }}',
        ...
    } },
    { limit: '${{ args.limit }}' },
],
```

支持的步骤注册在 `src/pipeline/registry.ts`：

```59:75:src/pipeline/registry.ts
registerStep('navigate', stepNavigate);
registerStep('fetch', stepFetch);
registerStep('select', stepSelect);
registerStep('evaluate', stepEvaluate);
registerStep('snapshot', stepSnapshot);
registerStep('click', stepClick);
registerStep('type', stepType);
registerStep('fill', stepFill);
registerStep('wait', stepWait);
registerStep('press', stepPress);
registerStep('map', stepMap);
registerStep('filter', stepFilter);
registerStep('sort', stepSort);
registerStep('limit', stepLimit);
registerStep('intercept', stepIntercept);
registerStep('tap', stepTap);
registerStep('download', stepDownload);
```

模版语言 `${{ ... }}` 由 `src/pipeline/template.ts` 实现，能引用 `args`/`data`/`item`/`index` 等上下文变量。

### 形态 D：Electron / 桌面应用（Strategy.UI）

```4:27:clis/codex/history.js
export const historyCommand = cli({
    site: 'codex',
    name: 'history',
    access: 'read',
    description: 'List visible Codex conversation threads grouped by project',
    domain: 'localhost',
    strategy: Strategy.UI,
    browser: true,
    args: [
        { name: 'project', required: false, help: 'Filter by project label or path' },
        { name: 'limit', required: false, help: 'Max conversations per project' },
    ],
    columns: ['Project', 'Index', 'Title', 'Updated', 'Active'],
    func: async (page, kwargs) => {
        const projects = await readCodexProjects(page);
        const rows = flattenCodexProjects(projects, kwargs);
        ...
    },
});
```

`Strategy.UI` + `site` 命中 `isElectronApp(...)` → `getBrowserFactory` 返回 `CDPBridge` → `launcher.ts` 自动起 Electron 应用（带 `--remote-debugging-port`）并连上 CDP。

写法上和形态 B 完全一样，区别只在底层通道。

## 输出 / 错误 / 退出码

### 输出格式：六合一

`src/output.ts` 一处统一：

```39:47:src/output.ts
switch (fmt) {
  case 'json': renderJson(data); break;
  case 'plain': renderPlain(data, opts); break;
  case 'md': case 'markdown': renderMarkdown(data, opts); break;
  case 'csv': renderCsv(data, opts); break;
  case 'yaml': case 'yml': renderYaml(data); break;
  default: renderTable(data, opts); break;
}
```

注意「非 TTY 自动降级」：

```32:34:src/output.ts
if (!opts.fmtExplicit) {
  if (fmt === 'table' && !process.stdout.isTTY) fmt = 'yaml';
}
```

被管道时自动从 table 降到 yaml，**保证 `opencli xxx | jq ...` 不会拿到 ANSI 边框乱码**。

### 错误：统一 envelope + Unix 退出码

```26:36:src/errors.ts
export const EXIT_CODES = {
  SUCCESS:         0,
  GENERIC_ERROR:   1,
  USAGE_ERROR:     2,   // Bad arguments / command misuse
  EMPTY_RESULT:   66,   // No data / not found           (EX_NOINPUT)
  SERVICE_UNAVAIL:69,   // Daemon / browser unavailable  (EX_UNAVAILABLE)
  TEMPFAIL:       75,   // Timeout — try again later     (EX_TEMPFAIL)
  NOPERM:         77,   // Auth required / permission    (EX_NOPERM)
  CONFIG_ERROR:   78,   // Missing / invalid config      (EX_CONFIG)
  INTERRUPTED:   130,
} as const;
```

所有错误都是 `CliError` 的子类，自带 `code / message / hint / exitCode`。`commanderAdapter` 渲染时统一输出 YAML envelope 到 stderr，agent 可直接 parse。

### Observation / Trace

`--trace=on` 或 `--trace=retain-on-failure` 时，`execution.ts` 会启用 `ObservationSession`：捕获网络、console、最终 snapshot、screenshot，落盘成可重放的诊断 artifact。这给"agent 失败时自动诊断"提供了一手物料。

## 扩展点（你能插哪里）

不修改任何核心代码的情况下，OpenCLI 提供 5 个扩展点：

| 扩展类型     | 放在哪里                          | 加载机制              | 详见                           |
| ------------ | --------------------------------- | --------------------- | ------------------------------ |
| 本地 plugin  | `~/.opencli/plugins/<name>/`      | `discoverPlugins`     | [扩展 OpenCLI](../guide/extending-opencli.md) |
| 用户 adapter | `~/.opencli/clis/<site>/<cmd>.js` | `discoverClisFromFs`  | 同上                           |
| Adapter eject | `~/.opencli/clis/` 覆盖内置       | 加载顺序后于内置      | 同上                           |
| 已有 binary 包装 | `~/.opencli/external-clis.yaml` | `external.ts`         | 同上                           |
| Pipeline 步骤 | 在 plugin 里 `registerStep(...)`  | `pipeline/registry.ts` | 自己读 `registry.ts`           |

生命周期钩子 `onStartup / onBeforeExecute / onAfterExecute`（`src/hooks.ts`）也是插件的标准用法，可以做日志、审计、统一拦截。

## 冷启动是怎么优化到极限的

`main.ts` 故意写得啰嗦，几个快路径都在第一时间 `process.exit`：

```49:90:src/main.ts
if (argv[0] === '--version' || argv[0] === '-V') {
  process.stdout.write(PKG_VERSION + '\n');
  process.exit(EXIT_CODES.SUCCESS);
}

if (argv[0] === 'completion' && argv.length >= 2) {
  if (printCompletionScriptFast(argv[1])) {
    process.exit(EXIT_CODES.SUCCESS);
  }
}

const getCompIdx = process.argv.indexOf('--get-completions');
if (getCompIdx !== -1) {
  ...
  if (hasAllManifests(manifestPaths)) {
    const candidates = getCompletionsFromManifest(words, cursor, manifestPaths);
    process.stdout.write(candidates.join('\n') + '\n');
    process.exit(EXIT_CODES.SUCCESS);
  }
}
```

只有走完这些快路径还要继续执行真命令时，才会 `import` 重型模块：

```93:99:src/main.ts
const { discoverClis, discoverPlugins, ... } = await import('./discovery.js');
const { getCompletions } = await import('./completion.js');
const { runCli } = await import('./cli.js');
const { emitHook } = await import('./hooks.js');
...
```

这是 shell completion 不被卡爆的关键。

## 把一条命令端到端串一遍

最后用 `opencli bilibili search "电影" --limit 5 -f json` 走完整条链：

```
1. shell 执行 opencli ...
2. src/main.ts
   - 不是 --version / completion 等快路径
   - import discovery.ts → discoverClis(BUILTIN_CLIS, USER_CLIS) → discoverPlugins()
   - 读 cli-manifest.json 注册 1300+ 命令（其中 bilibili/search 标 _lazy）
   - rewriteBrowserArgv → emitHook('onStartup') → runCli()
3. src/cli.ts → commanderAdapter.registerAllCommands
   - 为 bilibili 创建一个 site Command
   - 为 search 创建子命令，把 `query/type/page/limit` 注册成 positional/options
4. commander 解析 argv，命中 bilibili/search 的 action
5. commanderAdapter.action
   - 收 rawKwargs = { query: '电影', limit: 5, format: 'json' }
   - prepareCommandArgs → coerce limit 为 number 5
   - executeCommand(cmd, kwargs)
6. execution.executeCommand
   - shouldUseBrowserSession(cmd) === true (strategy=COOKIE, browser=true)
   - 非 Electron → BrowserFactory = BrowserBridge
   - browserSession(BrowserBridge, fn)
     - BrowserBridge.connect() → 起 daemon → 等扩展连上
     - 拿到 Page 实例 (session: 'site:bilibili:<uuid>')
     - resolvePreNav → 'https://www.bilibili.com'
     - shouldRunPreNav: ephemeral session → true
     - page.goto('https://www.bilibili.com')
       → HTTP POST /command navigate → daemon → WebSocket → 扩展 →
         chrome.tabs + chrome.debugger Page.navigate → 页面跳转完
     - runWithTimeout(runCommand(cmd, page, kwargs, false))
       - cmd._lazy === true → import(modulePath) → cmd.func 注入
       - cmd.func(page, kwargs)
         - page.evaluate(`async () => fetch('https://api.bilibili.com/x/web-interface/wbi/search/type?...&w_rid=...&wts=...', { credentials: 'include' })`)
           → HTTP POST /command exec → daemon → 扩展 →
             chrome.debugger Runtime.evaluate → 页面发请求 → 拿到 JSON
         - 加工成 [{rank, title, author, score, url}, ...]
     - page.closeWindow() 释放 tab
7. commanderAdapter renderOutput
   - fmt = 'json' → renderJson → console.log(JSON.stringify(rows, null, 2))
8. process.exit(0)
```

每一步在这篇文档里都有源码位置可以追。

## 看完这篇你应该能回答的问题

- **`cli({...})` 一次调用做了哪几件事？**
  归一化 strategy → 注册到全局 Map → 写入 aliases
- **`--version` 为什么 2ms 出结果？**
  快路径直接 exit，没 import discovery / cli / commanderAdapter
- **同一条命令 PUBLIC 和 COOKIE 的区别在执行路径哪里体现？**
  `normalizeCommand` 翻译为 `browser`+`navigateBefore`，再被 `shouldUseBrowserSession` 和 `resolvePreNav` 读取
- **Bridge 通道和 CDP 通道接口一致是怎么做到的？**
  都实现 `IBrowserFactory`，返回的 Page 都继承 `BasePage`，DOM 操作全部下沉到 evaluate 的 JS 字符串
- **想拦截每条命令记日志怎么做？**
  写一个 plugin 注册 `onBeforeExecute` / `onAfterExecute` 钩子
- **想新增一个 pipeline 步骤 `gpt`（调 LLM 加工 data）怎么做？**
  plugin 里 `registerStep('gpt', handler)`，可以选择加入 `BROWSER_ONLY_STEPS`

## 相关阅读

- [Chrome DevTools Protocol（中文）](../advanced/cdp.md) — CDP 通道与元素查找细节
- [Browser Bridge（中文）](../guide/browser-bridge.md) — Bridge 扩展通道的用户视角
- [给新 Electron 应用生成 CLI](../guide/electron-app-cli.md) — Strategy.UI 的实战
- [扩展 OpenCLI](../guide/extending-opencli.md) — plugin / adapter / external CLI 五条路径
- [用 OpenCLI 做 E2E / UI 测试](../guide/e2e-testing.md) — 把这套架构用在测试场景
