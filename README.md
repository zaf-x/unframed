# unframed

[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE.txt)
[![Version](https://img.shields.io/badge/version-0.3.0-blue)]()
[![PyPI](https://img.shields.io/badge/pypi-v0.3.0-blue?logo=pypi)](https://pypi.org/project/unframed/)
[![GitHub](https://img.shields.io/badge/GitHub-zaf--x%2Funframed-181717?logo=github)](https://github.com/zaf-x/unframed)

**AI 自举叙事游戏** — AI 从零开始构建世界观、规则、角色与剧情。

## 核心设计

- **AI 是唯一的创世者**：没有硬编码的游戏机制，所有规则由 AI 在运行时自行定义。
- **状态即真相**：游戏世界的唯一状态存储在 `vars` 字典中，AI 通过工具调用显式读写。
- **记忆分层**：核心区 (Pinned) / 活跃区 (Active) / 目录区 (Catalog) 三层显示，防止上下文溢出。
- **元数据锁定**：变量语义 (`meta`) 一旦定义不可覆盖，确保概念一致性。
- **剧情规划**：AI 构建剧情树，提前规划走向，跳过的分支自动修剪。
- **子AI系统**：AI 可创建持久化的 NPC 角色，拥有独立记忆。

## 安装

Python 3.8+ 环境：

```bash
pip install unframed
```

或

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

# 加载种子（剧本），自动使用 CLI 模式
unframed --seed ~/.unframed/seeds/cyberpunk.md

# 继续上次游戏，自动使用 CLI 模式
unframed --continue

# 显示帮助
unframed --help
```

> **注**：使用 `--seed`、`--continue` 或 `--debug` 时会自动切换到 CLI 模式。

## CLI 选项

```
unframed [--api-key API_KEY] [--base-url BASE_URL] [--model MODEL]
         [--temperature TEMP] [--seed SEED] [--seed-dir DIR]
         [--continue] [--cli] [--debug] [--help]
```

| 选项 | 说明 |
|------|------|
| `--api-key KEY` | API Key（默认读 `OPENAI_API_KEY` 环境变量或配置文件） |
| `--base-url URL` | 自定义 API 地址（默认读 `OPENAI_BASE_URL` 或配置文件） |
| `--model NAME` | 模型名，默认 `gpt-4o`（优先级：参数 > `OPENAI_MODEL` > 配置） |
| `--temperature NUM` | 采样温度 0-2，默认 `0.7`（优先级：参数 > `OPENAI_TEMPERATURE` > 配置） |
| `--seed PATH` | 种子文件路径（Markdown），跳过菜单直接加载（自动 CLI） |
| `--seed-dir DIR` | 额外种子目录（可多次指定），其中的种子自动出现在菜单中 |
| `--continue` | 继续上次游戏（自动 CLI） |
| `--cli` | 使用 CLI 模式（默认 TUI） |
| `--debug` | 显示工具调用详情（自动 CLI） |
| `--help` | 显示玩家手册 |

设置保存在 `~/.unframed/config.json`（权限 0o600），TUI 中主菜单→"设置"即可修改。

### 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | API Key |
| `OPENAI_BASE_URL` | API 地址（如 `https://api.example.com/v1`） |
| `OPENAI_MODEL` | 模型名（默认 `gpt-4o`） |
| `OPENAI_TEMPERATURE` | 采样温度（默认 `0.7`） |

读取优先级：**CLI 参数 > 环境变量 > 配置文件 > 内置默认**

## TUI 模式

### TUI 界面布局

```
┌──────────────────────────────────────────────────┐
│  U N F R A M E D                      14:30:21   │
├────────────────────────────────┬─────────────────┤
│                                │ ## 角色状态      │
│  叙事区域                       │ - **生命值**: 85 │
│  （AI 的故事输出，Markdown 渲染） │ - **位置**: 断指  │
│                                │   酒吧           │
│                                │                  │
│                                │ ---              │
│                                │ 回合 12          │
├────────────────────────────────┴─────────────────┤
│  AI 正在构思剧情...                                │
├──────────────────────────────────────────────────┤
│  > 输入你的行动...                        [发送]  │
└──────────────────────────────────────────────────┘
```

- **左侧**：叙事输出区，AI 生成的故事以 Markdown 渲染
- **右侧**：角色状态面板 — AI 使用 `show_var` 工具标记为玩家可见的变量
- **底部**：输入框，输入你的行动或对话
- **状态栏**：AI 处理时显示当前操作（如"正在修改世界状态"）

### 启动菜单

| 选项 | 说明 |
|------|------|
| **新建存档** | 输入存档名 → 选择种子 → 开始新游戏 |
| **继续上一个存档** | 直接回到上次玩的存档（仅在有历史时显示） |
| **加载存档** | 从已有存档中选择一个加载 |
| **存档管理** | 查看/保存/删除/重命名所有存档 |
| **设置** | 配置 API Key、模型、温度等 |
| **文档** | 查看玩家手册 |
| **退出** | 退出游戏 |

### TUI 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Enter` | 发送消息 |
| `Escape` | 返回主菜单（当前回合会先自动存档） |
| `Ctrl+S` | 打开存档管理器（Enter=保存，Delete=删除，R=重命名） |
| `Ctrl+L` | 打开读档列表 |
| `Ctrl+D` | 打开删档列表 |

## CLI 模式

### 启动菜单

| 选项 | 说明 |
|------|------|
| **新建存档** | 输入存档名 → 选择种子 → 开始新游戏 |
| **继续上一个存档** | 直接回到上次玩的存档 |
| **加载存档** | 从已有存档中选择一个加载 |
| **帮助文档** | 查看玩家手册 |

### 游戏中命令

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

种子是游戏的"剧本文件"，定义了世界观、规则、角色和目标。每个种子由一对文件组成：`seeds/<名称>.json`（元数据）和 `seeds/<名称>.md`（剧本内容）。游戏启动时自动识别 `seeds/` 下所有 `.json` 索引文件。

内置种子：

- **赛博朋克：深渊回响** — 2087 年，永夜之城"新重庆"
- **潮汐监狱** — 2147 年，深海环形海上堡垒
- **锈蚀边境：绿洲协议** — 2147 年，核冬天后的废土求生
- **孤星：坠落日** — 2247 年，殖民船坠毁后的外星求生
- **霓虹裁决** — 2140 年，同步轨道升降梯内
- **循环日** — 无法逃脱的时间循环
- **午夜频率** — 深夜广播信号背后的秘密
- **sudo apt 求生记** — 身为 APT 包管理器，面对一次危险的依赖冲突
- **地下王座** — 地下王国的权力与阴谋

你也可以自己编写种子——参考 `docs/SEED_SPEC.md`。

## 子AI系统（NPC）

unframed 支持 AI 在游戏中创建和管理长期存在的子 AI 角色，作为游戏世界中的 NPC、同伴或组织：

| 工具 | 功能 |
|------|------|
| **创建角色** | AI 可创建拥有独立性格、知识范围和记忆的 NPC |
| **与角色对话** | AI 可与已有 NPC 对话，并根据其性格做出回应 |
| **移除角色** | NPC 死亡或离开时，AI 可终止该角色 |

子 AI 可以读取世界状态变量了解当前局势，但不能直接修改它们。它们拥有独立对话记忆，会记住每一次交流。玩家通过主 AI 的叙事感知子 AI 的行为，子 AI 不直接与玩家交互。

## 存档

存档文件存储在 `~/.unframed/saves/` 目录，每局一个 UUID 文件（`{uuid}.json`）。

- **自动保存**：每轮自动保存到当前存档
- **继续存档**：主菜单"继续上一个存档"可直接回到上次的游戏
- **存档管理**：TUI 中 `Ctrl+S` 可保存/重命名/删除/新建存档
- **存档内容**：回合数、变量数据库、对话历史、剧情树、子 AI 状态

## 开发

```bash
git clone https://github.com/zaf-x/unframed.git
cd unframed
pip install -e .
```

运行测试：

```bash
pip install pytest
python -m pytest tests/
```

## 架构

```text
src/unframed/
├── __about__.py   — 版本信息
├── __init__.py    — 公共 API
├── engine.py      — 核心引擎：状态管理、工具定义、Prompt 组装、游戏循环
├── cli.py         — 交互式 CLI 入口（启动菜单、命令行命令）
├── settings.py    — 持久化配置（~/.unframed/config.json）
├── render.py      — BBCode → ANSI 渲染器
└── tui/
    ├── __init__.py — TUI 模块声明
    └── app.py      — Textual TUI 前端（图形界面）
```

基于 [ai-util](https://github.com/zaf-x/ai-util) 框架。

## 数据目录

首次运行后会在用户目录下创建：

```
~/.unframed/
├── config.json       # 持久化配置（权限 0o600）
├── saves/            # 存档文件（UUID 命名）
├── seeds/            # 种子文件（首次运行自动复制内置种子）
├── autosave.json     # CLI 模式自动存档
└── history           # CLI 命令历史
```

## License

`unframed` 基于 MIT 协议开源。
