# memU 项目深度分析 (六)：多模态与集成详解

> 基于源码分析的学习笔记

## 1. 多模态支持概述

memU 支持多种模态的记忆处理：

```mermaid
flowchart TB
    subgraph "输入模态"
        C[conversation]
        D[document]
        I[image]
        V[video]
        A[audio]
    end
    
    subgraph "处理"
        P1[对话处理]
        P2[文档处理]
        P3[图像处理]
        P4[视频处理]
        P5[音频处理]
    end
    
    subgraph "输出"
        O[统一记忆结构]
    end
    
    C --> P1
    D --> P2
    I --> P3
    V --> P4
    A --> P5
    
    P1 --> O
    P2 --> O
    P3 --> O
    P4 --> O
    P5 --> O
```

## 2. 模态处理器

### 2.1 对话 (conversation)

```python
async def _preprocess_conversation(
    self,
    text: str,
    template: str,
    llm_client,
) -> list[dict[str, str | None]]:
    """
    处理对话数据
    1. 格式化对话（添加索引）
    2. LLM 分段
    3. 为每段生成摘要
    """
    
    # 1. 格式化
    preprocessed_text = format_conversation_for_preprocess(text)
    
    # 2. 分段
    prompt = template.format(conversation=...)
    processed = await client.chat(prompt)
    _, segments = self._parse_conversation_preprocess_with_segments(processed)
    
    # 3. 每段生成摘要
    resources = []
    for segment in segments:
        segment_text = extract_segment(...)
        caption = await self._summarize_segment(segment_text)
        resources.append({"text": segment_text, "caption": caption})
    
    return resources
```

**对话格式示例**（实际由 `format_conversation_for_preprocess` 产出，预期输入是 JSON 而非纯文本）：

```7:36:memU/src/memu/utils/conversation.py
def format_conversation_for_preprocess(raw_text: str) -> str:
    """
    Normalize a conversation into a line-based format suitable for LLM preprocessing prompts.

    Supported input formats:
    - A JSON list of messages: [{"role": "...", "content": "...", "created_at": "..."}]
    - A JSON dict with a "content" list: {"content": [ ...messages... ]}

    Output format:
    - One message per line
    - Each line starts with an index marker: "[{idx}]"
    - If a created_at is available, it is included after the index
    - The role is included in square brackets: "[user]" / "[assistant]" etc.
    """
```

```
输入 (JSON):
[
  {"role": "user",      "content": "你好",            "created_at": "2026-04-27T08:00"},
  {"role": "assistant", "content": "你好！有什么可以帮你？"}
]

经 format_conversation_for_preprocess 处理后:
[0] 2026-04-27T08:00 [user]: 你好
[1] [assistant]: 你好！有什么可以帮你？
```

> 注意：源码注释里特别强调 *"always use the original JSON-derived, indexed conversation text for downstream segmentation"*——LLM 的 segment 输出只是返回 `start/end` 行号区间，**真正的切片是基于这份 indexed 文本进行的**。这是 memU 防止 LLM 改写对话内容（丢字段、改时间）导致下游解析出问题的关键设计。

### 2.2 文档 (document)

```python
async def _preprocess_document(
    self,
    text: str,
    template: str,
    llm_client,
) -> list[dict[str, str | None]]:
    """
    处理文档数据
    1. 提取关键信息
    2. 生成摘要
    """
    
    prompt = template.format(document_text=text)
    processed = await client.chat(prompt)
    
    # 解析处理后的内容和标题
    processed_content, caption = self._parse_multimodal_response(
        processed,
        "processed_content",
        "caption"
    )
    
    return [{"text": processed_content or text, "caption": caption}]
```

### 2.3 图像 (image)

```python
async def _preprocess_image(
    self,
    local_path: str,
    template: str,
    llm_client,
) -> list[dict[str, str | None]]:
    """
    处理图像数据
    使用 Vision API 提取描述
    """
    
    # 调用视觉模型
    processed = await client.vision(
        prompt=template,
        image_path=local_path,
    )
    
    # 解析详细描述和标题
    description, caption = self._parse_multimodal_response(
        processed,
        "detailed_description",
        "caption"
    )
    
    return [{"text": description, "caption": caption}]
```

**支持的图像格式**：
- PNG, JPG, JPEG, GIF, WebP, BMP

### 2.4 视频 (video)

```python
async def _preprocess_video(
    self,
    local_path: str,
    template: str,
    llm_client,
) -> list[dict[str, str | None]]:
    """
    处理视频数据
    1. 提取中间帧
    2. Vision API 分析
    3. 清理临时文件
    """
    
    # 检查 ffmpeg
    if not VideoFrameExtractor.is_ffmpeg_available():
        return [{"text": None, "caption": None}]
    
    # 提取中间帧
    frame_path = VideoFrameExtractor.extract_middle_frame(local_path)
    
    try:
        # 视觉分析
        processed = await client.vision(
            prompt=template,
            image_path=frame_path,
        )
        description, caption = self._parse_multimodal_response(...)
    finally:
        # 清理
        pathlib.Path(frame_path).unlink()
    
    return [{"text": description, "caption": caption}]
```

### 2.5 音频 (audio)

```python
async def _preprocess_audio(
    self,
    text: str,
    template: str,
    llm_client,
) -> list[dict[str, str | None]]:
    """
    处理音频数据
    1. 转录（如需要）
    2. 提取关键信息
    """
    
    prompt = template.format(transcription=text)
    processed = await client.chat(prompt)
    
    processed_content, caption = self._parse_multimodal_response(
        processed,
        "processed_content",
        "caption"
    )
    
    return [{"text": processed_content or text, "caption": caption}]
```

**支持的音频格式**：
- MP3, WAV, M4A, MP4, WebM

## 3. LLM 客户端

### 3.1 客户端类型

memU 在 `src/memu/llm/` 下提供了三种 LLM client backend，由 `LLMConfig.client_backend` 切换：

```mermaid
graph TB
    IF[LLMClient Interface<br/>chat / vision / embed / transcribe]

    subgraph backends["src/memu/llm/"]
        OAI[OpenAISDKClient<br/>client_backend = sdk]
        HTTP[HTTPLLMClient<br/>client_backend = httpx]
        LZ[LazyLLMClient<br/>client_backend = lazyllm_backend]
    end

    IF --> OAI
    IF --> HTTP
    IF --> LZ
```

| backend | 适合场景 | 实现文件 |
|---------|----------|----------|
| `sdk` （默认） | OpenAI 官方 SDK，类型安全；走 `AsyncOpenAI` | `llm/openai_sdk.py` |
| `httpx` | 自实现 HTTP 客户端，按 provider 拆分 backend，更易扩展 | `llm/http_client.py` |
| `lazyllm_backend` | 通过 [LazyLLM](https://github.com/LazyAGI/LazyLLM) 接入国内厂商（Qwen、Doubao、SiliconFlow 等） | `llm/lazyllm_client.py` |

### 3.2 OpenAI SDK 客户端

```python
class OpenAISDKClient:
    """OpenAI SDK 客户端"""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str,
        embed_model: str,
        embed_batch_size: int = 100,
    ):
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.chat_model = chat_model
        self.embed_model = embed_model
    
    async def chat(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs
    ) -> str:
        """聊天完成"""
    
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """文本嵌入"""
    
    async def vision(
        self,
        prompt: str,
        image_path: str,
        system_prompt: str | None = None,
    ) -> str:
        """视觉理解"""
    
    async def transcribe(self, audio_path: str) -> str:
        """音频转录"""
```

### 3.3 HTTP 客户端

```python
class HTTPLLMClient:
    """通用 HTTP LLM 客户端"""
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str,
        provider: str | None = None,
        endpoint_overrides: dict | None = None,
        embed_model: str | None = None,
    ):
        ...
```

**`httpx` backend 实际支持的 provider**（取决于 `LLMConfig.provider`）：

```1:7:memU/src/memu/llm/backends/__init__.py
from memu.llm.backends.base import LLMBackend
from memu.llm.backends.doubao import DoubaoLLMBackend
from memu.llm.backends.grok import GrokBackend
from memu.llm.backends.openai import OpenAILLMBackend
from memu.llm.backends.openrouter import OpenRouterLLMBackend
```

| provider | 用法要点 |
|----------|---------|
| `openai` | OpenAI 兼容 API（含 vLLM、Ollama、OpenAI Compatible 模型） |
| `doubao` | 字节跳动豆包，自定义 endpoint `/api/v3/...` |
| `grok` | xAI Grok，自动把 `base_url` 切到 `https://api.x.ai/v1` |
| `openrouter` | OpenRouter 聚合网关，可一键切换 Anthropic / Gemini / Mistral 等 |

> **备注**：Anthropic、Gemini、Bedrock 等"非 OpenAI 兼容"的 provider，目前**没有内置 backend**，需要走 `openrouter` 中转或扩展自定义 `LLMBackend`。如果直接配 `provider="anthropic"`，会因匹配不到 backend 而抛错。

### 3.4 多 Profile 配置

```python
from memu import MemoryService

service = MemoryService(
    llm_profiles={
        # 默认 Profile
        "default": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-...",
            "chat_model": "gpt-4o",
            "client_backend": "sdk"
        },
        # Embedding 专用
        "embedding": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-...",
            "embed_model": "text-embedding-3-small",
            "client_backend": "sdk"
        },
        # 快速模型（用于简单任务）
        "fast": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-...",
            "chat_model": "gpt-4o-mini",
            "client_backend": "httpx"
        }
    }
)
```

## 4. 向量模型

### 4.1 内置 Embedding backend

embedding 走的是独立模块 `src/memu/embedding/`，目前只有两套实现：

```
memU/src/memu/embedding/backends/
├── openai.py    # provider=openai
└── doubao.py    # provider=doubao
```

也就是说，凡是声明自己 *OpenAI 兼容* 的 embedding 服务（Voyage、Cohere、SiliconFlow、本地 vLLM、Ollama 等）都可以挂在 `provider="openai"` 上，把 `base_url` 改到对应 endpoint 就行；真正非 OpenAI 兼容的字节豆包则走 `provider="doubao"`。

### 4.2 Embedding 配置示例

```python
llm_profiles={
    # 默认：OpenAI text-embedding-3-small
    "embedding": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-...",
        "embed_model": "text-embedding-3-small",
    },
    # 替换：用 SiliconFlow 的 BGE（OpenAI 兼容）
    # "embedding": {
    #     "provider": "openai",
    #     "base_url": "https://api.siliconflow.cn/v1",
    #     "api_key": "sk-sf-...",
    #     "embed_model": "BAAI/bge-m3",
    # },
}
```

> 关于 LazyLLM：如果选 `client_backend="lazyllm_backend"`，可以通过 `lazyllm_source.embed_source` 接入更多国内 embedding 厂商，但前提是 `lazyllm` 已安装并在该厂商上跑通。

## 5. Blob 存储

### 5.1 本地文件系统

```10:80:memU/src/memu/blob/local_fs.py
class LocalFS:
    def __init__(self, base_dir: str):
        self.base = pathlib.Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    async def fetch(self, url: str, modality: str) -> tuple[str, str | None]:
        # Local path
        p = pathlib.Path(url)
        if p.exists():
            dst = self.base / p.name
            if str(p.resolve()) != str(dst.resolve()):
                shutil.copyfile(p, dst)
            text = None
            if modality in ("conversation", "text", "document"):
                text = dst.read_text(encoding="utf-8")
            return str(dst), text

        # HTTP - get clean filename
        filename = self._get_filename_from_url(url, modality)
        dst = self.base / filename

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(url)
            r.raise_for_status()
            dst.write_bytes(r.content)
        text = None
        if modality in ("conversation", "text", "document"):
            text = r.text
        return str(dst), text
```

要点：

- 只有 `conversation / text / document` 三种 modality 会读出 `text`，图像/视频/音频不读文本，下游通过 `local_path` 让 Vision/STT 客户端自取；
- 远程 URL 会自动下载到 `base_dir`，并对 query string、`grab.php` 之类的"假后缀"做了清洗（见 `_get_filename_from_url`）；
- 这是为下游记忆抽取留持久化痕迹的关键——一旦记忆链条出问题，可以根据 `Resource.local_path` 回溯到原始资源。

### 5.2 资源目录结构

```
resources/
├── conversations/
│   ├── 2024/
│   │   └── 01/
│   │       └── conv_001.txt
├── documents/
│   └── notes.md
├── images/
│   └── photos/
└── videos/
```

## 6. 集成示例

### 6.1 Slack 集成

```python
# 监听 Slack 消息并记忆
from slack_sdk import WebClient
from memu import MemoryService

service = MemoryService(...)

client = WebClient(token="xoxb-...")

@app.event("message")
async def handle_message(event):
    # 记忆消息
    await service.memorize(
        resource_url=event["text"],
        modality="conversation",
        user={"user_id": event["user"]}
    )
```

### 6.2 Discord 集成

```python
# Discord Bot 记忆
import discord
from memu import MemoryService

intents = discord.Intents.default()
client = discord.Client(intents=intents)

@client.event
async def on_message(message):
    # 记忆消息
    await service.memorize(
        resource_url=message.content,
        modality="conversation",
        user={"user_id": str(message.author.id)}
    )
```

### 6.3 Email 集成

```python
# Gmail 集成
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from memu import MemoryService

# 获取邮件
service_gmail = build('gmail', 'v1', credentials=credentials)
messages = service_gmail.users().messages().list(userId='me').execute()

# 记忆每封邮件
for msg in messages['messages']:
    email = service_gmail.users().messages().get(
        userId='me', id=msg['id'], format='full'
    ).execute()
    
    await memory_service.memorize(
        resource_url=email['snippet'],
        modality="conversation",
        user={"user_id": "me"}
    )
```

### 6.4 自定义 LLM

```python
# 使用 Ollama 本地模型
service = MemoryService(
    llm_profiles={
        "default": {
            "base_url": "http://localhost:11434/v1",
            "api_key": "ollama",
            "chat_model": "llama3",
            "client_backend": "httpx",
            "provider": "ollama"
        }
    }
)

# 或使用 OpenRouter
service = MemoryService(
    llm_profiles={
        "default": {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai",
            "api_key": "openrouter-...",
            "chat_model": "anthropic/claude-3.5-sonnet",
            "client_backend": "httpx"
        }
    }
)
```

## 7. Prompt 定制

### 7.1 预处理 Prompt

```python
from memu.app.settings import MemorizeConfig

config = MemorizeConfig(
    multimodal_preprocess_prompts={
        "conversation": """你是一个对话分析助手。
请将以下对话分段，并标注每段的主题。

<conversation>
{conversation}
</conversation>

请返回 JSON 格式：
{
    "segments": [
        {"start": 0, "end": 5, "caption": "开场白"},
        {"start": 6, "end": 15, "caption": "讨论项目"}
    ]
}""",
        
        "image": """描述这张图片的详细内容。"""
    }
)
```

### 7.2 记忆提取 Prompt

```python
config = MemorizeConfig(
    memory_type_prompts={
        "profile": """从以下内容中提取用户画像信息：
- 偏好
- 习惯
- 特点

{resource}

请返回 XML 格式：
<entries>
    <entry>
        <content>提取的记忆</content>
        <categories>相关类别</categories>
    </entry>
</entries>""",
        
        "skill": """从以下内容中提取技能信息：
{resource}"""
    }
)
```

### 7.3 类别摘要 Prompt

```python
config = MemorizeConfig(
    default_category_summary_prompt="""你是类别摘要助手。
类别: {category}
现有摘要:
{original_content}

新增记忆:
{new_memory_items_text}

请更新摘要，保持在 {target_length} 字以内。"""
)
```

## 8. 配置大全

### 8.1 完整配置示例

```python
from memu import MemoryService

service = MemoryService(
    # LLM 配置
    llm_profiles={
        "default": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-...",
            "chat_model": "gpt-4o",
            "embed_model": "text-embedding-3-small",
            "client_backend": "sdk",
            "provider": "openai"
        }
    },
    
    # 数据库配置（合法 vector provider 是 bruteforce / pgvector / none）
    database_config={
        "metadata_store": {"provider": "inmemory"},
        "vector_index": {"provider": "bruteforce"}
    },

    # Blob 存储（local 是默认 provider，目录默认 ./data/resources）
    blob_config={
        "provider": "local",
        "resources_dir": "./resources"
    },
    
    # 记忆配置（默认只启用 profile + event；下面这份是显式打开全部 6 类）
    memorize_config={
        "memory_types": ["profile", "event", "knowledge", "behavior", "skill", "tool"],
        "enable_item_reinforcement": True,
        "enable_item_references": True,
        "preprocess_llm_profile": "default",
        "memory_extract_llm_profile": "default",
        "category_update_llm_profile": "default"
    },
    
    # 检索配置（这些就是源码默认值，列出来便于对照）
    retrieve_config={
        "method": "rag",
        "route_intention": True,
        "sufficiency_check": True,
        "category": {"enabled": True, "top_k": 5},
        "item": {"enabled": True, "top_k": 5, "ranking": "salience", "recency_decay_days": 30.0},
        "resource": {"enabled": True, "top_k": 5}
    },

    # 用户模型：必须传 BaseModel 子类，而不是 dict
    user_config={"model": MyTenantUser},
)
```

> 关于 `user_config.model`：必须是 `pydantic.BaseModel` 的子类（参考 8.3 多租户配置），传 `{"user_id": str, ...}` 这种 type-hint 字典会被 Pydantic 校验拒掉。

### 8.2 环境变量

```bash
# OpenAI
export OPENAI_API_KEY="sk-..."

# OpenRouter
export OPENROUTER_API_KEY="..."

# 自定义 API
export CUSTOM_API_KEY="..."
```

## 9. 最佳实践

### 9.1 生产环境配置

```python
# 生产环境：PostgreSQL + pgvector（向量列写在同一张表里）
service = MemoryService(
    database_config={
        "metadata_store": {
            "provider": "postgres",
            "dsn": "postgresql://memu:secure_password@db.example.com:5432/memu_prod",
            "ddl_mode": "validate",
        },
        # 不显式给 vector_index 时，postgres 会自动联动到 pgvector，dsn 复用 metadata_store
        "vector_index": {"provider": "pgvector"},
    }
)
```

> `MetadataStoreConfig` 只接受 `provider / ddl_mode / dsn` 三个字段，不再支持 `host/port/database/user/password` 拆开传——务必拼成 DSN。
> `VectorIndexConfig.provider` 合法值是 `bruteforce | pgvector | none`，没有 `postgres`、`inmemory` 这种字面量。

### 9.2 开发环境配置

```python
# 开发环境：纯内存，零依赖
service = MemoryService(
    database_config={
        "metadata_store": {"provider": "inmemory"},
        "vector_index": {"provider": "bruteforce"},  # InMemory 走 numpy bruteforce
    }
)
```

### 9.3 多租户配置

```python
from pydantic import BaseModel

class TenantUser(BaseModel):
    tenant_id: str
    user_id: str

service = MemoryService(
    user_config={"model": TenantUser}
)

# 检索时指定租户
result = await service.retrieve(
    queries=[...],
    where={"tenant_id": "corp_a"}
)
```

## 10. 总结

memU 的多模态和集成能力：

1. **统一接口**：所有 modality 走同一个 `_memorize_preprocess_multimodal` 调度，下游永远是 `(text, caption)` 二元组；
2. **客户端分层**：`sdk` / `httpx` / `lazyllm_backend` 三种 LLM client backend 各司其职，国产模型走 LazyLLM、OpenRouter 或 Doubao backend；
3. **embedding 极简**：内置只有 OpenAI 兼容 + Doubao，其他 provider 都通过"OpenAI 兼容入口"接入；
4. **本地优先 blob**：`LocalFS.fetch` 透明处理本地路径与远程 URL，按 modality 决定是否读文本；
5. **Prompt 定制可粒度到块**：multimodal preprocess、memory type、category summary 都支持 `CustomPrompt(dict[str, PromptBlock])` 局部覆盖；
6. **多租户支持**：通过自定义 `UserModel` + `where` 实现 user/agent/session 级数据隔离。

如果你打算直接复用 memU 跑生产，重点关注三件事：

- **provider 是否真有 backend**（很多人误以为加 `provider="anthropic"` 就能走 Claude）；
- **数据库与向量索引的合法 provider 字面量**（`bruteforce / pgvector` 这种细节很容易踩坑）；
- **是否启用 salience + reinforcement**（默认 `similarity` 排序，启用要同时改 `MemorizeConfig.enable_item_reinforcement` 和 `RetrieveItemConfig.ranking`，详见 [analysis-09](./analysis-09-salience-and-reinforcement.md)）。
