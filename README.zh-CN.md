# Mila

**Telegram 里的开源数字员工。使用你自己的 Claude 订阅运行，记得住你的业务，只有经你同意才会以你的名义行事。**

*Warm by design.*

[English](README.md) · **中文** · [Русский](README.ru.md) · [Oʻzbekcha](README.uz.md)

[![tests](https://github.com/shakhruz/mila/actions/workflows/tests.yml/badge.svg)](https://github.com/shakhruz/mila/actions/workflows/tests.yml) [![License](https://img.shields.io/github/license/shakhruz/mila)](LICENSE)

Mila 是更大愿景的一部分 —— 阅读我们的宣言（英文）：[milagpt.io/en/manifest](https://milagpt.io/en/manifest/)

- **在 Telegram 里回复你的客户** —— 全天候在线，用客户的语言回复。
- **记住你的业务** —— 每一位客户、每一次对话、每一个承诺；每天早上给你一份简短汇总。
- **一个 Mila，两个钱包** —— 你自己的 Claude 订阅（或你自己的 Anthropic API 密钥）为你本人服务，由你本人登录；客户和访客由 Mila 通过 API 密钥、以 [OpenRouter](https://openrouter.ai) 按量计费的 token 回复：费用只随客户数量增长（访客分流：托管版已经提供，开源核心将随 mila-telegram 下一个版本加入）。
- **以你的名义行事，必先征得你的同意** —— 每一次这样的操作都会记录在日志里；你的文件保存在你自己的主目录（home 文件夹）里，对话内容只会发送给你选定的模型服务商。

## 快速开始

约需 5 分钟。你需要：Claude Code（以及 Claude 订阅）、[Bun](https://bun.sh)、从 `@BotFather` 获取的 Telegram 机器人 token。

```sh
curl -fsSL https://raw.githubusercontent.com/shakhruz/mila/main/install/get.sh | bash
```

然后在 Claude Code 会话中运行：

```
/plugin marketplace add shakhruz/mila-telegram
/plugin install mila-telegram@mila
/mila-telegram:configure <从 @BotFather 获取的 token>
```

用 `mila` 重新启动，给你的机器人发一条消息，完成配对（`/mila-telegram:access pair <验证码>`），然后关闭对外访问（仅允许白名单用户）：`/mila-telegram:access policy allowlist`。机器人没有反应时，运行 `mila doctor`。

## Claude —— 遵守 Anthropic 的规则

Mila 运行在 Anthropic 发布的原版 Claude Code 上，不做任何修改。每位主人自己安装、自己登录：使用自己的 Claude 订阅（Pro 或 Max）
或自己的 Anthropic API 密钥。登录在 Anthropic 自己的页面完成；Mila 看不到也不保存登录信息。为他人配置 Mila 的合作伙伴不会用自己的订阅
服务其客户，不为他们的 Claude 付费、不转售、不代为中转，也不收集任何人的 Claude 登录信息。给你的机器人写消息的客户和访客，通过 API 密钥
服务，费用由密钥所有者承担。来源：[Claude Code — legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)。

完整说明见 [English README](README.md)（英文）和 [docs/REFERENCE.md](docs/REFERENCE.md)（英文）。
