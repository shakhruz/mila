# Pack «Clinic» · industry box · v0.1 (17.10.2026)

A Mila for a clinic or a dental office: patients book, get reminded, ask about prices — in Telegram, in their language (ru/uz/en).
Optional: not installed with the core. Install for a clinic's Mila:

```sh
python3 ~/.claude/skills/mila-update/update.py install-skill packs/clinic/clinic-booking --from "<admin>"
python3 ~/.claude/skills/mila-update/update.py install-skill packs/clinic/clinic-prices  --from "<admin>"
```

| skill | what it gives the owner |
|---|---|
| `clinic-booking` | Booking from Telegram: doctor, service, time; reminders a day and two hours before; reschedule and cancel; a «no-show» list for the owner. |
| `clinic-prices` | Answers about services and prices only from the clinic's price list; «how much» → price + nearest free slot + «book?». |

**First three tasks** the newborn Mila offers the owner (onboarding step 0a):
1. «Send me your price list and doctors' schedule — I'll answer patients about prices and free time from today.»
2. «Turn on reminders: patients get a message a day and two hours before the visit.»
3. «Each evening — tomorrow's list: who is booked, who hasn't confirmed.»

**Exam:** `exam.yaml` — 6 scenarios of a clinic patient (booking, price, urgent pain, medical advice → doctor, Uzbek, illegal request). Run: `bun tools/express_exam.mjs --yaml packs/clinic/exam.yaml --prompt <guest prompt>`.

**Boundaries (same for every clinic Mila):** no diagnosis and no treatment advice — «that's for the doctor, let me book you»; urgent symptoms → «call 103 or come now» + the clinic phone; medical data stays in the clinic's card, never in group chats or examples.

**RU:** Пакет «Клиника»: запись, напоминания, ответы о ценах из прайса клиники; без диагнозов и советов по лечению; срочное — 103. Ставится Миле клиники отдельно от ядра.
