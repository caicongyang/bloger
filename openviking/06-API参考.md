# OpenViking API 参考

> 完整的 API 接口文档（与 `openviking/sync_client.py`、`openviking/async_client.py`、`openviking_cli/client/` 源码一一对应）

## 目录

1. [客户端初始化](#1-客户端初始化)
2. [资源管理](#2-资源管理)
3. [文件系统操作](#3-文件系统操作)
4. [搜索功能](#4-搜索功能)
5. [会话管理](#5-会话管理)
6. [关联管理](#6-关联管理)
7. [导入导出](#7-导入导出)
8. [数据类型](#8-数据类型)

---

## 1. 客户端初始化

### 1.1 顶层包导出

`openviking/__init__.py` 仅惰性导出以下名称：

```python
__all__ = [
    "OpenViking",        # = SyncOpenViking 别名
    "SyncOpenViking",
    "AsyncOpenViking",
    "SyncHTTPClient",
    "AsyncHTTPClient",
    "Session",
    "UserIdentifier",
]
```

> ⚠️ `TextPart` / `ContextPart` / `ToolPart` / `ContextType` / `SearchMode` **都不在顶层包**——前三个需要 `from openviking.message import ...`；`ContextType` 需要 `from openviking_cli.retrieve.types import ContextType`；`SearchMode` **完全不存在**。

### 1.2 嵌入式客户端

```python
import openviking as ov

# 同步客户端（OpenViking 即 SyncOpenViking）
client = ov.OpenViking(path="./data")
client.initialize()
# ... 使用 ...
client.close()

# 异步客户端
import asyncio
async def main():
    client = ov.AsyncOpenViking(path="./data")
    await client.initialize()
    # ... 使用 ...
    await client.close()
asyncio.run(main())
```

> `AsyncOpenViking` 是单例（`__new__` 锁），重复构造返回同一实例；`reset()` 类方法用于测试场景。

### 1.3 HTTP 客户端

```python
import openviking as ov

# 同步 HTTP 客户端
client = ov.SyncHTTPClient(
    url="http://localhost:1933",
    api_key="your-api-key",   # 服务端配置 root_api_key 时必填
)
client.initialize()

# 异步 HTTP 客户端
client = ov.AsyncHTTPClient(
    url="http://localhost:1933",
    api_key="your-api-key",
)
```

> `SyncHTTPClient`/`AsyncHTTPClient` 都支持自动从 `~/.openviking/ovcli.conf` 加载 `url`/`api_key`，参见 `openviking_cli/client/sync_http.py` 文档字符串。

---

## 2. 资源管理

### 2.1 add_resource

添加资源（仅作用于 `viking://resources/` scope）。

```python
result = client.add_resource(
    path="./docs",                      # 本地路径 / URL / GitHub 仓库
    to=None,                            # 显式指定目标 URI（不可与 parent 同时使用）
    parent=None,                        # 指定父 URI
    reason="API 文档",                   # 原因说明
    instruction="",                     # 处理指令
    wait=False,                         # 是否阻塞等待处理完成
    timeout=None,
    build_index=True,                   # 是否立即建立向量索引
    summarize=False,                    # 是否生成 L0/L1 摘要
)

# 返回 dict，含 'root_uri' 和其他元数据
print(result["root_uri"])     # "viking://resources/docs/"
print(result.get("queue_status"))  # 仅 wait=True 时返回
```

> 同时指定 `to` 与 `parent` 会抛 `ValueError`。

### 2.2 add_skill

添加 Claude Skills 协议格式的技能。

```python
result = client.add_skill(
    data={...},        # Skills 协议字典或文件路径
    wait=False,
    timeout=None,
)
```

### 2.3 wait_processed

等待全部异步语义处理完成。

```python
client.wait_processed()                # 无超时
client.wait_processed(timeout=300)     # 超时 300 秒；超时抛 DeadlineExceededError
```

---

## 3. 文件系统操作

### 3.1 ls

列出目录内容。

```python
# 真实签名：ls(uri, recursive=False, simple=False, output="original",
#               abs_limit=256, show_all_hidden=True)
result = client.ls("viking://resources/")
result_simple = client.ls("viking://resources/", simple=True)         # 仅返回路径列表
result_recursive = client.ls("viking://resources/", recursive=True)
```

### 3.2 tree

获取树形结构（**没有 `depth` 参数**）。

```python
# 真实签名：tree(uri, output="original", abs_limit=128,
#                show_all_hidden=True, node_limit=1000)
result = client.tree("viking://resources/")
result = client.tree("viking://resources/", node_limit=200)
```

### 3.3 mkdir

```python
client.mkdir("viking://resources/newproject/docs")
client.mkdir("viking://resources/newproject", description="项目根")
```

### 3.4 rm

```python
client.rm("viking://resources/temp.txt")
client.rm("viking://resources/oldproject", recursive=True)
```

### 3.5 mv

```python
client.mv("viking://resources/oldname", "viking://resources/newname")
```

### 3.6 read

```python
# 真实签名：read(uri, offset=0, limit=-1)
content = client.read("viking://resources/docs/auth.md")
chunk = client.read("viking://resources/docs/auth.md", offset=0, limit=1000)
```

### 3.7 abstract / overview

```python
abstract = client.abstract("viking://resources/docs/auth")  # 读取 .abstract.md
overview = client.overview("viking://resources/docs/auth")  # 读取 .overview.md
```

### 3.8 write

```python
# 写文本到既有文件并刷新 L0/L1/向量
result = client.write(
    uri="viking://user/memories/preferences/coding/style.md",
    content="# 编码偏好\n...",
    mode="replace",   # 目前实现 replace 模式
    wait=False,
)
```

### 3.9 glob

```python
# 真实签名：glob(pattern, uri="viking://")
result = client.glob(pattern="**/*.md", uri="viking://resources/")
print(result["matches"])
```

### 3.10 grep

```python
# 真实签名：grep(uri, pattern, case_insensitive=False,
#                node_limit=None, exclude_uri=None)
result = client.grep(
    uri="viking://resources/docs",
    pattern="OAuth",
    case_insensitive=True,
)
print(result["matches"])
```

### 3.11 stat

```python
info = client.stat("viking://resources/docs/auth.md")
```

---

## 4. 搜索功能

### 4.1 find

```python
# 真实签名：
# find(query, target_uri="", limit=10, score_threshold=None,
#      filter=None, telemetry=False, since=None, until=None, time_field=None)
results = client.find("OAuth 认证", target_uri="viking://resources/")

# 通过 filter 限定 context_type（find 没有 context_type 参数）
results = client.find(
    "认证",
    filter={"context_type": "resource"},
    limit=10,
)

# 时间范围过滤
results = client.find(
    "近期事件",
    since="2026-01-01",
    until="2026-02-01",
    time_field="created_at",
)

for r in results.resources:
    print(f"URI: {r.uri}")
    print(f"Level: {r.level} (0=L0,1=L1,2=L2)")
    print(f"Score: {r.score:.4f}")
    print(f"Abstract: {r.abstract[:80]}...")
```

### 4.2 search

```python
# 真实签名：
# search(query, target_uri="", session=None, session_id=None,
#        limit=10, score_threshold=None, filter=None, telemetry=False,
#        since=None, until=None, time_field=None)
session = client.session()
results = client.search(
    "帮我创建一个用户认证模块",
    session=session,                # 注意：参数名是 session，不是 session_info
    # 或：session_id="chat_001"
)

for r in results.resources:
    print(f"{r.uri} ({r.score:.4f})")

if results.query_plan:
    print("Reasoning:", results.query_plan.reasoning)
    for q in results.query_plan.queries:
        print("  -", q.context_type, q.priority, q.query)
```

### 4.3 关于"模式"的说明

OpenViking 的 Python 客户端 **不暴露 `SearchMode` 枚举**，`find()`/`search()` 也都**没有 `mode` 参数**。

源码中存在的是内部检索模式 `RetrieverMode`（`THINKING`/`QUICK`），位于 `openviking/retrieve/hierarchical_retriever.py`，由 `HierarchicalRetriever` 内部使用。是否启用 Rerank 取决于 `ov.conf` 中是否提供 `rerank` 配置：

```json
{
  "rerank": {
    "provider": "volcengine",
    "api_base": "https://ark.cn-beijing.volces.com/api/v3",
    "api_key": "your-api-key",
    "model": "doubao-seed-rerank"
  }
}
```

---

## 5. 会话管理

### 5.1 session

创建或加载会话。

```python
# 真实签名：session(session_id=None, must_exist=False)
session = client.session()                                   # 自动生成 ID
session = client.session(session_id="chat_001")              # 不存在则自动创建
session = client.session(session_id="chat_001", must_exist=True)  # 不存在抛 NotFoundError

# 显式管理
client.create_session("chat_001")
exists = client.session_exists("chat_001")
detail = client.get_session("chat_001")
client.delete_session("chat_001")
```

### 5.2 add_message

```python
from openviking.message import TextPart, ContextPart

session = client.session()

session.add_message(
    "user",
    [TextPart(text="如何配置 OpenViking?")],
)

session.add_message(
    "assistant",
    [
        TextPart(text="配置方法如下："),
        ContextPart(
            uri="viking://resources/config.md",
            context_type="resource",
            abstract="配置指南摘要",
        ),
    ],
)
```

> 也可通过客户端层面直接添加：`client.add_message(session_id, role, content=str, parts=list[dict], created_at=..., role_id=...)`。

### 5.3 used

记录实际使用的上下文/技能。

```python
session.used(contexts=[
    "viking://resources/docs/auth.md",
    "viking://user/memories/preferences/ui/style.md",
])

session.used(skill={
    "uri": "viking://agent/skills/code-search",
    "input": "search 'auth'",
    "output": "found 5 files",
    "success": True,
})
```

### 5.4 commit

提交会话：Phase 1 同步归档（PathLock 保护），Phase 2 后台异步提取记忆。

```python
result = session.commit()
# 实际返回（Session.commit_async 中可见）：
# {
#   "session_id": "...",
#   "status": "accepted",
#   "task_id": "...",                  # 可用 client.get_task() 跟踪 Phase 2
#   "archive_uri": "viking://session/.../history/archive_NNN/",
#   "archived": True,
#   "trace_id": "..."
# }

# 跟踪记忆提取进度
task = client.get_task(result["task_id"])
```

### 5.5 list_sessions

```python
sessions = client.list_sessions()           # ⚠️ 方法名是 list_sessions（不是 sessions）
ctx = client.get_session_context(
    "chat_001",
    token_budget=128_000,
)
archive = client.get_session_archive("chat_001", "archive_001")
```

---

## 6. 关联管理

### 6.1 link

创建关联（支持单个或多个 URI）。

```python
# 真实签名：link(from_uri, uris, reason="")
# uris 既可以是 str，也可以是 List[str]
client.link(
    from_uri="viking://resources/docs/auth",
    uris=[
        "viking://resources/docs/security",
        "viking://resources/docs/oauth",
    ],
    reason="相关安全文档",
)
```

### 6.2 unlink

删除单个关联。

```python
# 真实签名：unlink(from_uri, uri)  ⚠️ 第二个参数是单个 uri，不是列表
client.unlink(
    from_uri="viking://resources/docs/auth",
    uri="viking://resources/docs/security",
)
```

### 6.3 relations

获取关联列表。

```python
relations = client.relations("viking://resources/docs/auth")
# 真实返回：List[{"uri": "...", "reason": "..."}]
# [
#   {"uri": "viking://resources/docs/security", "reason": "相关安全文档"},
#   {"uri": "viking://resources/docs/oauth",    "reason": "OAuth 实现"},
# ]
```

---

## 7. 导入导出

### 7.1 export_ovpack

导出为 `.ovpack` 文件。

```python
# 真实签名：export_ovpack(uri, to)
exported_path = client.export_ovpack(
    uri="viking://resources/myproject",
    to="./myproject.ovpack",
)
```

### 7.2 import_ovpack

导入 `.ovpack` 文件到指定父路径。

```python
# 真实签名：import_ovpack(file_path, target, force=False, vectorize=True)
imported_root_uri = client.import_ovpack(
    file_path="./myproject.ovpack",
    target="viking://user/alice/resources/references/",
    force=False,
    vectorize=True,
)
```

---

## 8. 数据类型

### 8.1 ContextType

```python
# ⚠️ 不在 openviking 顶层包，需从 openviking_cli 导入
from openviking_cli.retrieve.types import ContextType

ContextType.MEMORY    # "memory"
ContextType.RESOURCE  # "resource"
ContextType.SKILL     # "skill"
```

### 8.2 ~~SearchMode~~ —— 不存在

OpenViking 客户端**没有 `SearchMode`**。`find()`/`search()` 不接收 `mode` 参数。
内部 `RetrieverMode`（位于 `openviking/retrieve/hierarchical_retriever.py`）只是 `HierarchicalRetriever` 的内部枚举，不是公共 API。

### 8.3 FindResult

```python
# 来自 openviking_cli/retrieve/types.py
@dataclass
class FindResult:
    memories: List[MatchedContext]
    resources: List[MatchedContext]
    skills: List[MatchedContext]
    query_plan: Optional[QueryPlan]              # 仅 search() 时填充
    query_results: Optional[List[QueryResult]]
    total: int                                    # 自动计算
```

### 8.4 MatchedContext

```python
@dataclass
class MatchedContext:
    uri: str
    context_type: ContextType
    level: int = 2                               # 0=L0 / 1=L1 / 2=L2（默认）
    abstract: str = ""
    overview: Optional[str] = None
    category: str = ""                           # 记忆细分类
    score: float = 0.0
    match_reason: str = ""
    relations: List[RelatedContext] = field(default_factory=list)
```

> ⚠️ **没有 `is_leaf` 字段**。

### 8.5 Part 类型

```python
from openviking.message import TextPart, ContextPart, ToolPart
```

详见 [会话管理详解](./05-会话管理详解.md#3-消息结构)。

---

## 相关文档

- [快速开始](./02-快速开始指南.md)
- [架构概述](./01-项目概览与架构.md)
- [部署指南](./09-部署指南.md)
