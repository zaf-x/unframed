# DeepSeek API Key 获取指南

unframed 支持所有 OpenAI 兼容 API，**DeepSeek** 是目前性价比最高的选择之一。以下是获取 DeepSeek API Key 的步骤。

## 注册与获取

### 1. 访问 DeepSeek 开放平台

打开 https://platform.deepseek.com/

### 2. 注册/登录

- 支持手机号（中国大陆）或邮箱注册
- 注册后需完成手机验证

### 3. 领取充值赠送金

注册后通常赠送 **500 万 tokens**（约 ¥7.5 左右），无需充值即可开始使用。具体额度以官网最新活动为准。

### 4. 创建 API Key

1. 登录后进入左侧 **API Keys** 页面
2. 点击 **"创建 API Key"**
3. 为 Key 起个名字（如 "unframed"）
4. 复制生成的 Key（以 `sk-` 开头）
5. **关闭页面后不可再次查看**，请立即保存

### 5. 配置 unframed

**方式一：环境变量（推荐）**

```bash
export OPENAI_API_KEY="sk-你的key"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export OPENAI_MODEL="deepseek-chat"
unframed
```

**方式二：TUI 设置页面**

1. 运行 `unframed`
2. 主菜单 → **设置**
3. 填写：
   - **API Key**: `sk-你的key`
   - **Base URL**: `https://api.deepseek.com/v1`
   - **Model**: `deepseek-chat`（或其他 DeepSeek 模型）
4. 点击 **保存**

**方式三：命令行参数**

```bash
unframed --api-key sk-你的key --base-url https://api.deepseek.com/v1 --model deepseek-chat
```

## 可用模型

| 模型 | 说明 | 适合场景 |
|------|------|---------|
| `deepseek-v4-flash` | V4 Flash 系列，快速轻量 | 日常游戏，响应快，性价比最高 |
| `deepseek-v4-pro` | V4 Pro 系列，更强推理 | 复杂剧情，更高质量的叙事 |

## 注意事项

- **不要分享你的 API Key** — 别人拿到后可以用你的额度调用
- **免费额度有限** — 500 万 tokens 大约够玩几十小时，用完后需充值
- **充值最低** — DeepSeek 充值门槛较低，约 ¥10 起
- **计费方式** — 按 tokens 计费，输入和输出价格不同，详见 DeepSeek 官网定价页面
- **国内直连** — DeepSeek 服务器在国内，无需翻墙，延迟低

## 其他兼容 API

| 服务商 | Base URL | 特点 |
|--------|---------|------|
| DeepSeek | `https://api.deepseek.com/v1` | 性价比高，国内直连 |
| OpenAI | `https://api.openai.com/v1` | 原版，需翻墙 |
| 硅基流动 | `https://api.siliconflow.cn/v1` | 国内镜像，部分免费模型 |
| 阿里通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | 国内，有免费额度 |

选择 `Base URL` 时，**必须**以 `/v1` 结尾。
