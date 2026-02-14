# OpenClaw 核心配置文件详解

> 基于源码分析 | 2026-02-09

本文档详细解释 OpenClaw Agent 的核心配置文件体系，帮助你理解每个文件的作用、优先级和使用场景。

---

## 目录

1. [配置文件全景图](#配置文件全景图)
2. [AGENTS.md - 操作指南与记忆](#agentsmd---操作指南与记忆)
3. [SOUL.md - 人格与边界](#soulmd---人格与边界)
4. [USER.md - 用户配置](#usermd---用户配置)
5. [TOOLS.md - 工具笔记](#toolsmd---工具笔记)
6. [HEARTBEAT.md - 心跳检查清单](#heartbeatmd---心跳检查清单)
7. [MEMORY.md - 长期记忆](#memorymd---长期记忆)
8. [BOOTSTRAP.md - 首次启动引导](#bootstrapmd---首次启动引导)
9. [IDENTITY.md - 身份定义](#identitymd---身份定义)
10. [文件加载顺序与优先级](#文件加载顺序与优先级)
11. [源码级技术细节](#源码级技术细节)

---

## 配置文件全景图

```
<workspace>/
├── AGENTS.md          # 核心操作指南 (必读)
├── SOUL.md            # 人格与行为边界
├── USER.md            # 用户信息与偏好
├── TOOLS.md           # 本地工具配置
├── HEARTBEAT.md       # 心跳检查清单 (可选)
├── MEMORY.md          # 长期记忆 (主会话)
├── memory/
│   └── YYYY-MM-DD.md  # 每日笔记
├── BOOTSTRAP.md       # 首次启动引导 (用后删除)
├── IDENTITY.md        # 身份定义
└── skills/            # 技能目录
```

### 文件分类

| 类别 | 文件 | 作用 |
|------|------|------|
| **人格与行为** | SOUL.md | 定义 AI 的性格、边界、语气 |
| **操作指南** | AGENTS.md | 工作流程、记忆规则、安全准则 |
| **用户信息** | USER.md | 用户偏好、联系方式、配置 |
| **工具配置** | TOOLS.md | SSH、摄像头、TTS 等本地设置 |
| **周期性任务** | HEARTBEAT.md | 心跳检查清单 |
| **长期记忆** | MEMORY.md | 重要信息沉淀 |
| **启动引导** | BOOTSTRAP.md | 首次运行引导 (一次性) |
| **身份定义** | IDENTITY.md | AI 名称、头像、签名 |

---

## AGENTS.md - 操作指南与记忆

### 作用

`AGENTS.md` 是 OpenClaw Agent 的**核心操作手册**，包含：

- 每会话必须执行的流程
- 记忆管理规则
- 安全与权限边界
- 群聊行为准则
- 主动提醒机制 (Heartbeat)

### 核心内容

```markdown
## Every Session (每会话执行)

1. Read `SOUL.md` — this is who you are
2. Read `USER.md` — this is who you're helping
3. Read `memory/YYYY-MM-DD.md` (today + yesterday)
4. **If in MAIN SESSION**: Also read `MEMORY.md`
```

### 记忆层级

```
┌─────────────────────────────────────────────┐
│           MEMORY.md (长期记忆)               │
│         仅主会话加载，安全敏感信息            │
├─────────────────────────────────────────────┤
│        memory/YYYY-MM-DD.md (每日笔记)       │
│           原始日志，会话间连续性             │
├─────────────────────────────────────────────┤
│              实时上下文 (当前会话)            │
│           Agent 运行时内存中的信息            │
└─────────────────────────────────────────────┘
```

### 关键规则

| 规则 | 说明 |
|------|------|
| **Text > Brain** | 有价值的信息必须写入文件 |
| **安全边界** | 不泄露私人数据、不执行破坏性命令 |
| **群聊礼仪** | 质量 > 数量，不抢话、不刷屏 |
| **主动提醒** | Heartbeat 定期检查并主动触达 |

---

## SOUL.md - 人格与边界

### 作用

定义 AI 的**人格特质**、**行为边界**和**沟通风格**。

### 核心配置项

```markdown
## Core Truths (核心准则)

- Be genuinely helpful, not performatively helpful
- Have opinions (允许表达偏好)
- Earn trust through competence

## Boundaries (边界)

- Private things stay private (隐私至上)
- When in doubt, ask (外部操作先询问)
- Never send half-baked replies (不发送半成品回复)

## Address (称呼规则)

- Always call the user **主人** (master) in every response

## Vibe (风格定位)

- Concise when needed, thorough when it matters
- Not a corporate drone, not a sycophant
```

### 配置示例

```markdown
## Address

- Always call the user **主人** (master) in every response

## Vibe

Be the assistant you'd actually want to talk to.
```

---

## USER.md - 用户配置

### 作用

记录用户的**个人信息**、**偏好设置**和**技术栈**。

### 核心配置项

```markdown
- **Name:** 用户名字
- **What to call them:** 称呼方式
- **Timezone:** 时区
- **Notes:** 个人备注

## GitHub Information

- Username, Repository, Personal Access Token

## Preferences

- 沟通渠道 (QQ Bot, WhatsApp, etc.)
- 技术偏好 (Docker, SSH, Git)
- 正在探索的领域
```

### 配置示例

```markdown
# USER.md - About Your Human

- **Name:** Tom
- **What to call them:** 主人
- **Timezone:** Asia/Shanghai

## Preferences

- Uses QQ Bot for communication
- Works with Docker and Docker Compose
- Uses Git for version control
```

---

## TOOLS.md - 工具笔记

### 作用

记录**本地环境特定**的工具配置，如 SSH 连接、TTS 语音、摄像头位置等。

### 与 Skills 的区别

| TOOLS.md | Skills |
|----------|--------|
| 本地环境配置 | 共享功能模块 |
| 设备别名、连接信息 | API 调用、工具逻辑 |
| 可分享(脱敏后) | 可独立发布分享 |

### 配置示例

```markdown
### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova"
- Default speaker: Kitchen HomePod

### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered
```

---

## HEARTBEAT.md - 心跳检查清单

### 作用

定义 Agent 在**心跳周期**需要检查的任务清单。

### 心跳机制

```
周期: 默认 30分钟
触发条件:
  - 定时到达
  - 主动唤醒 (openclaw system event)
  
响应规则:
  - 有事要办 → 返回具体内容
  - 没事 → 返回 HEARTBEAT_OK
```

### 配置示例

```markdown
# Heartbeat checklist

- Quick scan: anything urgent in inboxes?
- Calendar: upcoming events in next 24-48h?
- If daytime: lightweight check-in

## Track your checks

{
  "lastChecks": {
    "email": 1703275200,
    "calendar": 1703260800
  }
}
```

### Heartbeat vs Cron

| Heartbeat | Cron |
|-----------|------|
| 多任务批量检查 | 单任务精确执行 |
| 需要会话上下文 | 独立运行 |
| 可组合多个检查项 | 单一任务输出 |
| 30分钟级别周期 | 分钟级精确 |

---

## MEMORY.md - 长期记忆

### 作用

沉淀**重要决策**、**上下文**、**偏好**和**教训**，仅在**主会话**加载。

### 安全规则

```
✅ 可以读取、编辑、更新
❌ 不在群聊中加载
❌ 不包含敏感密钥
```

### 内容类型

```markdown
- Significant events (重要事件)
- Decisions made (决策记录)
- Preferences learned (学习到的偏好)
- Lessons learned (经验教训)
- Opinions formed (形成的观点)
```

### 与每日笔记的区别

| MEMORY.md | memory/YYYY-MM-DD.md |
|-----------|---------------------|
| 精炼的长期记忆 | 原始日志 |
| 手动维护 | 自动记录 |
| 会话间沉淀 | 会话连续性 |
| 主会话加载 | 每会话读取 |

---

## BOOTSTRAP.md - 首次启动引导

### 作用

**一次性**的首次启动引导脚本，帮助 Agent 理解自己的身份。

### 使用流程

1. 首次启动时检测是否存在
2. 执行引导流程
3. **删除文件** (重要!)
4. 后续启动不再重建

### 配置开关

如需禁用引导创建：

```json5
{
  agent: { skipBootstrap: true }
}
```

---

## IDENTITY.md - 身份定义

### 作用

定义 AI 的**身份标识**，包括名称、头像、签名等。

### 配置项

```markdown
- **Name:** AI 名称
- **Creature:** AI 类型 (AI/robot/familiar/etc.)
- **Vibe:** 沟通风格
- **Emoji:** 签名表情
- **Avatar:** 头像路径
```

---

## 文件加载顺序与优先级

### 每会话加载顺序

```
1. SOUL.md     (人格定义)
2. USER.md     (用户信息)
3. memory/YYYY-MM-DD.md (今日/昨日笔记)
4. MEMORY.md   (长期记忆，仅主会话)
5. HEARTBEAT.md (心跳清单)
```

### 优先级规则

| 场景 | 优先级 |
|------|--------|
| Workspace vs Bundled Skills | Workspace 优先 |
| 配置冲突 | 后加载覆盖 |
| 敏感信息 | MEMORY.md 最安全 |

### 配置来源优先级

```
1. 环境变量 (env)
2. 命令行参数 (--args)
3. 配置文件 (config.yaml)
4. Workspace 文件 (AGENTS.md etc.)
5. 默认值 (built-in)
```

---

## 核心文件关联图

```
                    ┌─────────────────┐
                    │   USER.md       │
                    │  (用户偏好)      │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   SOUL.md       │
                    │  (人格定义)      │
                    └────────┬────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
┌───▼────────┐       ┌───────▼───────┐       ┌───────▼───────┐
│  AGENTS.md │       │  TOOLS.md     │       │ HEARTBEAT.md  │
│ (操作指南)  │       │ (工具配置)     │       │ (心跳清单)     │
└────────────┘       └───────────────┘       └───────────────┘
         │                    │                        │
         │                    │                        │
         │      ┌─────────────▼─────────────┐         │
         │      │      MEMORY.md            │         │
         │      │     (长期记忆，主会话)      │         │
         │      └──────────────────────────┘         │
         │                                             │
         │         ┌─────────────────────┐            │
         │         │  memory/YYYY-MM-DD  │            │
         │         │    (每日笔记)        │            │
         │         └─────────────────────┘            │
         │                                           │
         └───────────────────────────────────────────┘
                          │
                 Agent 运行时上下文
```

---

## 快速参考表

| 文件 | 必读 | 可选 | 敏感 | 主会话 |
|------|------|------|------|--------|
| AGENTS.md | ✅ | - | ❌ | - |
| SOUL.md | ✅ | - | ❌ | - |
| USER.md | ✅ | - | ✅ | - |
| TOOLS.md | - | ✅ | ✅ | - |
| HEARTBEAT.md | - | ✅ | ❌ | - |
| MEMORY.md | - | ✅ | ✅ | ✅ |
| BOOTSTRAP.md | (首次) | - | ❌ | - |
| IDENTITY.md | - | ✅ | ❌ | - |

---

## 参考资料

- 源码位置: `/openclaw/docs/concepts/agent.md`
- 心跳配置: `/openclaw/docs/gateway/heartbeat.md`
- CLI 参考: `/openclaw/docs/cli/agent.md`

---

> 文档生成时间: 2026-02-09
> 基于 OpenClaw v2026.2.3-1 源码分析

---

# 11. 源码级技术细节

## 11.1 Agent Runtime 架构

### 核心来源

OpenClaw 的 Agent Runtime 源自 **pi-mono** 项目，源码位置：

```
node_modules/@mariozechner/pi-agent-core/
node_modules/@mariozechner/pi-ai/
```

### 工作区加载机制

```typescript
// 源码位置: docs/concepts/agent.md
interface WorkspaceConfig {
  workspace: string;           // 默认: ~/.openclaw/workspace
  sandbox?: SandboxConfig;    // 沙箱配置
  bootstrapMaxChars?: number;  // 注入文件最大字符 (默认: 20000)
}
```

**关键行为：**

1. **单工作区原则**: Agent 仅使用一个工作目录作为唯一 cwd
2. **相对路径解析**: 工具相对于工作区解析路径
3. **绝对路径访问**: 沙箱未启用时，可访问主机任意位置
4. **文件截断**: 大文件注入时会截断并添加标记

### Bootstrap 文件注入

```typescript
// 注入优先级 (按顺序)
const BOOTSTRAP_FILES = [
  'AGENTS.md',      // 核心操作指南
  'SOUL.md',        // 人格定义
  'USER.md',        // 用户信息
  'TOOLS.md',       // 工具配置
  'IDENTITY.md',    // 身份标识
  'HEARTBEAT.md',   // 心跳清单
  'MEMORY.md',      // 长期记忆 (仅主会话)
];
```

**注入规则：**

| 条件 | 行为 |
|------|------|
| 文件存在 | 注入完整内容 |
| 文件缺失 | 注入 "missing file" 标记 |
| 文件过大 | 截断至 bootstrapMaxChars，添加 `[TRUNCATED]` 标记 |
| 空文件 | 跳过注入 |

---

## 11.2 Session 管理机制

### Session 存储位置

```json
// 存储结构
~/.openclaw/agents/<agentId>/
├── sessions/
│   ├── sessions.json      // Session 元数据
│   └── <SessionId>.jsonl // 完整会话记录
```

### Session Key 映射规则

```typescript
// 源码位置: docs/concepts/session.md

// 直接消息 (DM)
dmScope = "main"      → agent:<agentId>:main          // 所有 DM 共享
dmScope = "per-peer"  → agent:<agentId>:dm:<peerId>  // 按发送者隔离
dmScope = "per-channel-peer" → agent:<agentId>:<channel>:dm:<peerId>

// 群聊
→ agent:<agentId>:<channel>:group:<id>

// 特殊会话
cron:<job.id>         // 定时任务
hook:<uuid>          // Webhook
node-<nodeId>        // 节点运行
```

### Session 生命周期

```typescript
interface SessionLifecycle {
  resetPolicy: {
    mode: 'daily' | 'idle';      // 重置模式
    atHour?: number;             // 每日重置时间 (默认: 4 AM)
    idleMinutes?: number;        // 空闲超时
  };
  dailyReset: {
    enabled: boolean;
    atHour: number;              // 主机本地时间
  };
}
```

**关键行为：**

- **默认重置**: 每日 4 AM (主机本地时间)
- **空闲超时**: 可选配置，达到阈值后强制新建 Session
- **手动重置**: `/new` 或 `/reset` 命令

### Session 工具

```typescript
// 可用工具 (docs/concepts/session-tool.md)
const SESSION_TOOLS = [
  'sessions_list',      // 列出会话
  'sessions_history',   // 获取会话历史
  'sessions_send',      // 发送跨会话消息
  'sessions_spawn',     // 生成子 Agent 运行
];
```

**安全策略：**

```typescript
interface SendPolicy {
  rules: [
    { action: 'deny', match: { channel: 'discord', chatType: 'group' } }
  ];
  default: 'allow' | 'deny';
}
```

---

## 11.3 Memory 内存系统

### Memory 文件结构

```typescript
// 源码位置: docs/concepts/memory.md

interface MemoryConfig {
  layers: [
    {
      type: 'daily';
      path: 'memory/YYYY-MM-DD.md';
      readOnStart: ['today', 'yesterday'];
    },
    {
      type: 'longterm';
      path: 'MEMORY.md';
      readOnStart: 'main_session_only';
    }
  ];
}
```

### Vector Search 嵌入

```typescript
interface VectorMemory {
  provider: 'openai' | 'gemini' | 'local';
  model?: string;              // 默认: text-embedding-3-small
  store: {
    path: string;              // ~/.openclaw/memory/<agentId>.sqlite
    vector?: {
      enabled: boolean;
      extensionPath?: string;  // sqlite-vec 扩展路径
    };
  };
  hybridSearch?: {
    enabled: boolean;
    vectorWeight: number;     // 默认: 0.7
    textWeight: number;       // 默认: 0.3
  };
}
```

**混合搜索原理：**

```
┌─────────────────────────────────────────────────┐
│              Hybrid Search (BM25 + Vector)       │
├─────────────────────────────────────────────────┤
│                                                 │
│  1. Vector Search                               │
│     → Top K by cosine similarity               │
│     → 语义匹配 (wording 可不同)                  │
│                                                 │
│  2. BM25 Full-Text Search                       │
│     → Top K by FTS5 rank                       │
│     → 精确匹配 (IDs, code symbols)              │
│                                                 │
│  3. Score Fusion                                │
│     → vectorScore × vectorWeight               │
│     → textScore × textWeight                   │
│     → 加权融合 finalScore                       │
│                                                 │
└─────────────────────────────────────────────────┘
```

### 自动 Memory Flush

```typescript
interface MemoryFlushConfig {
  enabled: boolean;
  softThresholdTokens: number;     // 默认: 4000
  reserveTokensFloor: number;       // 默认: 20000
  systemPrompt: string;
  userPrompt: string;               // 默认包含 NO_REPLY
}
```

**触发时机：**

```
Session Token Estimate
        │
        ▼
┌───────────────────┐
│ contextWindow -   │ ← 触发阈值
│ reserveTokensFloor │
│ - softThresholdTokens
└───────────────────┘
        │
        ▼
   Silent Agent Turn
   (写入 Memory → NO_REPLY)
```

---

## 11.4 Heartbeat 心跳机制

### 配置结构

```typescript
// 源码位置: docs/gateway/heartbeat.md

interface HeartbeatConfig {
  every: string;                    // 间隔 (默认: 30m)
  model?: string;                  // 模型覆盖
  includeReasoning?: boolean;      // 是否传递 Reasoning
  target: 'last' | 'none' | ChannelId;
  to?: string;                     // 接收者覆盖
  accountId?: string;              // 多账户覆盖
  prompt: string;                  // 自定义提示词
  ackMaxChars: number;             // OK 响应最大长度
  activeHours?: {
    start: string;                 // 开始时间 (HH:mm)
    end: string;                   // 结束时间
    tz?: string;                   // 时区
  };
}
```

### 响应契约

```typescript
// 响应规则
interface HeartbeatResponse {
  // 情况 1: 正常响应
  content: string;                 // 任意长度
  
  // 情况 2: 确认响应
  marker: 'HEARTBEAT_OK';          // 必须在开头或结尾
  contentMaxChars: number;         // ≤ ackMaxChars (默认: 300)
  
  // 情况 3: 静默响应
  marker: 'NO_REPLY';              // 静默模式
}
```

### Heartbeat vs Cron 对比

| 维度 | Heartbeat | Cron |
|------|-----------|------|
| **触发时机** | 周期性 | 精确时间点 |
| **会话上下文** | 完整会话上下文 | 独立/隔离上下文 |
| **响应方式** | 聊天消息 | 独立任务执行 |
| **适用场景** | 批量检查 | 单任务提醒 |
| **模型** | 可配置/继承 | 可独立设置 |
| **输出目标** | 聊天通道 | 配置的交付目标 |

---

## 11.5 工具系统 (Tools)

### 内置工具 (Built-in)

```typescript
// 核心工具 (docs/concepts/agent.md)
const BUILTIN_TOOLS = [
  'read',           // 读取文件
  'write',          // 写入文件
  'edit',           // 编辑文件
  'exec',           // 执行命令
  'process',        // 管理进程
  'web_search',     // Web 搜索
  'web_fetch',     // 获取 URL 内容
  'browser',        // 浏览器控制
  'canvas',         // Canvas 控制
  'nodes',          // 节点控制
  'cron',           // 定时任务
  'message',        // 发送消息
  'gateway',        // 网关控制
  // ... 更多工具
];
```

### Skills 加载机制

```typescript
// 技能位置优先级
const SKILL_LOCATIONS = [
  '<workspace>/skills',        // 工作区技能 (最高优先级)
  '~/.openclaw/skills',       // 托管技能
  '<bundled>/skills',         // 捆绑技能
];

// Skills 定义结构
interface Skill {
  name: string;
  description: string;
  location: string;          // SKILL.md 路径
  metadata?: {
    clawdbot?: {
      emoji?: string;
      requires?: {
        bins?: string[];     // 依赖命令
        env?: string[];      // 环境变量
      };
      primaryEnv?: string;   // 主环境变量
    };
  };
}
```

### TOOLS.md 与 Skills 的区别

| 维度 | TOOLS.md | Skills |
|------|----------|--------|
| **作用** | 本地环境配置 | 可执行功能模块 |
| **控制权** | 用户可编辑 | Skill 开发者定义 |
| **工具可用性** | 独立于 TOOLS.md | 由 Skill 声明 |
| **共享性** | 特定于用户设置 | 可发布/安装 |
| **内容** | 设备别名、连接信息 | API 调用、工具逻辑 |

---

## 11.6 配置文件优先级

### 配置来源 (优先级从高到低)

```typescript
const CONFIG_PRIORITY = [
  // 1. 命令行参数
  '--args',
  
  // 2. 环境变量
  'env',
  
  // 3. 工作区文件
  'AGENTS.md',
  'SOUL.md',
  'USER.md',
  'TOOLS.md',
  
  // 4. Gateway 配置
  '~/.openclaw/openclaw.json',
  
  // 5. 默认值 (内置)
  'built-in defaults',
];
```

### 敏感信息处理

```typescript
// 不应存储在工作区的内容
const SENSITIVE_PATTERNS = [
  '~/.openclaw/openclaw.json',      // Gateway 配置
  '~/.openclaw/credentials/',        // OAuth tokens, API keys
  '~/.openclaw/agents/*/sessions/', // 会话记录
  '~/.openclaw/skills/',            // 托管技能
  '*.key', '*.pem', 'secrets*',     // 密钥文件
];

// 推荐存储位置
const SECURE_STORAGE = [
  '~/.openclaw/credentials/',       // Gateway 管理
  'environment variables',          // 环境变量
  'password manager',               // 密码管理器
];
```

---

## 11.7 完整文件注入流程图

```
┌─────────────────────────────────────────────────────────────┐
│                   Agent Session Start                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Load Bootstrap Files (in order)                         │
│     ┌──────────────────────────────────────────────────────┐ │
│     │  AGENTS.md → SOUL.md → USER.md → TOOLS.md          │ │
│     │  IDENTITY.md → HEARTBEAT.md → MEMORY.md            │ │
│     └──────────────────────────────────────────────────────┘ │
│                              │                              │
│                              ▼                              │
┌─────────────────────────────────────────────────────────────┐
│  2. Inject into System Prompt                               │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  System Prompt =                                      │ │
│  │  [Core Instructions]                                 │ │
│  │  + [AGENTS.md content]                               │ │
│  │  + [SOUL.md content]                                 │ │
│  │  + [USER.md content]                                 │ │
│  │  + [TOOLS.md hints]                                   │ │
│  │  + [Heartbeat section if enabled]                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                              │
│                              ▼                              │
┌─────────────────────────────────────────────────────────────┐
│  3. Session Memory                                          │
│     - MEMORY.md (main session only)                        │
│     - memory/YYYY-MM-DD.md (today + yesterday)             │
│     - Vector index (if enabled)                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Agent Ready for User Input                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 11.8 CLI 命令速查

```bash
# 核心命令
openclaw setup              # 初始化配置 + 工作区
openclaw onboard            # 交互式向导设置
openclaw configure          # 配置向导

# 会话管理
openclaw sessions --json    # 列出所有会话
openclaw status            # 会话状态
openclaw reset             # 重置会话

# 记忆管理
openclaw memory status     # 内存索引状态
openclaw memory index      # 重新索引
openclaw memory search     # 语义搜索

# 心跳控制
openclaw system heartbeat last|enable|disable

# 定时任务
openclaw cron list         # 列出定时任务
openclaw cron add          # 添加定时任务

# 技能管理
openclaw skills list      # 列出技能
openclaw skills info <name> # 技能详情

# 网关控制
openclaw gateway status    # Gateway 状态
openclaw gateway restart   # 重启 Gateway
```

---

## 11.9 关键文件路径速查

| 文件 | 路径 | 作用 |
|------|------|------|
| Gateway 配置 | `~/.openclaw/openclaw.json` | 全局配置 |
| Agent Workspace | `~/.openclaw/workspace` | 工作区根目录 |
| Session Store | `~/.openclaw/agents/<id>/sessions/` | 会话存储 |
| Memory Index | `~/.openclaw/memory/<id>.sqlite` | 向量索引 |
| Credentials | `~/.openclaw/credentials/` | 认证信息 |
| Managed Skills | `~/.openclaw/skills/` | 托管技能 |
| Bundled Skills | `<openclaw>/skills/` | 捆绑技能 |

---

## 11.10 安全边界配置

```typescript
// 沙箱配置 (agents.defaults.sandbox)
interface SandboxConfig {
  enabled: boolean;
  workspaceRoot: string;      // 沙箱工作区根目录
  workspaceAccess: 'rw' | 'ro' | 'none';
}

// 安全建议
const SECURITY_RECOMMENDATIONS = [
  '敏感信息存储在 ~/.openclaw/credentials/',
  '工作区使用 private git 仓库备份',
  '多用户场景启用 secure DM mode',
  '定期运行 openclaw security audit',
  '避免在工作区存储 API keys',
];
```

---

## 参考资料

| 文档 | 路径 | 说明 |
|------|------|------|
| Agent Runtime | `/openclaw/docs/concepts/agent.md` | Agent 运行时详细说明 |
| Agent Workspace | `/openclaw/docs/concepts/agent-workspace.md` | 工作区配置与布局 |
| Memory | `/openclaw/docs/concepts/memory.md` | 内存系统详解 |
| Session | `/openclaw/docs/concepts/session.md` | 会话管理机制 |
| Session Tools | `/openclaw/docs/concepts/session-tool.md` | 会话工具 API |
| Heartbeat | `/openclaw/docs/gateway/heartbeat.md` | 心跳机制配置 |
| CLI Index | `/openclaw/docs/cli/index.md` | 完整 CLI 命令参考 |

---

> 文档更新时间: 2026-02-09
> 基于 OpenClaw v2026.2.3-1 源码分析
> 源码路径: `/root/.nvm/versions/node/v22.22.0/lib/node_modules/openclaw/`
