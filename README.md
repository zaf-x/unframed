# unframed

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-0.1.0-blue)]()
[![GitHub](https://img.shields.io/badge/GitHub-zaf--x%2Funframed-181717?logo=github)](https://github.com/zaf-x/unframed)

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

# 调整温度（越高越有创意，越低越稳定）
unframed --temperature 0.9

# 加载种子（剧本）
unframed --seed seeds/cyberpunk.md
```

## CLI 选项

```
unframed [--api-key API_KEY] [--base-url BASE_URL] [--model MODEL]
         [--temperature TEMP] [--seed SEED] [--continue] [--cli] [--debug]
```

| 选项 | 说明 |
|------|------|
| `--api-key KEY` | API Key（默认读 `OPENAI_API_KEY` 环境变量或配置文件） |
| `--base-url URL` | 自定义 API 地址（默认读 `OPENAI_BASE_URL` 或配置文件） |
| `--model NAME` | 模型名，默认 `gpt-4o`（优先级：参数 > `OPENAI_MODEL` > 配置） |
| `--temperature NUM` | 采样温度 0-2，默认 `0.7`（优先级：参数 > `OPENAI_TEMPERATURE` > 配置） |
| `--seed PATH` | 种子文件路径（Markdown），跳过菜单直接加载 |
| `--continue` | 继续上次游戏 |
| `--cli` | 使用 CLI 模式（默认 TUI） |
| `--debug` | 显示工具调用详情 |

设置保存在 `~/.unframed_config.json`（权限 0o600），TUI 中点击"设置"即可修改。

## 游戏内命令

### TUI 模式

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 发送消息 |
| `Ctrl+S` | 打开存档管理器 |
| `Ctrl+L` | 打开读档列表 |
| `Ctrl+D` | 打开删档列表 |

### CLI 模式

| 命令 | 说明 |
|------|------|
| 直接输入 | 你的行动或对话，AI 会推进剧情 |
| `/save` | 打开存档菜单 |
| `/save 我的存档` | 快速存到指定名称（新建或覆盖） |
| `/save list` | 列出所有存档 |
| `/load` | 打开读档菜单 |
| `/load 我的存档` | 快速加载指定名称的存档 |
| `/delete` | 打开删档菜单 |
| `/quit` | 退出游戏 |

## 种子（Seed）

种子是游戏的剧本文件，定义了世界观、规则、角色和目标。游戏启动时自动识别 `seeds/` 下的所有种子。

内置种子：

```
赛博朋克：深渊回响  — 2087 年，永夜之城"新重庆"
潮汐监狱           — 2147 年，深海环形海上堡垒
锈蚀边境：绿洲协议  — 2147 年，核冬天后的废土求生
孤星：坠落日       — 2247 年，殖民船坠毁后的外星求生
霓虹裁决           — 2140 年，同步轨道升降梯内
```

你也可以自己编写种子——参考 `docs/SEED_SPEC.md`。

## 存档

存档文件存储在 `~/.unframed_saves/` 目录，每局一个 UUID 文件（`{uuid}.json`）。

- 自动保存：每轮自动保存到当前存档
- 继续存档：主菜单"继续上一个存档"可直接回到上次的游戏
- 管理存档：TUI 中 `Ctrl+S` 可保存/重命名/删除/新建存档

## 开发

```bash
git clone https://github.com/zaf-x/unframed.git
cd unframed
pip install -e .
```

运行测试：

```bash
pip install -e .
pip install pytest
python -m pytest tests/
```

## 架构

```text
src/unframed/
├── engine.py    — 核心引擎：状态管理、工具定义、Prompt 组装、游戏循环
├── cli.py       — 交互式 CLI 入口（启动菜单、命令行命令）
├── tui/app.py   — Textual TUI 前端（图形界面）
├── settings.py  — 持久化配置（~/.unframed_config.json）
└── render.py    — BBCode → ANSI 渲染器
```

基于 [ai-util](https://github.com/zaf-x/ai-util) 框架。

## License

`unframed` 基于 MIT 协议开源。
