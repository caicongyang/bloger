# memU 项目分析文档索引

> 这是一个持续更新的学习笔记系列

## 📚 文档列表

| 序号 | 文档 | 简介 |
|------|------|------|
| 01 | [整体架构与核心概念](./analysis-01-architecture.md) | 项目概述、三层记忆结构、双模式检索、数据模型 |
| 02 | [记忆流程 (Memorize) 详解](./analysis-02-memorize.md) | 7步记忆流程、多模态处理、配置选项 |
| 03 | [检索流程 (Retrieve) 详解](./analysis-03-retrieve.md) | RAG vs LLM、渐进式检索、充分性检查 |
| 04 | [数据层与存储架构](./analysis-04-database.md) | 数据库抽象、四大仓库、向量搜索、用户作用域 |
| 05 | [工作流引擎详解](./analysis-05-workflow.md) | PipelineManager、WorkflowRunner、拦截器机制 |
| 06 | [多模态与集成详解](./analysis-06-multimodal.md) | 对话/文档/图像/视频/音频处理、LLM 客户端集成 |
| 07 | [memU vs OpenClaw：架构对比与启示](./analysis-07-comparison.md) | 两者对比分析、可借鉴的设计模式 |
| 08 | [OpenClaw + memU 集成方案](./analysis-08-openclaw-integration.md) | 两种集成方案、代码示例、配置指南 |

## 🔑 核心概念速查

### 记忆三层结构
```
Resource (资源) → MemoryItem (记忆项) → MemoryCategory (类别)
```

### 两种检索模式
- **RAG**: 快速、基于向量相似度
- **LLM**: 深度、基于推理预测

### 六大记忆类型
- `profile` - 用户画像
- `event` - 事件
- `knowledge` - 知识
- `behavior` - 行为模式
- `skill` - 技能
- `tool` - 工具使用

## 🚀 快速开始

### 安装
```bash
pip install - 基本使用
```e .
```

###python
from memu import MemoryService

service = MemoryService(
    llm_profiles={"default": {"base_url": "...", "api_key": "..."}},
    database_config={"metadata_store": {"provider": "inmemory"}}
)

# 记忆
await service.memorize(
    resource_url="conversation.txt",
    modality="conversation",
    user={"user_id": "123"}
)

# 检索
result = await service.retrieve(
    queries=[{"role": "user", "content": {"text": "用户的偏好是什么？"}}]
)
```

## 📂 项目结构

```
memU/
├── src/memu/
│   ├── app/           # 核心应用逻辑
│   ├── database/      # 数据存储层
│   ├── llm/          # LLM 客户端
│   ├── embedding/    # 向量模型
│   ├── blob/         # 文件存储
│   ├── workflow/     # 工作流引擎
│   └── prompts/      # 提示词模板
├── docs/             # 本分析文档
└── tests/            # 测试用例
```

## 🔗 相关链接

- [GitHub 仓库](https://github.com/NevaMind-AI/memU)
- [在线文档](https://memu.pro/docs)
- [memU Cloud](https://app.memu.so/quick-start)
- [Discord 社区](https://discord.gg/memu)

## 📝 更新日志

- 2024-02-14: 初始版本，包含 7 篇分析文档
