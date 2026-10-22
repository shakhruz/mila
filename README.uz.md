# Mila

**Telegramdagi ochiq kodli raqamli xodim. Sizning Claude obunangizda ishlaydi, biznesingizni eslab qoladi, sizning nomingizdan faqat roziligingiz bilan ish qiladi.**

*Iliqlik uchun yaratilgan.*

[![tests](https://github.com/shakhruz/mila/actions/workflows/tests.yml/badge.svg)](https://github.com/shakhruz/mila/actions/workflows/tests.yml) [![License](https://img.shields.io/github/license/shakhruz/mila)](LICENSE)

[English](README.md) · [中文](README.zh-CN.md) · [Русский](README.ru.md) · **Oʻzbekcha**

Mila — kattaroq narsaning bir qismi. Manifestimizni o‘qing (rus va ingliz tillarida): [milagpt.io/manifest](https://milagpt.io/manifest/) · [English](https://milagpt.io/en/manifest/)

Mila — biznesingiz uchun hamkasb: mijozlaringizga javob beradi, va’dalaringizni eslab qoladi, har bir suhbatni yodda tutadi, postlar yozadi, uchrashuvlarni eslatadi va har tong nima «yonayotganini» aytadi. U bilan telefoningizdan — matn yoki ovoz orqali, xuddi jamoangizdagi odam bilan gaplashgandek gaplashasiz.

- **Raqamli xodim, universal agent emas.** Mijoz suhbatlari, va’dalar va vazifalar, egasining «ha»si uchun kartochkalar, haftalik ritm, xarajat limitlari.
- **Telegramda yashaydi.** Yangi ilova o‘rnatish shart emas.
- **Bitta Mila, ikki hamyon.** O‘zingizning Claude obunangiz (yoki o‘z Anthropic API kalitingiz) — siz uchun, unga o‘zingiz kirasiz; mijozlar va mehmonlarga Mila API kalit orqali [OpenRouter](https://openrouter.ai) tokenlarida, sarflanganicha toʻlov bilan javob beradi: xarajat faqat mijozlar bilan birga oʻsadi (mehmonlarni yoʻnaltirish: bulutli versiyada hozir bor, ochiq yadroda — mila-telegram ning keyingi chiqishi bilan). Fayllaringiz o‘z uy papkangizda qoladi; suhbatlar faqat siz tanlagan model provayderlariga boradi; Mila 100% sizniki.
- **Xavfsiz.** Sizning «ha»ingizsiz sizning nomingizdan hech narsa yuborilmaydi.
- **Ochiq yadro, Apache-2.0.**

## Mijozingiz tilida gapiradi

Qutidan 3 ta til — **inglizcha, ruscha, o‘zbekcha**; o‘zingiznikini bitta fayl bilan qo‘shasiz. Mila mijoz qaysi tilda yozsa, o‘sha tilda javob beradi.

## Tez boshlash

≈ 5 daqiqa. Kerak: Claude Code (Claude obunasi bilan), [Bun](https://bun.sh), `@BotFather`dan bot tokeni.

```sh
curl -fsSL https://raw.githubusercontent.com/shakhruz/mila/main/install/get.sh | bash
```

Buyruq Claude Code, Bun va git’ni tekshiradi, to‘plamni `~/mila` ga yuklaydi va Telegram plaginini `mila-telegram` o‘rnatadi.

Keyin Claude Code sessiyasida:

```
/mila-telegram:configure <@BotFather bergan token>
```

`mila` bilan qayta ishga tushiring, botga yozing, juftlang (`/mila-telegram:access pair <kod>`) va kirishni yoping: `/mila-telegram:access policy allowlist`. Bot jim bo‘lsa — `mila doctor`.

## Claude — Anthropic qoidalari bo‘yicha

Mila Claude Code’da Anthropic chiqargan holida, o‘zgartirishsiz ishlaydi. Har bir egasi uni o‘zi o‘rnatadi va o‘zi kiradi:
o‘z Claude obunasi (Pro yoki Max) yoki o‘z Anthropic API kaliti bilan. Kirish — Anthropic sahifasida; Mila uni ko‘rmaydi va saqlamaydi.
Milani boshqa odamga sozlab beradigan hamkor mijozlarni o‘z obunasida yuritmaydi, ularning Claude uchun to‘lamaydi, uni qayta sotmaydi
va birovning kirish ma’lumotlarini yig‘maydi. Botingizga yozgan mijoz va mehmonlarga API kalit orqali, kalit egasi hisobidan xizmat ko‘rsatiladi.
Manba: [Claude Code — legal and compliance](https://code.claude.com/docs/en/legal-and-compliance).

To‘liq ma’lumot — [English README](README.md) va [docs/REFERENCE.md](docs/REFERENCE.md).
