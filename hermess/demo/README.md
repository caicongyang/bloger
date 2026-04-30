# Hermess Demo · Minimal Skill Iteration Loop

用 **LangChain + LangGraph** 实现的最小闭环 demo,复刻 hermes-agent 的**技能沉淀与自我迭代**能力。

配套博客见 [`../skill-framework.md`](../skill-framework.md),设计文档见 [`DESIGN.md`](DESIGN.md)。

---

## 它展示了什么

三轮任务连跑,完整呈现一个技能的生命周期:

| Round | 任务 | 预期行为 |
|-------|------|---------|
| 1 | `"2026年4月30日"` → ISO 8601 | 技能库空 → Agent 探索解决 → **create** 新技能 `date-iso-normalize` |
| 2 | `"30 April 2026"` → ISO 8601 | 自动加载上一轮沉淀的技能 → 顺利执行 → **noop** |
| 3 | `"2026年4月30日 14:30 东八区"` → 带时区 ISO 8601 | 加载技能 → 发现技能没讲时区 → **patch** 补上时区规则 |

---

## 架构一眼

**双层 LangGraph**:

```
外层 StateGraph:  plan → execute → reflect → persist
                           ↑
                   内层 ReAct:
                   ChatModel ⇄ [parse_date_string, format_iso, submit_final]
```

- `plan`:读 `skills/` 里所有 SKILL.md 的 frontmatter,LLM 判断加载哪些。
- `execute`:基于 `langgraph.prebuilt.create_react_agent` 的 ReAct 子图;加载的 skill 原文注入 system prompt。
- `reflect`:LLM 用 `with_structured_output` 产出 `{action: none|create|patch, ...}` 决策。
- `persist`:文件系统 CRUD(frontmatter 校验 + 原子写 + 冲突检测 + patch 唯一命中)。

---

## 运行

### 1. 安装

```bash
cd bloger/hermess/demo
python -m venv .venv && source .venv/bin/activate   # 可选
pip install -r requirements.txt
```

### 2. 配置 API key

```bash
cp .env.example .env
# 编辑 .env,填入 DEEPSEEK_API_KEY(或切到通义千问、智谱 GLM,见 .env.example 注释)
```

默认使用 [DeepSeek](https://platform.deepseek.com/) 的 `deepseek-chat`。模型必须支持 **OpenAI function calling**,否则 ReAct 不工作。

### 3. 一键跑

```bash
python main.py
```

跑完会在 `skills/text-processing/date-iso-normalize/SKILL.md` 看到第一轮沉淀的产物,第三轮跑完后文件会被 patch。

### 4. 验证"下次生效"

第一次跑完后,把 `skills/` 清空再跑第二次——会看到 Round 1 同样从零开始。**这正是 hermes 设计的本意:技能是文件,跨会话持久。**

反之,如果不清空 `skills/` 直接再跑,Round 1 会命中上一次沉淀的技能,Round 2/3 行为保持一致。

---

## 目录结构

```
demo/
├── README.md                  ← 你在这里
├── DESIGN.md                  ← 设计文档(架构、状态 schema、节点约束)
├── requirements.txt
├── .env.example
├── main.py                    ← 3 轮剧本入口
├── hermess_demo/
│   ├── config.py              ← ChatOpenAI 构造(支持任意 OpenAI 兼容端点)
│   ├── skill_store.py         ← 文件系统 CRUD + frontmatter + 原子写
│   ├── react_tools.py         ← 内层 3 个 @tool
│   ├── prompts.py             ← 三段 prompt 模板 + trace 压缩
│   ├── nodes.py               ← plan / execute / reflect / persist
│   └── graph.py               ← StateGraph 装配
└── skills/                    ← 运行时产生,空仓起步
```

---

## 与 hermes 原型的映射

| hermes 原件 | demo 对应 |
|------------|----------|
| `agent/skill_utils.py::parse_frontmatter` | `skill_store.py::parse_frontmatter` |
| `tools/skill_manager_tool.py::_create_skill/_patch_skill` | `skill_store.py::create/patch` |
| `tools/skills_tool.py::skill_view` | `skill_store.py::view` + `plan_node` 加载 |
| 系统 prompt 里的 `SKILLS_GUIDANCE` + `<available_skills>` 块 | `prompts.py::PLAN_PROMPT` + `render_skill_index_block` |
| "困难任务 → offer to save / patch" | `prompts.py::REFLECT_PROMPT` 的三分支决策规则 |
| ReAct 主循环 | `create_react_agent` 子图 |
| "本次会话不见新技能" | demo 为演示紧凑,**同一进程的后续轮次可以看到**;跨进程语义与 hermes 一致 |

---

## 调试小贴士

- **结构化输出失败**:`nodes.py` 的 `plan_node` / `reflect_node` 都对 `with_structured_output` 异常做了兜底(降级为空加载 / none 动作),不会崩图;但你可以打开 `LANGCHAIN_TRACING_V2=true` 看具体错误。
- **ReAct 不调 `submit_final`**:`execute_node` 有兜底——取最后一条 AI 消息的 content 作为答案。
- **想看内层轨迹**:`main.py` 打印了 `tool_calls` 数量,要更详细的逐步可以把 `final_state["execution_messages"]` 直接 print。
- **patch 没触发**:多半是 Round 3 的 ReAct 根本没用 `tz_offset`(LLM 偷懒直接输出字符串)。调高执行节点的温度、或在 `prompts.py::EXECUTE_SYSTEM_BASE` 里加强"必须用工具"的语气。

---

## YAGNI 声明

这是一个**展示性 demo**,刻意不实现:

- 安全扫描(`_security_scan_skill`)
- 插件命名空间 / 外部目录
- `platforms` / `requires_tools` 条件过滤
- LRU 缓存 + `.manifest.json` 磁盘快照
- 轨迹压缩(`trajectory_compressor.py`)

上述所有能力都在博客 [`../skill-framework.md`](../skill-framework.md) 里有对应 hermes 源码位置,可按需回填到本 demo。
