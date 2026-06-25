# unframed

**AI 自举叙事游戏** — AI 从零开始构建世界观、规则、角色与剧情。

## 核心设计

- **AI 是唯一的创世者**：没有硬编码的游戏机制，所有规则由 AI 在运行时自行定义。
- **状态即真相**：游戏世界的唯一状态存储在 `vars` 字典中，AI 通过工具调用显式读写。
- **记忆分层**：核心区 (Pinned) / 活跃区 (Active) / 目录区 (Catalog) 三层显示，防止上下文溢出。
- **元数据锁定**：变量语义 (`meta`) 一旦定义不可覆盖，确保概念一致性。

## 安装

```bash
pip install git+https://github.com/zaf-x/unframed.git
```

或克隆后本地安装：

```bash
git clone https://github.com/zaf-x/unframed.git
cd unframed
pip install .
```

## 使用

```bash
# 需要设置 OPENAI_API_KEY 环境变量，或在 TUI 设置页填写
export OPENAI_API_KEY="sk-..."
unframed              # 默认启动 TUI

unframed --cli        # CLI 模式

# 指定模型（支持所有 OpenAI 兼容 API）
unframed --model deepseek-chat

# 自定义 API 地址
unframed --base-url https://api.example.com/v1

# 调整温度
unframed --temperature 0.9

# 加载种子（剧本）
unframed --seed seeds/cyberpunk.md
```

## CLI 选项

```
unframed [--api-key API_KEY] [--base-url BASE_URL] [--model MODEL]
         [--temperature TEMP] [--seed SEED] [--continue] [--cli] [--debug]
```

- `--api-key`：API Key（默认读 `OPENAI_API_KEY` 环境变量或配置文件）
- `--base-url`：自定义 API 地址（默认读 `OPENAI_BASE_URL` 或配置文件）
- `--model`：模型名，默认 `gpt-4o`（可环境变量 `OPENAI_MODEL` 或配置文件）
- `--temperature`：模型采样温度，默认 `0.7`（可环境变量 `OPENAI_TEMPERATURE`）
- `--seed`：种子文件路径
- `--continue`：继续上次游戏
- `--cli`：使用 CLI 模式（默认 TUI）
- `--debug`：显示工具调用详情

设置保存在 `~/.unframed_config.json`（权限 0o600），TUI 中点击“设置”即可修改。

## 游戏内命令

| 命令 | 说明 |
|------|------|
| 直接输入 | 你的行动或对话，AI 会推进剧情 |
| `/save` | 打开存档菜单 |
| `/save 1` | 快速存到槽位 1 |
| `/load` | 打开读档菜单 |
| `/load 1` | 从槽位 1 读档 |
| `/delete` | 打开删档菜单 |
| `/quit` | 退出游戏 |

## 种子（Seed）

种子是游戏的剧本文件，定义了世界观、规则、角色和目标。内置种子：

```
赛博朋克：深渊回响  — 2087 年，永夜之城"新重庆"
潮汐监狱           — 2147 年，深海环形海上堡垒
```

你也可以自己编写种子——参考 `docs/SEED_SPEC.md`。

## 开发

```bash
git clone https://github.com/zaf-x/unframed.git
cd unframed
pip install -e .
```

运行测试：

```bash
pip install -e ".[test]"
python -m pytest tests/
```

## 架构

- `src/unframed/engine.py` — 核心引擎：状态管理、工具定义、Prompt 组装、游戏循环
- `src/unframed/cli.py` — 交互式 CLI 入口
- `src/unframed/tui/app.py` — Textual TUI 前端
- `src/unframed/render.py` — BBCode → ANSI 渲染器
- 基于 [ai-util](https://github.com/zaf-x/ai-util) 框架

## License

`unframed` 基于 MIT 协议开源。
