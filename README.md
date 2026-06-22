# unframed

**AI 自举叙事游戏** — AI 从零开始构建世界观、规则、角色与剧情。

[![PyPI - Version](https://img.shields.io/pypi/v/unframed.svg)](https://pypi.org/project/unframed)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/unframed.svg)](https://pypi.org/project/unframed)

## 核心设计

- **AI 是唯一的创世者**：没有硬编码的游戏机制，所有规则由 AI 在运行时自行定义。
- **状态即真相**：游戏世界的唯一状态存储在 `vars` 字典中，AI 通过工具调用显式读写。
- **记忆分层**：核心区 (Pinned) / 活跃区 (Active) / 目录区 (Catalog) 三层显示，防止上下文溢出。
- **元数据锁定**：变量语义 (`meta`) 一旦定义不可覆盖，确保概念一致性。

## 安装

```bash
pip install unframed
```

## 使用

```bash
# 需要设置 OPENAI_API_KEY 环境变量
export OPENAI_API_KEY="sk-..."
unframed

# 指定模型（支持所有 OpenAI 兼容 API）
unframed --model deepseek-chat

# 自定义 API 地址
unframed --base-url https://api.example.com/v1
```

### 游戏内命令

| 命令 | 说明 |
|------|------|
| 直接输入 | 你的行动或对话，AI 会推进剧情 |
| `/quit` | 退出游戏 |
| `/save <path>` | 存档到文件 |
| `/load <path>` | 从文件读档 |

## CLI 选项

```
unframed [--api-key API_KEY] [--base-url BASE_URL] [--model MODEL]
```

- `--api-key`：OpenAI 兼容 API Key（默认读 `OPENAI_API_KEY` 环境变量）
- `--base-url`：自定义 API 地址
- `--model`：模型名，默认 `gpt-4o`

## 开发

```bash
# 克隆并安装
git clone https://github.com/zaf-x/unframed.git
cd unframed
hatch env create
pip install -e /path/to/ai-util  # 依赖 ai-util
hatch run unframed --help

# 运行测试
hatch run python tests/test_engine.py
```

## 架构

- `src/unframed/engine.py` — 核心引擎：状态管理、工具定义、Prompt 组装、游戏循环
- `src/unframed/cli.py` — 交互式 CLI 入口
- 基于 [ai-util](https://github.com/zaf-x/ai-util) 框架

## 依赖

- Python >= 3.8
- [ai-util](https://github.com/zaf-x/ai-util) >= 0.4
- [openai](https://pypi.org/project/openai/) >= 1.0

## License

`unframed` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
