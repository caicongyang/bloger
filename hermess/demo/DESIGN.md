# Hermess Demo · 设计文档

> 最小闭环 demo:基于 LangChain + LangGraph,复刻 hermes-agent 技能系统的**从经验沉淀到自我迭代**完整链路。
>
> 对应博客文档:`../skill-framework.md`。

---

## 1. 目标

用最小可运行代码展示三件事:

1. **发现 & 加载** —— Agent 启动时扫本地技能索引,LLM 自主判断是否加载。
2. **自主沉淀(create)** —— 一次复杂任务解决后,Agent 把流程写成新的 SKILL.md。
3. **自我迭代(patch)** —— 下次使用既有 skill 时发现覆盖不足,agent 顺手 patch 自己写的 skill。

非目标:多租户、插件命名空间、安全扫描、轨迹压缩、分布式——这些都是 hermes 原型的能力,demo 不引入。

---

## 2. 技术栈

| 组件 | 选型 |
|------|------|
| LLM | DeepSeek / 通义千问(通过 `langchain-openai` 走 OpenAI 兼容接口) |
| 智能体框架 | LangGraph(`StateGraph` 外层 + `create_react_agent` 内层) |
| 结构化输出 | `ChatModel.with_structured_output(PydanticModel)` |
| 存储 | 文件系统,`skills/<category>/<name>/SKILL.md` |

---

## 3. 架构

**双层图** —— 外层元循环 + 内层 ReAct。

```
[OUTER StateGraph]
  START → plan → execute(ReAct 子图) → reflect → persist → END

[INNER create_react_agent]
  messages → ChatModel → [tool_call] → tools → ChatModel → … → submit_final
```

### 3.1 外层状态(TypedDict)

```python
class OuterState(TypedDict):
    task: str
    round_id: int

    skill_index: list[SkillIndexEntry]   # [{name, description, path}]
    plan_decision: PlanDecision          # Pydantic
    loaded_skills: list[LoadedSkill]     # [{name, frontmatter, body, path}]

    execution_messages: list[BaseMessage]
    execution_answer: str

    reflection: ReflectDecision          # Pydantic
    persist_result: dict
```

### 3.2 Pydantic 决策模型

```python
class PlanDecision(BaseModel):
    load: list[str] = Field(default_factory=list,
                            description="skill names to load (≤3)")
    rationale: str

class ReflectDecision(BaseModel):
    action: Literal["none", "create", "patch"]
    rationale: str
    # create 分支
    name: str | None = None
    category: str | None = None
    content: str | None = None           # full SKILL.md
    # patch 分支
    target_skill: str | None = None
    old_string: str | None = None
    new_string: str | None = None
```

### 3.3 节点职责

| 节点 | 输入 | 产出 | 关键动作 |
|------|------|------|---------|
| `plan` | task, skill_index | plan_decision, loaded_skills | 只读 frontmatter 组索引 → LLM.with_structured_output → skill_view 拉全文 |
| `execute` | task, loaded_skills | execution_messages, execution_answer | 构造 system_prompt(基础指令 + skill body 注入) → create_react_agent → invoke |
| `reflect` | task, loaded_skills, execution_* | reflection | 压缩 trace → LLM 判定 none/create/patch → 本地二次校验 content |
| `persist` | reflection | persist_result | SkillStore.create / patch,失败不崩图,错误写入 state |

### 3.4 内层 ReAct 工具

| 工具 | 签名 | 作用 |
|------|------|------|
| `parse_date_string` | `(text: str) -> dict` | 用 `dateutil.parser.parse` 解析,返回 `{year,month,day,hour,minute,tz_hint}`;失败返回 `{error}` |
| `format_iso` | `(year,month,day,hour=None,minute=None,tz_offset=None) -> str` | 组装 ISO 8601 输出 |
| `submit_final` | `(answer: str) -> str` | 终止信号;返回 answer 作为 tool output |

**`tz_offset` 的设计意图**:Round 1 不带时区,skill 只教 `year-month-day` + `hour-minute`;Round 3 任务包含"东八区",agent 发现必须用到 `tz_offset`,但 skill 文本里没提,reflect 触发 patch 补时区段落。

---

## 4. 目录结构

```
demo/
├── README.md
├── requirements.txt
├── .env.example                  # DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL
├── DESIGN.md                     # 本文档
├── hermess_demo/
│   ├── __init__.py
│   ├── config.py                 # 环境变量 + ChatModel 构造
│   ├── skill_store.py            # 文件系统 CRUD + frontmatter
│   ├── react_tools.py            # 内层 3 个 @tool
│   ├── prompts.py                # 三段 prompt 模板
│   ├── nodes.py                  # plan / execute / reflect / persist
│   └── graph.py                  # StateGraph 装配 + build_app()
├── skills/                       # 运行时产生,空启动
│   └── .gitkeep
└── main.py                       # 连跑 3 轮剧本的入口
```

---

## 5. 三轮剧本

**Round 1**(无 skill,从零沉淀)
- 任务:`请将 "2026年4月30日" 标准化为 ISO 8601。`
- 期望路径:plan 不加载 → execute 调 `parse_date_string` → `format_iso(year,month,day)` → `submit_final("2026-04-30")` → reflect action=create
- 沉淀产物:`skills/text-processing/date-iso-normalize/SKILL.md`,含 Steps 覆盖纯日期场景 + Verification Checklist

**Round 2**(复用,无 patch)
- 任务:`请将 "30 April 2026" 标准化为 ISO 8601。`
- 期望路径:plan 加载 `date-iso-normalize` → execute 按 skill 跑通 → reflect action=none

**Round 3**(带时区,触发 self-patch)
- 任务:`请将 "2026年4月30日 14:30 东八区" 标准化为 ISO 8601(含时间和时区)。`
- 期望路径:plan 加载 `date-iso-normalize` → execute 发现必须用 `tz_offset="+08:00"` → 输出 `2026-04-30T14:30+08:00` → reflect 检测到 skill 没讲 tz → action=patch,把 `## Steps` 段落追加时区处理

---

## 6. SkillStore 实现要点

复刻 `tools/skill_manager_tool.py` 核心约束:

| 校验 | 规则 | 来源 |
|------|------|------|
| `name` | `≤64` 字符,`^[a-z0-9][a-z0-9._-]*$` | `_validate_name` |
| `description` | `≤1024` | `MAX_DESCRIPTION_LENGTH` |
| `SKILL.md` 总长 | `≤100_000` | `MAX_SKILL_CONTENT_CHARS` |
| frontmatter | 必须以 `---` 开头,以 `\n---\n` 闭合,YAML 可解析,必含 `name`/`description` | `_validate_frontmatter` |
| 原子写 | `tempfile + os.replace` | `_atomic_write_text` |
| 冲突检测 | 创建前跨目录查重名 | `_find_skill` |
| patch | `old_string` 必须唯一命中,否则报错 | `_patch_skill` |

**不实现**(YAGNI):安全扫描、插件命名空间、外部目录、`platforms` / `requires_tools` 过滤——demo 只扫本地 `skills/` 一棵树。

---

## 7. 错误处理 & 边界

- **LLM 调用失败**:上抛,由 main.py 捕获展示,不静默吞。
- **结构化输出失败**:`with_structured_output` 已有 Pydantic 重试;仍失败则 fallback 到 `action=none`(附 rationale)。
- **create content 校验失败**:reflect 节点内本地二次校验(frontmatter/size),不合规降级为 `action=none`,持久化阶段才不会报错。
- **patch old_string 不唯一或未命中**:persist 节点返回 error,state 保留,不中断图。
- **ReAct agent 不调 `submit_final` 就结束**:execute 节点兜底——取最后一条 AI message 的 `content` 作为答案,并在日志中标注"no submit_final"。

---

## 8. 依赖

```
langgraph>=0.2.55
langchain>=0.3.13
langchain-openai>=0.2.14
langchain-core>=0.3.28
python-dateutil>=2.9
pydantic>=2.9
pyyaml>=6.0
python-dotenv>=1.0
```

OpenAI 兼容模型通过 `ChatOpenAI(base_url=...)` 接入,所以不需要 `langchain-anthropic` / `dashscope` 官方 SDK。

---

## 9. 运行方式

```bash
cd bloger/hermess/demo
pip install -r requirements.txt
cp .env.example .env   # 填入 DEEPSEEK_API_KEY
python main.py
```

**第一次跑**:Round 1 从零沉淀 skill(`skills/` 会出现新目录),Round 2/3 复用 + patch。
**第二次跑**:Round 1 直接命中 skill(沉淀已落盘),展示"下一会话才生效"的语义。

---

## 10. 与 hermes 原型的对应关系

| hermes 构件 | demo 对应 |
|------------|----------|
| `agent/skill_utils.py::parse_frontmatter` | `skill_store.py::parse_frontmatter` |
| `tools/skill_manager_tool.py::_create_skill/_patch_skill` | `skill_store.py::create/patch` |
| `tools/skills_tool.py::skill_view` | `skill_store.py::view` + `plan` 节点中的加载逻辑 |
| `agent/prompt_builder.py::SKILLS_GUIDANCE + 索引注入` | `prompts.py::PLAN_PROMPT` 中的 "err on loading" 段 |
| 系统 prompt 里 "difficult tasks → offer to save / patch" | `prompts.py::REFLECT_PROMPT` 的三分支规则 |
| ReAct 主循环 | `create_react_agent` 子图 |
| 本次会话不见新技能 | 每次 round 运行都重新 `SkillStore.list()` → 刚 create 的 skill 在同一 main.py 流程里**同一批次的 plan 节点可以看到**(demo 为演示紧凑性做了妥协,README 会说明这一差异) |
