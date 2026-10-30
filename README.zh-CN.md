# Mila Agent

**面向 Telegram 的开源商业智能体。使用你自己的 Claude 订阅运行，记得住你的业务，只有经你同意才会以你的名义行事。**

*Warm by design.*

[English](README.md) · **中文** · [Русский](README.ru.md) · [Oʻzbekcha](README.uz.md)

[![tests](https://github.com/shakhruz/mila-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/shakhruz/mila-agent/actions/workflows/tests.yml) [![Latest release](https://img.shields.io/github/v/release/shakhruz/mila-agent?sort=semver&label=release)](https://github.com/shakhruz/mila-agent/releases/latest) [![License](https://img.shields.io/github/license/shakhruz/mila-agent)](LICENSE)

**当前版本：[v1.6.6](https://github.com/shakhruz/mila-agent/releases/latest)** · [更新内容](CHANGELOG.md)

Mila 是更大愿景的一部分 —— 阅读我们的宣言（英文）：[milagpt.io/en/manifest](https://milagpt.io/en/manifest/)

### Claude —— 遵守 Anthropic 的规则

- Mila 运行在普通、未经修改的 Claude Code 上，与 Anthropic 发布的版本完全一致。
- 由你本人登录，且只在 Anthropic 的页面登录：使用你自己的 Claude 套餐或你自己的 Anthropic API 密钥。Mila 不复制、不保存你的登录信息和 token；你自己也不要把 OAuth token 复制到任何地方。
- 你的套餐只供你本人使用。给你的机器人写消息的客户和访客，通过 API 密钥服务，费用由密钥所有者承担。
- 为你配置 Mila 的合作伙伴不会用自己的订阅为你服务，不为你的 Claude 付费、不转售、不代为中转，也不收集登录信息。

来源：[Claude Code — legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)。

- **在 Telegram 里回复你的客户** —— 全天候在线，用客户的语言回复。
- **记住你的业务** —— 每一位客户、每一次对话、每一个承诺；每天早上给你一份简短汇总。
- **一个 Mila，两个钱包** —— 你自己的 Claude 订阅（或你自己的 Anthropic API 密钥）为你本人服务，由你本人登录；客户和访客由 Mila 通过 API 密钥、以 [OpenRouter](https://openrouter.ai) 按量计费的 token 回复：费用只随客户数量增长（访客分流：托管版已经提供，开源核心将随 mila-telegram 下一个版本加入）。
- **以你的名义行事，必先征得你的同意** —— 每一次这样的操作都会记录在日志里；你的文件保存在你自己的主目录（home 文件夹）里，对话内容只会发送给你选定的模型服务商。

## 快速开始

约需 5 分钟。你需要：Claude Code（以及 Claude 订阅）、[Bun](https://bun.sh)、从 `@BotFather` 获取的 Telegram 机器人 token。

```sh
curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-agent/main/install/get.sh | bash
```

该命令会检查 Claude Code、Bun 和 git，把套件克隆到 `~/mila`，并安装 Telegram 插件 `mila-telegram`。

然后完成三步，每一步都会检查：

```sh
mila onboard
```

1. **机器人 token** —— 隐藏输入，由 Telegram 验证，以 600 权限保存。
2. **Claude** —— 如果尚未登录，会打开 Anthropic 自己的登录页面；Mila 看不到登录信息。
3. **配对** —— 你会得到一个 6 位验证码，从 Telegram 发给你的机器人；你就成为主人（白名单 + `OWNER_ID`）。

之后运行 `mila` 启动。`mila onboard --check` 只显示三步状态，不做任何更改。机器人没有反应时，运行 `mila doctor`。

**Mila 的真实短板。** 只支持 Telegram。需要 Claude Code 以及你自己的 Claude 套餐或 API 密钥。只有在你的电脑和会话运行时 Mila 才会回复：笔记本合上，Mila 就不回复，需要一台常开的电脑或服务器。支持 macOS 和 Linux；Windows 只能通过 WSL。Claude Code 的频道功能仍处于研究预览阶段，因此启动器目前使用开发标志。

## 社区

<!-- Discord: badge + invite link go here when the invite is ready -->
提问、分享想法、展示你的 Mila 在做什么：[GitHub Discussions](https://github.com/shakhruz/mila-agent/discussions)。问题反馈：[Issues](https://github.com/shakhruz/mila-agent/issues)。

完整说明见 [English README](README.md)（英文）和 [docs/REFERENCE.md](docs/REFERENCE.md)（英文）。
