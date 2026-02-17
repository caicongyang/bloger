# OpenViking API 参考

> 完整的 API 接口文档

## 目录

1. [客户端初始化](#1-客户端初始化)
2. [资源管理](#2-资源管理)
3. [文件系统操作](#3-文件系统操作)
4. [搜索功能](#4-搜索功能)
5. [会话管理](#5-会话管理)
6. [关联管理](#6-关联管理)

---

## 1. 客户端初始化

### 1.1 嵌入式客户端

```python
import openviking as ov

# 同步客户端
client = ov.SyncOpenViking(path="./data")
client.initialize()
# ... 使用 ...
client.close()

# 异步客户端
client = ov.OpenViking(path="./data")
await client.initialize()
# ... 使用 ...
await client.close()
```

### 1.2 HTTP 客户端

```python
import openviking as ov

# 同步 HTTP 客户端
client = ov.SyncHTTPClient(
    url="http://localhost:1933",
    api_key="your-api-key"
)

# 异步 HTTP 客户端
client = ov.HTTPClient(
    url="http://localhost:1933",
    api_key="your-api-key"
)
```

---

## 2. 资源管理

### 2.1 add_resource

添加资源（文件、目录、URL）。

```python
# 添加本地文件/目录
result = client.add_resource(
    path="./docs",           # 本地路径
    reason="API 文档"         # 原因说明
)

# 添加 URL
result = client.add_resource(
    path="https://example.com/docs.pdf"
)

# 添加 GitHub 仓库
result = client.add_resource(
    path="https://github.com/user/repo"
)

# 返回值
{
    "root_uri": "viking://resources/docs/",
    "file_count": 10,
    "status": "processing"
}
```

### 2.2 add_skill

添加技能定义。

```python
result = client.add_skill({
    "name": "search-code",
    "description": "代码搜索技能",
    "content": "# search-code\n...",
    "scripts": {
        "search": "python scripts/search.py"
    }
})
```

### 2.3 wait_processed

等待异步处理完成。

```python
# 等待所有资源处理完成
client.wait_processed()

# 带超时等待
client.wait_processed(timeout=300)  # 300 秒
```

---

## 3. 文件系统操作

### 3.1 ls

列出目录内容。

```python
# 基本使用
result = client.ls("viking://resources/")
print(result)

# 返回格式
{
    "entries": [
        {"name": "docs", "type": "dir"},
        {"name": "README.md", "type": "file"}
    ]
}
```

### 3.2 tree

获取树形结构。

```python
result = client.tree("viking://resources/", depth=3)
print(result)
```

### 3.3 mkdir

创建目录。

```python
client.mkdir("viking://resources/newproject/docs")
```

### 3.4 rm

删除文件或目录。

```python
# 删除文件
client.rm("viking://resources/temp.txt")

# 递归删除目录
client.rm("viking://resources/oldproject", recursive=True)
```

### 3.5 mv

移动/重命名。

```python
client.mv(
    "viking://resources/oldname",
    "viking://resources/newname"
)
```

### 3.6 read

读取文件内容。

```python
# 读取 L2 完整内容
content = client.read("viking://resources/docs/auth.md")

# 读取指定长度
content = client.read("viking://resources/docs/auth.md", limit=1000)
```

### 3.7 abstract

读取 L0 摘要。

```python
abstract = client.abstract("viking://resources/docs/auth")
# 返回: "API 认证指南，涵盖 OAuth 2.0、JWT 令牌..."
```

### 3.8 overview

读取 L1 概览。

```python
overview = client.overview("viking://resources/docs/auth")
# 返回完整的 L1 内容
```

### 3.9 glob

模式匹配查找文件。

```python
# 查找所有 md 文件
result = client.glob(
    pattern="**/*.md",
    uri="viking://resources/"
)

# 查找特定模式
result = client.glob(
    pattern="**/api*.md",
    uri="viking://resources/docs"
)

print(result["matches"])
# ["viking://resources/docs/api/auth.md", ...]
```

### 3.10 grep

文本搜索。

```python
result = client.grep(
    pattern="OAuth",
    uri="viking://resources/docs"
)

print(result["matches"])
# [
#   {"uri": "...", "line": 10, "content": "..."},
#   ...
# ]
```

---

## 4. 搜索功能

### 4.1 find

简单语义搜索。

```python
# 基本搜索
results = client.find(
    "OAuth 认证",
    target_uri="viking://resources/"
)

# 搜索指定类型
results = client.find(
    "认证方法",
    target_uri="viking://resources/",
    context_type="resource"  # resource/memory/skill
)

# 限制返回数量
results = client.find(
    "查询",
    target_uri="viking://resources/",
    limit=10
)

# 遍历结果
for r in results.resources:
    print(f"URI: {r.uri}")
    print(f"Score: {r.score:.4f}")
    print(f"Abstract: {r.abstract}")
```

### 4.2 search

复杂搜索（需要会话）。

```python
# 创建会话
session = client.session()

# 复杂搜索
results = client.search(
    "帮我创建一个用户认证模块",
    session_info=session,
    mode=ov.SearchMode.THINKING  # 启用 Rerank
)

# 获取结果
for r in results.resources:
    print(f"{r.uri} ({r.score:.4f})")

# 获取查询计划
if results.query_plan:
    print(results.query_plan)
```

### 4.3 SearchMode

```python
import openviking as ov

# 默认模式
ov.SearchMode.DEFAULT

# 思考模式 - 启用 Rerank
ov.SearchMode.THINKING

# 快速模式 - 禁用 Rerank
ov.SearchMode.FAST
```

---

## 5. 会话管理

### 5.1 session

创建会话。

```python
# 创建新会话
session = client.session()

# 恢复已有会话
session = client.session(session_id="chat_001")
```

### 5.2 add_message

添加消息。

```python
session = client.session()

# 添加用户消息
session.add_message(
    "user",
    [ov.TextPart("如何配置 OpenViking?")]
)

# 添加助手消息
session.add_message(
    "assistant",
    [
        ov.TextPart("配置方法如下："),
        ov.ContextPart(
            uri="viking://resources/config.md",
            abstract="配置指南摘要"
        )
    ]
)
```

### 5.3 used

记录使用的上下文。

```python
# 记录使用的资源
session.used(contexts=[
    "viking://resources/docs/auth.md",
    "viking://user/memories/preferences/ui.md"
])

# 记录使用的技能
session.used(skill={
    "uri": "viking://agent/skills/code-search",
    "input": "search 'auth'",
    "output": "found 5 files",
    "success": True
})
```

### 5.4 commit

提交会话。

```python
result = session.commit()

# 返回值
{
    "status": "committed",
    "memories_extracted": 5,
    "active_count_updated": 2,
    "archived": True,
    "extracted_memories": [
        {
            "type": "preferences",
            "action": "UPDATE",
            "uri": "viking://user/memories/preferences/..."
        }
    ]
}
```

### 5.5 sessions

列出所有会话。

```python
# 列出所有会话
sessions = client.sessions()

# 过滤条件
sessions = client.sessions(limit=10, offset=0)
```

---

## 6. 关联管理

### 6.1 link

创建资源关联。

```python
client.link(
    from_uri="viking://resources/docs/auth",
    uris=[
        "viking://resources/docs/security",
        "viking://resources/docs/oauth"
    ],
    reason="相关安全文档"
)
```

### 6.2 unlink

删除资源关联。

```python
client.unlink(
    from_uri="viking://resources/docs/auth",
    uris=["viking://resources/docs/security"]
)
```

### 6.3 relations

获取关联列表。

```python
relations = client.relations("viking://resources/docs/auth")

print(relations)
# {
#   "viking://resources/docs/security": "相关安全文档",
#   "viking://resources/docs/oauth": "OAuth 实现"
# }
```

---

## 7. 导入导出

### 7.1 export_ovpack

导出为 OVPack 格式。

```python
result = client.export_ovpack(
    uri="viking://resources/myproject",
    output_path="./myproject.ovpack"
)
```

### 7.2 import_ovpack

导入 OVPack 文件。

```python
result = client.import_ovpack(
    input_path="./myproject.ovpack"
)
```

---

## 8. 数据类型

### 8.1 ContextType

```python
from openviking import ContextType

ContextType.RESOURCE  # 资源
ContextType.MEMORY   # 记忆
ContextType.SKILL    # 技能
```

### 8.2 SearchMode

```python
from openviking import SearchMode

SearchMode.DEFAULT   # 默认
SearchMode.THINKING  # 思考模式（Rerank）
SearchMode.FAST      # 快速模式
```

### 8.3 FindResult

```python
@dataclass
class FindResult:
    memories: List[MatchedContext]
    resources: List[MatchedContext]
    skills: List[MatchedContext]
    query_plan: Optional[QueryPlan]
    query_results: Optional[List[QueryResult]]
    total: int
```

### 8.4 MatchedContext

```python
@dataclass
class MatchedContext:
    uri: str
    context_type: ContextType
    is_leaf: bool
    abstract: str
    score: float
    relations: List[RelatedContext]
```

---

## 相关文档

- [快速开始](./02-快速开始指南.md)
- [架构概述](./01-项目概览与架构.md)
- [部署指南](./09-部署指南.md)
