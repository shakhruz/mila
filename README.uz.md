# Mila Agent

**Telegram uchun ochiq kodli biznes-agent. Sizning Claude obunangizda ishlaydi, biznesingizni eslab qoladi va xabarnomalar, pullik ish hamda yangi chatlarga xabardan oldin «ha»ingizni so‘raydi.**

*Iliqlik uchun yaratilgan.*

[![tests](https://github.com/shakhruz/mila-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/shakhruz/mila-agent/actions/workflows/tests.yml) [![Latest release](https://img.shields.io/github/v/release/shakhruz/mila-agent?sort=semver&label=release)](https://github.com/shakhruz/mila-agent/releases/latest) [![License](https://img.shields.io/github/license/shakhruz/mila-agent)](LICENSE)

[English](README.md) · [中文](README.zh-CN.md) · [Русский](README.ru.md) · **Oʻzbekcha**

**Joriy chiqish: [v1.6.6](https://github.com/shakhruz/mila-agent/releases/latest)** · [nima yangi](CHANGELOG.md)

Mila — kattaroq narsaning bir qismi. Manifestimizni o‘qing (rus va ingliz tillarida): [milagpt.io/manifest](https://milagpt.io/manifest/) · [English](https://milagpt.io/en/manifest/)

Mila — biznesingiz uchun hamkasb: mijozlaringizga javob beradi, va’dalaringizni eslab qoladi, har bir suhbatni yodda tutadi, postlar yozadi, uchrashuvlarni eslatadi va har tong nima «yonayotganini» aytadi. U bilan telefoningizdan — matn yoki ovoz orqali, xuddi jamoangizdagi odam bilan gaplashgandek gaplashasiz.

### Claude — Anthropic qoidalari bo‘yicha

- Mila oddiy, o‘zgartirilmagan Claude Code’da ishlaydi — Anthropic chiqargan holida.
- Siz o‘zingiz, faqat Anthropic sahifasida kirasiz: o‘z Claude rejangiz yoki o‘z Anthropic API kalitingiz bilan. Mila kirish ma’lumotlari va tokenni nusxalamaydi va saqlamaydi; OAuth-tokenni o‘zingiz ham hech qayerga nusxalamang.
- Rejangiz — o‘zingiz uchun. Botingizga yozgan mijoz va mehmonlarga API kalit orqali, kalit egasi hisobidan xizmat ko‘rsatiladi.
- Milani sizga sozlab beradigan hamkor sizni o‘z obunasida yuritmaydi, Claude uchun to‘lamaydi, uni qayta sotmaydi va kirish ma’lumotlarini yig‘maydi.

Manba: [Claude Code — legal and compliance](https://code.claude.com/docs/en/legal-and-compliance).

- **Raqamli xodim, universal agent emas.** Mijoz suhbatlari, va’dalar va vazifalar, egasining «ha»si uchun kartochkalar, haftalik ritm, xarajat limitlari.
- **Telegramda yashaydi.** Yangi ilova o‘rnatish shart emas.
- **Bitta Mila, ikki hamyon.** O‘zingizning Claude obunangiz (yoki o‘z Anthropic API kalitingiz) — siz uchun, unga o‘zingiz kirasiz; mijozlar va mehmonlarga Mila API kalit orqali [OpenRouter](https://openrouter.ai) tokenlarida, sarflanganicha toʻlov bilan javob beradi: xarajat faqat mijozlar bilan birga oʻsadi (mehmonlarni yoʻnaltirish: bulutli versiyada hozir bor, ochiq yadroda — mila-telegram ning keyingi chiqishi bilan). Fayllaringiz o‘z uy papkangizda qoladi; suhbatlar faqat siz tanlagan model provayderlariga boradi; Mila 100% sizniki.
- **Katta qadamlardan oldin so‘raydi.** Yuborish qo‘riqchisi bir suhbatni boshqasiga o‘tkazadigan va siz ulamagan chatga ketadigan xabarni to‘xtatadi; botingizdan xabarnoma va limitdan ortiq xarajat — sizning ✅ bilan. Ulangan chatlardagi oddiy javoblar tekshirilmaydi.
- **Ochiq yadro, Apache-2.0.**

## Mijozingiz tilida gapiradi

Qutidan 3 ta til — **inglizcha, ruscha, o‘zbekcha**; o‘zingiznikini bitta fayl bilan qo‘shasiz. Mila mijoz qaysi tilda yozsa, o‘sha tilda javob beradi.

## Tez boshlash

≈ 5 daqiqa. Kerak: Claude Code (Claude obunasi bilan), [Bun](https://bun.sh), `@BotFather`dan bot tokeni.

```sh
curl -fsSL https://raw.githubusercontent.com/shakhruz/mila-agent/main/install/get.sh | bash
```

Buyruq Claude Code, Bun va git’ni tekshiradi, to‘plamni `~/mila` ga yuklaydi va Telegram plaginini `mila-telegram` o‘rnatadi.

Keyin uch qadam, har biri tekshiriladi:

```sh
mila onboard
```

1. **Bot tokeni** — yashirin kiritasiz, Telegram tasdiqlaydi, 600 huquqli faylga yoziladi.
2. **Claude** — kirmagan bo‘lsangiz, Anthropic’ning o‘z kirish sahifasi ochiladi; Mila uni ko‘rmaydi.
3. **Juftlash** — 6 belgili kod olasiz va uni botingizga yuborasiz; siz — egasiz (allowlist va `OWNER_ID`).

Keyin — `mila`. `mila onboard --check` hech narsani o‘zgartirmasdan uch qadamni ko‘rsatadi. Bot jim bo‘lsa — `mila doctor`.

**Milaning ochiq kamchiliklari.** Faqat Telegram. Claude Code va o‘z Claude rejangiz yoki API kalitingiz kerak. Mila kompyuteringiz va sessiya ishlayotgan paytda javob beradi: noutbuk yopiq — Mila jim, doim yoqilgan kompyuter yoki server kerak. macOS va Linux; Windows — faqat WSL orqali. Claude Code’da kanallar hali sinov rejimida, shuning uchun ishga tushirgich hozircha ishlab chiqish bayrog‘idan foydalanadi.

## Hamjamiyat

<!-- Discord: badge + invite link go here when the invite is ready -->
Savollar, g‘oyalar, Milangiz nima qilayotganini ko‘rsating: [GitHub Discussions](https://github.com/shakhruz/mila-agent/discussions). Xatolar — [Issues](https://github.com/shakhruz/mila-agent/issues).

To‘liq ma’lumot — [English README](README.md) va [docs/REFERENCE.md](docs/REFERENCE.md).
