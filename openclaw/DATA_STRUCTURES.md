# OpenClaw 核心数据结构

## 概述

OpenClaw 是一个多平台 AI 助手框架，支持跨多个通信平台（如 Discord、Telegram、Slack、iMessage 等）的统一对话体验。系统采用模块化架构设计，核心组件包括消息系统、会话系统、Agent 系统、工具系统、通道系统、记忆系统和 Gateway 服务。

本文档详细分析 OpenClaw 的核心数据结构及其相互关系。

---

## 1. 消息系统

### 1.1 消息类型定义

```mermaid
classDiagram
    class ChannelMessageActionName {
        <<type alias>>
    }
    
    class AgentMessage {
        <<interface>>
        +role: "user" | "assistant" | "tool" | "system"
        +content: string | array
        +tool_call_id?: string
        +tool_name?: string
        +tool_use_id?: string
        +is_antthinking?: boolean
        +timestamp?: number
    }
    
    class ReplyPayload {
        <<interface>>
        +text?: string
        +blocks?: array
        +action?: ChannelMessageActionName
        +replyTo?: string
    }
    
    class ChannelOutboundContext {
        <<interface>>
        +cfg: OpenClawConfig
        +to: string
        +text: string
        +mediaUrl?: string
        +gifPlayback?: boolean
        +replyToId?: string | null
        +threadId?: string | number | null
        +accountId?: string | null
    }
```

### 1.2 消息状态流转

```mermaid
stateDiagram-v2
    [*] --> Created: 新消息创建
    
    Created --> Queued: 加入发送队列
    Queued --> Processing: 开始处理
    
    Processing --> Sending: 执行发送
    Sending --> Sent: 发送成功
    
    Processing --> Error: 发送失败
    Error --> Queued: 重试队列
    
    Sent --> Delivered: 确认送达
    Delivered --> [*]
    
    Error --> [*]: 永久失败
```

### 1.3 通道消息格式

```typescript
// 核心消息类型定义
interface ChannelMessage {
  channel: ChannelId;
  from: string;
  to: string;
  content: string;
  timestamp: number;
  threadId?: string | number;
  replyToId?: string;
  media?: ChannelMedia[];
  metadata?: Record<string, unknown>;
}

interface ChannelMedia {
  type: "image" | "video" | "audio" | "file";
  url: string;
  mimeType?: string;
  size?: number;
}
```

---

## 2. 会话系统

### 2.1 会话数据结构

```mermaid
classDiagram
    class GatewaySessionRow {
        <<interface>>
        +key: string
        +kind: "direct" | "group" | "global" | "unknown"
        +label?: string
        +displayName?: string
        +channel?: string
        +subject?: string
        +updatedAt: number | null
        +modelProvider?: string
        +model?: string
        +thinkingLevel?: string
        +verboseLevel?: string
        +sendPolicy?: "allow" | "deny"
    }
    
    class SessionEntry {
        <<interface>>
        +key: string
        +origin?: string
        +lastChannel?: string
        +lastTo?: string
        +lastAccountId?: string
    }
    
    class SessionPreviewItem {
        <<interface>>
        +role: "user" | "assistant" | "tool" | "system" | "other"
        +text: string
    }
```

### 2.2 会话生命周期

```mermaid
flowchart TD
    A[会话创建] --> B{会话类型}
    B -->|主会话| C[初始化 Agent]
    B -->|独立会话| D[独立 Agent 上下文]
    
    C --> E[加载系统提示词]
    D --> E
    E --> F[加载历史消息]
    F --> G[工具调用循环]
    
    G --> H{需要工具?}
    H -->|是| I[执行工具]
    I --> J[保存结果]
    J --> G
    H -->|否| K[返回响应]
    
    K --> L[压缩上下文]
    L --> M[检查终止条件]
    M -->|继续| F
    M -->|结束| N[会话结束]
```

### 2.3 主会话 vs 独立会话

```typescript
// 会话相关类型
type SessionKey = string;
type SessionType = "main" | "subagent";

interface SessionContext {
  sessionKey: SessionKey;
  type: SessionType;
  agentId: string;
  parentSessionKey?: string;
  workspaceDir: string;
  model?: string;
  thinkingLevel?: "off" | "low" | "high";
  verboseLevel?: "off" | "low" | "high";
}

interface SubagentSpawnParams {
  agentId: string;
  sessionKey?: string;
  model?: string;
  message?: string;
  announce?: boolean;
}
```

---

## 3. Agent 系统

### 3.1 Agent 配置结构

```mermaid
classDiagram
    class AgentTool {
        <<interface>>
        +name: string
        +description: string
        +input_schema: TSchema
        +output_schema?: TSchema
    }
    
    class AgentConfig {
        <<interface>>
        +id: string
        +name?: string
        +identity?: AgentIdentity
        +model?: string
        +modelProvider?: string
        +systemPrompt?: string
        +contextTokens?: number
        +thinking?: string
    }
    
    class AgentIdentity {
        <<interface>>
        +name?: string
        +theme?: string
        +emoji?: string
        +avatar?: string
        +avatarUrl?: string
    }
```

### 3.2 工具调用链路

```mermaid
sequenceDiagram
    participant A as Agent
    participant T as ToolManager
    participant P as PolicyGuard
    participant E as Executor
    
    A->>T: 调用工具 (name, params)
    T->>P: 检查调用策略
    P->>P: 验证参数
    P-->>T: 验证结果
    
    alt 允许调用
        T->>E: 执行工具
        E-->>T: 执行结果
        T->>T: 格式化结果
        T-->>A: 返回结果
    else 拒绝调用
        T-->>A: 抛出策略错误
    end
```

### 3.3 上下文窗口管理

```typescript
// Agent 相关类型
interface ContextWindowConfig {
  maxTokens: number;
  warningThreshold: number;
  compactionThreshold: number;
}

interface CompactionResult {
  messageCount: number;
  tokenCount: number;
  compactedCount: number;
  preservedCount: number;
}

interface ToolCallRecord {
  callId: string;
  toolName: string;
  params: Record<string, unknown>;
  startTime: number;
  endTime?: number;
  result?: unknown;
  error?: string;
}
```

---

## 4. 工具系统

### 4.1 工具定义结构

```mermaid
classDiagram
    class ChannelAgentTool {
        <<type alias>>
        +AgentTool~TSchema, unknown~
    }
    
    class AnyAgentTool {
        <<type alias>>
        +AgentTool~any, unknown~
    }
    
    class ToolDefinition {
        <<interface>>
        +name: string
        +description: string
        +input_schema: Record~string, unknown~
        +output_schema?: Record~string, unknown~
        +annotations?: Record~string, unknown~
    }
    
    class ToolPolicy {
        <<interface>>
        +allow?: string[]
        +deny?: string[]
    }
```

### 4.2 工具执行流程

```mermaid
flowchart TD
    A[工具调用请求] --> B[验证参数模式]
    B --> C{参数有效?}
    C -->|否| D[返回参数错误]
    C -->|是| E[应用策略检查]
    
    E --> F{允许执行?}
    F -->|否| G[记录拒绝日志]
    G --> H[返回策略错误]
    F -->|是| I[执行工具逻辑]
    
    I --> J{执行成功?}
    J -->|否| K[捕获执行错误]
    K --> L[格式化错误响应]
    J -->|是| M[格式化结果]
    
    L --> N[记录工具调用历史]
    M --> N
    N --> O[返回结果]
```

### 4.3 工具策略配置

```typescript
// 工具系统类型
type ToolProfileId = "minimal" | "coding" | "messaging" | "full";

interface ToolProfilePolicy {
  allow?: string[];
  deny?: string[];
}

interface ToolInvocationPolicy {
  userInvocable: boolean;
  disableModelInvocation: boolean;
}

const TOOL_GROUPS: Record<string, string[]> = {
  "group:memory": ["memory_search", "memory_get"],
  "group:web": ["web_search", "web_fetch"],
  "group:fs": ["read", "write", "edit", "apply_patch"],
  "group:runtime": ["exec", "process"],
  "group:sessions": ["sessions_list", "sessions_history", "sessions_send"],
  "group:openclaw": ["browser", "canvas", "nodes", "message", "gateway"],
};
```

---

## 5. 通道系统

### 5.1 通道配置结构

```mermaid
classDiagram
    class ChannelId {
        <<type alias>>
        +string
    }
    
    class ChannelConfig {
        <<interface>>
        +enabled: boolean
        +accountId: string
        +account?: ResolvedAccount
    }
    
    class ChannelAccountSnapshot {
        <<interface>>
        +accountId: string
        +name?: string
        +enabled?: boolean
        +configured?: boolean
        +linked?: boolean
        +running?: boolean
        +connected?: boolean
        +lastError?: string | null
    }
    
    class ChannelMeta {
        <<interface>>
        +id: ChannelId
        +label: string
        +blurb: string
        +docsPath: string
    }
```

### 5.2 通道适配器架构

```mermaid
classDiagram
    class ChannelPlugin {
        <<interface>>
        +meta: ChannelMeta
        +config: ChannelConfigAdapter
        +setup?: ChannelSetupAdapter
        +outbound?: ChannelOutboundAdapter
        +directory?: ChannelDirectoryAdapter
        +status?: ChannelStatusAdapter
        +gateway?: ChannelGatewayAdapter
    }
    
    class ChannelCapabilities {
        <<interface>>
        +chatTypes: string[]
        +polls?: boolean
        +reactions?: boolean
        +edit?: boolean
        +threads?: boolean
        +media?: boolean
    }
```

### 5.3 消息路由机制

```mermaid
flowchart TD
    A[接收消息] --> B[解析通道类型]
    B --> C[确定目标会话]
    C --> D{会话存在?}
    D -->|否| E[创建新会话]
    D -->|是| F[加载会话上下文]
    
    E --> G[初始化 Agent]
    F --> G
    G --> H[处理消息]
    
    H --> I[生成响应]
    I --> J[路由到输出适配器]
    
    J --> K{使用 Gateway?}
    K -->|是| L[Gateway 发送]
    K -->|否| M[直接发送]
    
    L --> N[更新会话状态]
    M --> N
```

---

## 6. 记忆系统

### 6.1 记忆存储结构

```mermaid
classDiagram
    class MemoryManager {
        <<interface>>
        +search(query, opts): Promise~MemorySearchResult[]~
        +readFile(params): Promise~{text, path}~
        +status(): MemoryProviderStatus
        +sync(params?): Promise~void~
    }
    
    class MemorySearchResult {
        <<interface>>
        +path: string
        +startLine: number
        +endLine: number
        +score: number
        +snippet: string
        +source: MemorySource
    }
    
    class MemorySource {
        <<type alias>>
        +"memory" | "sessions"
    }
```

### 6.2 数据库 Schema

```mermaid
erDiagram
    meta {
        TEXT key PK
        TEXT value
    }
    
    files {
        TEXT path PK
        TEXT source
        TEXT hash
        INTEGER mtime
        INTEGER size
    }
    
    chunks {
        TEXT id PK
        TEXT path FK
        TEXT source
        INTEGER start_line
        INTEGER end_line
        TEXT hash
        TEXT model
        TEXT text
        TEXT embedding
        INTEGER updated_at
    }
    
    embedding_cache {
        TEXT provider PK
        TEXT model PK
        TEXT provider_key PK
        TEXT hash PK
        TEXT embedding
        INTEGER dims
        INTEGER updated_at
    }
    
    files ||--o{ chunks : contains
```

### 6.3 语义检索流程

```mermaid
sequenceDiagram
    participant U as User
    participant M as MemoryManager
    participant E as EmbeddingService
    participant V as VectorDB
    participant F as FileSystem
    
    U->>M: search(query, maxResults)
    M->>E: generateEmbedding(query)
    E-->>M: queryVector
    
    M->>V: similaritySearch(queryVector)
    V-->>M: topKResults
    
    loop For each result
        M->>F: readFile(relPath, lines)
        F-->>M: fileContent
    end
    
    M->>M: formatSnippets
    M-->>U: MemorySearchResult[]
```

---

## 7. Gateway 核心结构

### 7.1 连接管理

```mermaid
classDiagram
    class GatewayClient {
        <<interface>>
        +connect(): Promise~void~
        +send(payload): Promise~void~
        +on(event, handler): void
        +close(): Promise~void~
    }
    
    class GatewayServer {
        <<interface>>
        +start(port): Promise~void~
        +stop(): Promise~void~
        +broadcast(message): void
        +getClients(): GatewayClient[]
    }
    
    class GatewayAuth {
        <<interface>>
        +authenticate(token): Promise~boolean~
        +authorize(scope): Promise~boolean~
    }
```

### 7.2 Gateway 消息路由

```mermaid
flowchart TD
    A[Gateway 消息] --> B[验证认证令牌]
    B --> C{认证成功?}
    C -->|否| D[返回 401 错误]
    C -->|是| E[解析消息类型]
    
    E --> F{消息类型}
    F -->|agent_message| G[路由到 Agent]
    F -->|tool_call| H[路由到工具执行器]
    F -->|session_create| I[创建新会话]
    F -->|session_update| J[更新会话状态]
    F -->|memory_query| K[路由到记忆系统]
    
    G --> L[生成响应]
    H --> M[执行工具]
    M --> L
    
    L --> N[序列化响应]
    N --> O[发送回客户端]
```

### 7.3 Gateway 连接状态

```typescript
// Gateway 核心类型
interface GatewayConnection {
  id: string;
  clientName: string;
  clientDisplayName?: string;
  mode: GatewayClientMode;
  url?: string;
  token?: string;
  connectedAt: number;
  lastActivityAt: number;
  status: "connecting" | "connected" | "disconnected" | "error";
}

type GatewayClientMode = "live" | "polling" | "webhook";

interface GatewayClientConfig {
  clientName: string;
  url?: string;
  token?: string;
  timeoutMs?: number;
  mode: GatewayClientMode;
}
```

---

## 8. 核心数据结构关系图

```mermaid
erDiagram
    Agent ||--o{ Session : manages
    Session ||--o{ Message : contains
    Session ||--o{ ToolCall : has
    ToolCall ||--o{ ToolResult : produces
    
    Agent ||--o{ ToolDefinition : uses
    Agent ||--o{ MemorySearch : queries
    
    Channel ||--o{ Message : handles
    Channel ||--o{ Session : routes
    
    Gateway ||--o{ Connection : manages
    Gateway ||--o{ Session : coordinates
    
    Plugin ||--o{ ToolDefinition : registers
    Plugin ||--o{ Hook : handles
    
    MemoryManager ||--o{ MemoryIndex : maintains
    MemoryIndex ||--o{ Chunk : stores
```

---

## 9. 数据流示例

### 9.1 消息处理数据流

```mermaid
flowchart LR
    subgraph Input["输入处理"]
        A[通道接收] --> B[消息解析]
        B --> C[会话解析]
    end
    
    subgraph Agent["Agent 处理"]
        D[上下文构建]
        E[模型调用]
        F[工具规划]
    end
    
    subgraph Output["输出处理"]
        G[响应格式化]
        H[路由决策]
        I[通道发送]
    end
    
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    
    I -.->|"结果记录"| C
```

### 9.2 工具调用数据流

```mermaid
sequenceDiagram
    participant A as Agent
    participant CM as ContextManager
    participant PG as PolicyGuard
    participant TE as ToolExecutor
    participant TR as ToolResult
    
    A->>CM: 发起工具调用请求
    CM->>PG: 验证调用权限
    PG-->>CM: 权限验证结果
    
    CM->>TE: 执行工具 (name, params)
    TE->>TE: 加载工具实现
    TE->>TE: 执行工具逻辑
    
    TE-->>TR: 捕获执行结果
    TR->>TR: 格式化结果
    
    TR-->>CM: 返回工具结果
    CM-->>A: 返回最终响应
```

---

## 10. 关键类型定义

### 10.1 消息类型

```typescript
// 核心消息类型定义
import type { TSchema } from "@sinclair/typebox";
import type { AgentTool } from "@mariozechner/pi-agent-core";

// 消息角色类型
type MessageRole = "user" | "assistant" | "tool" | "system";

// 消息内容类型
type MessageContent = string | Array<ContentBlock>;

interface ContentBlock {
  type: "text" | "image" | "tool_use" | "tool_result";
  text?: string;
  media_url?: string;
  tool_use?: {
    id: string;
    name: string;
    input: Record<string, unknown>;
  };
  tool_result?: {
    id: string;
    content: string;
  };
}

// Agent 消息接口 (来自 pi-agent-core)
interface AgentMessage {
  role: MessageRole;
  content: MessageContent;
  timestamp?: number;
  // 工具相关
  tool_call_id?: string;
  tool_name?: string;
  tool_use_id?: string;
  // 思考标签
  is_antthinking?: boolean;
}

// 通道消息动作
type ChannelMessageActionName = 
  | "reaction"
  | "edit"
  | "unsend"
  | "reply"
  | "thread";

// 回复载荷
interface ReplyPayload {
  text?: string;
  blocks?: Array<Record<string, unknown>>;
  action?: ChannelMessageActionName;
  replyTo?: string;
}
```

### 10.2 会话类型

```typescript
// 会话相关类型
import type { NormalizedChatType } from "../channels/chat-type.js";
import type { SessionEntry } from "../config/sessions.js";
import type { DeliveryContext } from "../utils/delivery-context.js";

// 会话密钥类型
type SessionKey = string;

// 会话类型
type SessionKind = "direct" | "group" | "global" | "unknown";

// 会话行数据 (数据库存储)
interface GatewaySessionRow {
  key: SessionKey;
  kind: SessionKind;
  label?: string;
  displayName?: string;
  derivedTitle?: string;
  lastMessagePreview?: string;
  channel?: string;
  subject?: string;
  groupChannel?: string;
  space?: string;
  chatType?: NormalizedChatType;
  origin?: SessionEntry["origin"];
  updatedAt: number | null;
  sessionId?: string;
  systemSent?: boolean;
  abortedLastRun?: boolean;
  thinkingLevel?: string;
  verboseLevel?: string;
  reasoningLevel?: string;
  elevatedLevel?: string;
  sendPolicy?: "allow" | "deny";
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  responseUsage?: "on" | "off" | "tokens" | "full";
  modelProvider?: string;
  model?: string;
  contextTokens?: number;
  deliveryContext?: DeliveryContext;
  lastChannel?: SessionEntry["lastChannel"];
  lastTo?: string;
  lastAccountId?: string;
}

// 会话预览项
interface SessionPreviewItem {
  role: "user" | "assistant" | "tool" | "system" | "other";
  text: string;
}

// 会话预览结果
interface SessionsPreviewEntry {
  key: SessionKey;
  status: "ok" | "empty" | "missing" | "error";
  items: SessionPreviewItem[];
}

// 会话配置
interface SessionConfig {
  modelProvider: string | null;
  model: string | null;
  contextTokens: number | null;
  thinkingLevel?: string;
  verboseLevel?: string;
}
```

### 10.3 工具类型

```typescript
// 工具系统类型
import type { TSchema } from "@sinclair/typebox";
import type { AgentTool, AgentToolResult } from "@mariozechner/pi-agent-core";

// 工具配置
type ToolProfileId = "minimal" | "coding" | "messaging" | "full";

// 工具配置文件
interface ToolProfilePolicy {
  allow?: string[];
  deny?: string[];
}

// 工具策略来源
interface SandboxToolPolicySource {
  source: "agent" | "global" | "default";
  key: string;
}

// 解析后的工具策略
interface SandboxToolPolicyResolved {
  allow: string[];
  deny: string[];
  sources: {
    allow: SandboxToolPolicySource;
    deny: SandboxToolPolicySource;
  };
}

// 工具调用结果
type ToolResult<T = unknown> = 
  | { success: true; data: T }
  | { success: false; error: string };

// 工具执行上下文
interface ToolExecutionContext {
  toolName: string;
  params: Record<string, unknown>;
  sessionKey: string;
  agentId: string;
  sandboxed?: boolean;
}

// 工具调用记录
interface ToolCallRecord {
  callId: string;
  toolName: string;
  params: Record<string, unknown>;
  startTime: number;
  endTime?: number;
  result?: unknown;
  error?: string;
  durationMs?: number;
}
```

### 10.4 通道类型

```typescript
// 通道系统类型
import type { ChannelId } from "./plugins/types.core.js";

// 通道元数据
interface ChannelMeta {
  id: ChannelId;
  label: string;
  selectionLabel: string;
  docsPath: string;
  docsLabel?: string;
  blurb: string;
  order?: number;
  aliases?: string[];
  systemImage?: string;
  showConfigured?: boolean;
}

// 通道账户状态
type ChannelAccountState =
  | "linked"
  | "not linked"
  | "configured"
  | "not configured"
  | "enabled"
  | "disabled";

// 账户快照
interface ChannelAccountSnapshot {
  accountId: string;
  name?: string;
  enabled?: boolean;
  configured?: boolean;
  linked?: boolean;
  running?: boolean;
  connected?: boolean;
  reconnectAttempts?: number;
  lastConnectedAt?: number | null;
  lastDisconnect?: {
    at: number;
    status?: number;
    error?: string;
    loggedOut?: boolean;
  } | null;
  lastMessageAt?: number | null;
  lastError?: string | null;
}

// 通道能力
interface ChannelCapabilities {
  chatTypes: Array<NormalizedChatType | "thread">;
  polls?: boolean;
  reactions?: boolean;
  edit?: boolean;
  unsend?: boolean;
  reply?: boolean;
  effects?: boolean;
  groupManagement?: boolean;
  threads?: boolean;
  media?: boolean;
  nativeCommands?: boolean;
  blockStreaming?: boolean;
}

// 通道目录条目
interface ChannelDirectoryEntry {
  kind: "user" | "group" | "channel";
  id: string;
  name?: string;
  handle?: string;
  avatarUrl?: string;
  rank?: number;
  raw?: unknown;
}
```

---

## 11. 内存 vs 持久化

### 11.1 内存数据结构

```typescript
// 内存中临时数据结构

// 会话状态 (内存)
interface SessionRuntimeState {
  key: SessionKey;
  messages: AgentMessage[];
  contextTokens: number;
  lastActivityAt: number;
  isActive: boolean;
  currentModel?: string;
  toolCallHistory: ToolCallRecord[];
}

// Agent 运行时状态
interface AgentRuntimeState {
  agentId: string;
  config: AgentConfig;
  isRunning: boolean;
  currentSession?: SessionRuntimeState;
  toolPolicy: ToolProfilePolicy;
  embeddedSandbox?: SandboxContext;
}

// 通道连接状态
interface ChannelConnectionState {
  accountId: string;
  isConnected: boolean;
  lastPingAt: number;
  reconnectAttempts: number;
  pendingMessages: ReplyPayload[];
}

// 工具调用缓存
interface ToolCallCache {
  toolName: string;
  paramsHash: string;
  result: unknown;
  expiresAt: number;
}

// 上下文窗口状态
interface ContextWindowState {
  usedTokens: number;
  maxTokens: number;
  warningThreshold: number;
  compactionNeeded: boolean;
}
```

### 11.2 持久化结构

```typescript
// 持久化存储格式

// 会话文件结构 (JSON)
interface SessionFile {
  version: number;
  key: SessionKey;
  agentId: string;
  createdAt: number;
  updatedAt: number;
  metadata: {
    channel?: string;
    to?: string;
    subject?: string;
  };
  config: {
    modelProvider?: string;
    model?: string;
    thinkingLevel?: string;
  };
  messages: AgentMessage[];
}

// 认证配置文件 (JSON)
interface AuthProfileStore {
  version: number;
  profiles: Record<string, AuthProfileCredential>;
  order?: Record<string, string[]>;
  lastGood?: Record<string, string>;
  usageStats?: Record<string, ProfileUsageStats>;
}

// 配置快照 (JSON)
interface ConfigSnapshot {
  version: number;
  channels: Record<string, ChannelConfig>;
  agents: Record<string, AgentConfig>;
  plugins: Record<string, PluginConfig>;
  sandboxes?: SandboxConfig;
  memory?: MemoryProviderStatus;
}

// 记忆索引数据库 (SQLite)
interface MemoryIndexSchema {
  meta: { key: string; value: string };
  files: { path: string; source: string; hash: string; mtime: number; size: number };
  chunks: { 
    id: string; 
    path: string; 
    source: string;
    start_line: number; 
    end_line: number; 
    hash: string; 
    model: string; 
    text: string; 
    embedding: string;
    updated_at: number 
  };
  embedding_cache: {
    provider: string;
    model: string;
    provider_key: string;
    hash: string;
    embedding: string;
    dims: number;
    updated_at: number;
  };
}
```

---

## 附录：文件位置索引

| 模块 | 关键文件 | 说明 |
|------|---------|------|
| **Agent** | `src/agents/context.ts` | Agent 上下文定义 |
| **Agent** | `src/agents/sandbox/types.ts` | 沙箱配置类型 |
| **Agent** | `src/agents/skills/types.ts` | 技能类型定义 |
| **Agent** | `src/agents/auth-profiles/types.ts` | 认证配置类型 |
| **Channel** | `src/channels/plugins/types.core.ts` | 通道核心类型 |
| **Channel** | `src/channels/plugins/types.adapters.ts` | 通道适配器类型 |
| **Channel** | `src/channels/session.ts` | 会话通道类型 |
| **Gateway** | `src/gateway/session-utils.types.ts` | Gateway 会话类型 |
| **Memory** | `src/memory/types.ts` | 记忆系统类型 |
| **Memory** | `src/memory/memory-schema.ts` | 记忆数据库 Schema |
| **Plugin** | `src/plugins/types.ts` | 插件系统类型 |
| **Tool** | `src/agents/tool-policy.ts` | 工具策略类型 |

---

*文档生成时间: 2026-02-08*
*OpenClaw 版本: 基于代码分析*
