# memU 项目分析文档索引

> 持续更新的源码学习笔记系列。每篇都是基于 `memU/src/memu` 当前实现的逐行精读。

## 文档列表

| 序号 | 文档 | 简介 |
|------|------|------|
| 01 | [整体架构与核心概念](./analysis-01-architecture.md) | 项目概述、三层记忆结构、双模式检索、数据模型 |
| 02 | [记忆流程 (Memorize) 详解](./analysis-02-memorize.md) | 7 步记忆流水线、多模态处理、prompt 块化组合 |
| 03 | [检索流程 (Retrieve) 详解](./analysis-03-retrieve.md) | RAG vs LLM、pre-retrieval decision、渐进式 + 充分性检查 |
| 04 | [数据层与存储架构](./analysis-04-database.md) | 数据库抽象、四大仓库、向量搜索、强化与 user scope |
| 05 | [工作流引擎详解](./analysis-05-workflow.md) | PipelineManager、WorkflowRunner、LLM/Workflow 双拦截器栈 |
| 06 | [多模态与集成详解](./analysis-06-multimodal.md) | 对话/文档/图像/视频/音频处理、LLM 客户端集成 |
| 07 | [memU vs OpenClaw：架构对比与启示](./analysis-07-comparison.md) | 两者对比分析、可借鉴的设计模式 |
| 08 | [OpenClaw + memU 集成方案](./analysis-08-openclaw-integration.md) | 两种集成方案、代码示例、配置指南 |
| 09 | [记忆强化与 Salience 评分](./analysis-09-salience-and-reinforcement.md) | 内容哈希去重、reinforcement、salience-aware ranking |
| 10 | [CRUD 与类别摘要传播](./analysis-10-patch-and-propagation.md) | PatchMixin、category_patch prompt、传播机制 |

## 核心概念速查

### 记忆三层结构
```
Resource (原始资源) → MemoryItem (记忆项) → MemoryCategory (类别)
```

### 两种检索模式
- **RAG**：快速、基于向量相似度（可选 salience-aware 加权）
- **LLM**：深度、由 LLM 在三层之间逐级筛选与排序

### 记忆类型（六种可选，默认仅启用前两种）
- `profile` ✅ 默认 — 用户长期画像（基础信息、偏好、习惯）
- `event` ✅ 默认 — 具体事件
- `knowledge` — 用户掌握的知识/事实
- `behavior` — 行为模式
- `skill` — 技能
- `tool` — 工具使用记忆（带 `when_to_use / metadata / tool_calls`）

> 默认值定义在 `src/memu/prompts/memory_type/__init__.py`：
> ```python
> DEFAULT_MEMORY_TYPES: list[str] = ["profile", "event"]
> ```
> 其他类型需要在 `MemorizeConfig.memory_types` 显式开启。

## 快速开始

### 安装

```bash
pip install -e .
```

### 基本使用

```python
from memu import MemoryService

service = MemoryService(
    llm_profiles={"default": {"base_url": "...", "api_key": "..."}},
    database_config={"metadata_store": {"provider": "inmemory"}},
)

# 记忆
await service.memorize(
    resource_url="conversation.txt",
    modality="conversation",
    user={"user_id": "123"},
)

# 检索（最后一条 query 是当前问题，前面的是上下文）
result = await service.retrieve(
    queries=[
        {"role": "user", "content": {"text": "Tell me about preferences"}},
        {"role": "assistant", "content": {"text": "Sure"}},
        {"role": "user", "content": {"text": "What are they"}},
    ],
    where={"user_id": "123"},
)
```

## 项目结构

```
memU/
├── src/memu/
│   ├── app/             # 核心服务、memorize/retrieve/crud/patch mixin
│   ├── database/        # 数据存储层（inmemory / postgres / sqlite）
│   ├── llm/             # LLM 客户端包装与拦截器
│   ├── client/          # 各家厂商客户端（openai/lazyllm/openrouter/...）
│   ├── embedding/       # 向量模型
│   ├── blob/            # 文件存储
│   ├── workflow/        # 工作流引擎（PipelineManager / Runner / Interceptor）
│   ├── prompts/         # 块化提示词模板
│   ├── integrations/    # LangGraph 等外部框架适配
│   └── utils/
├── docs/                # 官方文档
└── tests/               # 各后端 / 各场景测试
```

## 相关链接

- [GitHub 仓库](https://github.com/NevaMind-AI/memU)
- [在线文档](https://memu.pro/docs)
- [memU Cloud](https://app.memu.so/quick-start)
- [Discord 社区](https://discord.gg/memu)

## 更新日志

- 2024-02-14：初始版本，包含 7 篇分析文档。
- 2026-04-27：基于最新源码全面修订
  - 修复 README 安装段落格式问题；
  - 更新 02/03/04/05 中与当前实现不一致的描述（dedupe 已实现、默认仅 2 种 memory type、新增 pre-retrieval decision 等）；
  - 新增第 09 篇：记忆强化与 Salience 评分；
  - 新增第 10 篇：CRUD 与类别摘要传播。
