# 用 OpenCLI 做 E2E / UI 功能测试

这篇文档回答一个具体问题：

> **能不能用 OpenCLI 给我自家的 Web 系统做 E2E / UI 功能测试？特别是结合 AI agent。**

结论先放在前面：

- **能做，而且在「agent 驱动」场景下比 Playwright / Cypress 等专业测试框架更顺手**
- 但**纯人工写脚本的 Web E2E**，专业测试框架更成熟，不要硬上 OpenCLI
- 推荐架构是 **「agent 录制 + 确定性回放 + agent 自愈」** 三阶段

下面把判断依据、能力边界、推荐架构和最小可行实现都讲清楚。

## 先对齐概念：E2E 测试是什么

End-to-End（端到端）测试 = **模拟一个真实用户，从浏览器入口开始把一条完整业务链路跑完，验证最终结果是不是预期的**。中间经过的前端、网络、后端、数据库、第三方服务**全都是真的**，不打桩。

软件测试通常分三层（"测试金字塔"）：

```
        ▲ 慢、贵、覆盖广、不稳定
        │
   ┌────┴────┐
   │   E2E   │   3%   ← 模拟用户：浏览器点点点跑完整流程
   ├─────────┤
   │集成测试  │  20%   ← 几个模块组合（API + DB 等）
   ├─────────┤
   │ 单元测试 │  77%   ← 单个函数 / 单个组件
   └─────────┘
        │
        ▼ 快、便宜、覆盖窄、稳定
```

| 维度       | 单元测试    | 集成测试       | E2E 测试            |
| ---------- | ----------- | -------------- | ------------------- |
| 测什么     | 一个函数    | 几个模块组合   | 真实用户完整流程    |
| 启动什么   | 只有被测码  | 部分服务       | 整个系统            |
| 用什么调用 | 直接调方法  | 调 API/service | **模拟浏览器点击**  |
| 数据       | mock        | 部分 mock      | 真实数据库          |
| 单次耗时   | 毫秒        | 秒             | 几秒到几分钟        |
| 稳定性     | 极稳        | 较稳           | flaky（容易抖）     |
| 失败定位   | 一眼能定位  | 范围中等       | 不知道哪一环挂了    |

E2E 通常要同时验证四个面：

1. **UI 维度** — 元素出现没、文案对不对、布局没崩
2. **交互维度** — 点击/输入/拖拽/上传链路通不通
3. **接口维度** — 背后调的 API 状态码、关键字段
4. **副作用维度** — 真的写库了吗、控制台有没有报错、埋点有没有发

这四个维度正好对应 OpenCLI 的 `browser state` / `browser click|type` / `browser network` / `browser console`。

## OpenCLI 已有的测试自动化能力

把 `BasePage` + `CDPPage` + `tests/e2e/` 现成代码合在一起，OpenCLI 已经覆盖了 E2E 测试 80% 的基础动作：

| 测试需要的能力           | OpenCLI 对应 API                         | 关键点                                     |
| ------------------------ | ---------------------------------------- | ------------------------------------------ |
| 选择器查找 + 唯一性校验  | `resolveTargetJs`（CSS / ref 双路径）    | 多匹配主动报 `selector_ambiguous`          |
| 点击 / 双击 / 拖拽 / 悬停 | `click / dblClick / drag / hover`        | 优先 `Input.dispatchMouseEvent`，能触发 Radix/MUI |
| 输入 / 填充 / 清空       | `typeText / fillText`                    | 自带 native input 路径，支持受控组件       |
| 单选 / 复选 / 文件上传   | `setChecked / uploadFiles`               | `DOM.setFileInputFiles` 直传               |
| 等待元素 / 文本 / DOM 稳定 | `wait({ selector, text, timeout })`      | 内置 `waitForDomStableJs`                  |
| 截图 / 全页截图 / 标注截图 | `screenshot / annotatedScreenshot`       | 支持 `--full-page`                         |
| 网络抓取 + 断言响应      | `startNetworkCapture / readNetworkCapture` | 单 body 上限 8MB，避免截断丢字段           |
| Console / 未捕获异常     | `consoleMessages('error')`               | 自动把 `Runtime.exceptionThrown` 当 error 收 |
| JS 对话框                | `handleJavaScriptDialog(true)`           | confirm / prompt 都能处理                  |
| cookie / 登录态复用      | CDP `Network.getCookies` + 本机 Chrome profile | **不用维护 storage state**           |
| 测试 runner + fixture    | `tests/e2e/*.test.ts` + vitest           | 已经接好，可直接抄                         |

并且 OpenCLI 专门为 **SPA 重渲染** 做了 `exact / stable / reidentified` 三级容错——这恰恰是大部分 Playwright/Cypress 测试最容易 flaky 的地方。详见 [Chrome DevTools Protocol](/zh/advanced/cdp)。

## 跟专业测试框架的差距

诚实对比，OpenCLI 缺这些东西：

| 能力                           | OpenCLI                              | Playwright |
| ------------------------------ | ------------------------------------ | ---------- |
| 断言 DSL（`expect(el).toBeVisible()`） | 无，要自己写 `evaluate`              | 有         |
| 自动重试断言（auto-retrying assertions）| 无                                   | 有         |
| Test runner（并发 / retry / shard）| 借 vitest，配置自己写                | 内置       |
| Trace viewer / time-travel     | 无                                   | 有         |
| Video 录制                     | 无，只能截图                         | 有         |
| **Network mock / stub / route override** | **只有抓取，没有篡改**         | 有 `page.route()` |
| 跨浏览器（Firefox / WebKit）   | ❌ 只能 Chromium 系                  | 有         |
| 移动模拟（device emulation 全套）| 部分（`Emulation.setDeviceMetricsOverride`）| 完整 |
| HTML 测试报告 / JUnit 输出     | 无                                   | 有         |
| Fixture / 并行 worker 隔离     | 借 vitest                            | 内置       |
| CI 集成                        | 自己组装                             | 一条命令   |

**最关键的缺口是「没有 network stub」** —— 你只能"看到"请求，但不能拦截改返回。做契约测试 / 离线 mock 会比较吃力。

## 场景判断：什么时候该用 OpenCLI

| 你的场景                          | 建议                                                                 |
| --------------------------------- | -------------------------------------------------------------------- |
| 纯 Web 前端的 E2E / 回归测试，人工写脚本 | **不推荐**，直接上 Playwright。它的 auto-waiting、断言库、trace viewer 是为这个生的 |
| 用真实账号登录态做线上巡检 / 监控测试 | **OpenCLI 更优**。复用本机 Chrome profile，省掉认证态管理            |
| Electron 桌面应用功能测试         | **OpenCLI 几乎是当下最方便的方案**。Playwright 桌面支持有限，Spectron 已弃 |
| **AI agent 驱动的 UI / 功能测试** | **OpenCLI 的舒适区**。下面专门展开                                   |
| API / 接口契约测试（带 mock）     | 不推荐，缺 network stub                                              |

## 为什么 agent 驱动测试场景下 OpenCLI 比 Playwright 顺手

| 给 agent 用时的痛点                  | Playwright 的处理                       | OpenCLI 的处理                                                  |
| ------------------------------------ | --------------------------------------- | --------------------------------------------------------------- |
| selector 写不对（agent 凭文本猜 CSS） | 全靠 agent 自己写 `text=` / `role=` selector | **直接给 ref 编号**：`browser state` 返回所有 ref，agent 用 `browser click 42` 即可 |
| 页面重渲染后 selector 失效           | 重新跑 locator，频繁 flaky              | `match_level: stable / reidentified` 三级容错，自动重定位       |
| Radix/MUI 自定义控件 `click` 没反应  | 需要手动 hack `force: true`             | `Input.dispatchMouseEvent` 真实事件链，默认就解决               |
| 上下文越来越长（每次 dump 完整 DOM） | 没原生方案                              | snapshot 内置 ref 编号 + 文本截断 + diff 模式，只给变化部分     |
| agent 怎么知道动作有没有成功         | 自己写 expect                           | 每个动作返回 `{ matches_n, match_level }`，外加 `network`/`console` 旁路验证 |
| 给 agent 的工具描述                  | 自己 wrap                               | `opencli browser --help` 就是 LLM-friendly 的指令集，可直接灌进 system prompt |

特别注意 `snapshot({ source: 'ax' })` 模式（基于 Chrome Accessibility Tree）的输出，是 LLM 一看就懂的结构，且跨 iframe / shadow DOM：

```
button "Sign in" [42]
textbox "Email" [43]
checkbox "Remember me" [44] checked
link "Forgot password?" [45]
```

agent 看到 `[42]`，直接 `opencli browser click 42` 就行，不用猜 selector。这是为这种场景量身定做的。

## 推荐架构：三阶段（Record + Replay + Self-Heal）

如果让 agent 每次都跑一遍真实功能，token 烧得慌、不稳定、还难回溯。推荐这种混合模式：

```
┌───────────────────────────────────────────────────────────────┐
│  Phase 1: 探索 / 录制（agent 介入，每个 case 只跑一次）        │
│                                                                 │
│  [Test Case Markdown]                                          │
│       "用户登录后能创建订单并看到订单号"                         │
│           │                                                     │
│           ▼                                                     │
│  Agent loop（LLM + opencli browser）：                          │
│    1. browser open <url>                                       │
│    2. browser state --source ax  →  看到 ref 列表                │
│    3. 决策：click ref=42（登录按钮）                             │
│    4. 用 browser network / console 验证副作用                    │
│    5. 重复 2-4 直到 case 完成                                    │
│           │                                                     │
│           ▼                                                     │
│  生成可重放脚本（脚本里只剩动作 + 断言，无 LLM）                  │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Phase 2: CI 回放（每次提交自动跑，0 token）                    │
│                                                                 │
│  vitest run tests/regression/                                  │
│    → opencli browser 系列命令按录制顺序回放                       │
│    → 任一断言失败 → 自动触发 agent「修复」流程                    │
└───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────┐
│  Phase 3（可选）: agent 自愈                                    │
│                                                                 │
│  回放失败时，把失败前后的 snapshot + 错误信息丢给 agent，         │
│  让它判断是「功能 bug」还是「ui 改了，脚本需更新」                  │
└───────────────────────────────────────────────────────────────┘
```

**为什么这样设计**：

- agent 介入只在「新 case」和「失败诊断」时发生，平时回归 0 LLM 成本
- 录制脚本可以 git diff、code review、人工修改，不是黑盒
- 失败有 snapshot + 网络 + console 三路证据，agent 诊断时上下文足够

## 最小可行实现

### 1. 测试用例用自然语言写

```markdown
<!-- tests/cases/checkout.md -->
# 用户能完成下单流程

## 前置
- 已登录账号: test@example.com
- 购物车空

## 步骤
1. 打开商品详情页 https://shop.example.com/p/123
2. 点击「加入购物车」
3. 进入购物车页面
4. 点击「去结算」
5. 选择默认地址，点击「提交订单」

## 验收
- 看到「下单成功」提示
- 调用 /api/order/create 返回 200，body.orderId 非空
- console 没有 error
```

### 2. Agent 录制循环（伪代码）

```typescript
import { runCli, parseJsonOutput } from './e2e/helpers.js';

async function recordCase(caseMd: string) {
  const steps: RecordedStep[] = [];

  await runCli(['browser', 'open', extractUrl(caseMd)]);

  while (!done) {
    const snapshot = parseJsonOutput(
      (await runCli(['browser', 'state', '--source', 'ax', '--interactive'])).stdout,
    );

    const action = await llm.next({
      system: AGENT_SYSTEM_PROMPT,
      tools: OPENCLI_TOOLS_DESC,
      case: caseMd,
      snapshot,
      history: steps,
    });

    if (action.tool === 'done') break;

    const result = await runCli(['browser', ...action.args]);
    steps.push({ args: action.args, result, snapshotHash: hash(snapshot) });
  }

  return generateReplayScript(steps);
}
```

### 3. 录制结果生成的可重放脚本

```typescript
// tests/regression/checkout.test.ts （自动生成 + 人工 review）
import { describe, it, expect } from 'vitest';
import { runCli, parseJsonOutput } from './helpers.js';

describe('checkout', () => {
  it('user can complete order', async () => {
    await runCli(['browser', 'open', 'https://shop.example.com/p/123']);

    await runCli(['browser', 'click', 'button.add-to-cart']);
    await runCli(['browser', 'wait', '--selector', '.cart-success-toast']);

    await runCli(['browser', 'open', 'https://shop.example.com/cart']);

    await runCli(['browser', 'network', 'start', '--pattern', '/api/order/create']);
    await runCli(['browser', 'click', 'button.checkout']);
    await runCli(['browser', 'click', 'button.submit-order']);

    await runCli(['browser', 'wait', '--text', '下单成功', '--timeout', '10']);

    const requests = parseJsonOutput(
      (await runCli(['browser', 'network', 'read'])).stdout,
    );
    const orderApi = requests.find((r) => r.url.includes('/api/order/create'));
    expect(orderApi.responseStatus).toBe(200);
    expect(JSON.parse(orderApi.responsePreview).orderId).toBeTruthy();

    const errors = parseJsonOutput(
      (await runCli(['browser', 'console', '--level', 'error'])).stdout,
    );
    expect(errors).toHaveLength(0);
  });
});
```

### 4. agent system prompt 关键片段

```
你是 web 功能测试 agent。每一步通过下面工具操作页面：

- browser state --source ax           # 拿当前可交互元素的 ref 树
- browser click <ref>                 # 点击 ref 编号的元素
- browser type <ref> "<text>"         # 在 ref 输入框输入
- browser wait --text "..." --timeout 10
- browser network start --pattern <url>    # 开始抓接口
- browser network read                     # 读已抓到的接口
- browser console --level error            # 检查 JS 报错

规则：
1. 每次动作前必须先 state，不要凭记忆点 ref（页面会变）
2. 优先用 ref（数字），CSS selector 只在 ref 不够稳定时用
3. 每个验收点必须用 state / network / console 之一证明
4. 不要硬等 sleep，用 wait --selector / --text
```

## 你需要自己补的几样东西

OpenCLI 现成的覆盖了执行层，agent 测试还差这几块（都不大）：

1. **断言 helper 库** — 把「检查 toast 出现」「检查接口 200」「检查 console 无 error」封装成稳定 helper
2. **测试用例 → agent prompt 转换器** — 上面那种 markdown 解析
3. **录制结果 → 回放脚本生成器** — 最有价值的一块，把 agent 的探索结果固化
4. **失败诊断器** — 失败时把 snapshot + diff + 网络 + console 打包给 agent
5. **CI 集成** — vitest + GitHub Actions，仓库内 `tests/e2e/helpers.ts` 可以照抄

## 一个反向建议

**别把测试用例写成「测试脚本」，写成「业务行为契约」**：

```markdown
behaviors/order.md
  - 用户登录后能下单
  - 库存不足时下单返回友好提示
  - 未登录用户点下单跳转到登录页
```

这套契约 agent 既能用它**录制回归用例**，也能用它**做日常监控**（线上巡检），还能在产品改版时**自动发现哪些 case 需要更新**。

跑通后，你拥有的是：**一份契约 + 一组可执行回归 + 一个能自愈的 agent**，比传统 E2E 测试 (Cypress / Playwright) 的维护成本低一个数量级，但底层执行能力一点不弱（因为底层用的还是 CDP）。

## 常见问题

### Q：那我现在 Playwright / Cypress 的资产怎么办

不用废。两套并存最稳：

- **关键路径回归**继续 Playwright（成熟、生态好、报告美观）
- **新功能验证 / 探索式测试 / 长链路业务流**用 OpenCLI + agent
- **线上巡检 / 真实账号监控**完全切到 OpenCLI（复用登录态简单）

### Q：每个 case 都要烧 LLM token 吗

不需要。Phase 1 录制一次，之后 Phase 2 回放是纯 CLI 调用，0 token。只有产品改版导致回放失败，Phase 3 才会再次唤醒 agent。

### Q：UI 大改一次，所有脚本是不是全废

不会。`match_level: reidentified` 兜底能吸收大部分变更；真彻底改了的 case 才需要 agent 重录，且**目标契约（"用户能下单"）不变，agent 只是探索新路径**。

### Q：跟 Bridge 扩展、CDP 模式有什么关系

完全无关。本地有 GUI 就用 Bridge 扩展（参见 [Browser Bridge](/zh/guide/browser-bridge)），无头服务器或要直连 Electron 就用 CDP 模式（参见 [Chrome DevTools Protocol](/zh/advanced/cdp)）。两种模式下 `browser xxx` 命令完全一致，测试脚本不用改。

### Q：能不能不走 agent，纯人工写 OpenCLI 测试脚本

能，但**不如直接用 Playwright**。OpenCLI 没有 auto-waiting、retry、parallel runner、trace viewer 这些专业测试框架的"基本盘"，人工写脚本时这些东西天天要用。

## 相关阅读

- [Chrome DevTools Protocol（中文）](/zh/advanced/cdp) — 底层协议与元素查找原理
- [Browser Bridge（中文）](/zh/guide/browser-bridge) — 本机有 GUI 时的扩展模式
- [给新 Electron 应用生成 CLI](/zh/guide/electron-app-cli) — 桌面应用适配
- [扩展 OpenCLI](/zh/guide/extending-opencli) — 写自己的适配器
