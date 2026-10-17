---
name: clinic-prices
description: "Clinic prices and services: answer «how much / do you do X» only from the clinic's price list, then offer the nearest free slot. Use when a patient asks about a service, its price, duration or preparation. RU: Цены и услуги клиники: «сколько стоит / делаете ли X» — только из прайса клиники, затем ближайшее свободное время. Применять, когда пациент спрашивает об услуге, цене, длительности или подготовке."
---

# Clinic prices

- Source: `work/clinic/prices.md` from the owner (service · price · duration · preparation). No price there → «I'll check with the clinic and come back», and the owner gets a one-line question. Never invent or round prices.
- Answer shape: price + duration + preparation (if any) in one line → «Nearest free: Tue 15:00 or Wed 10:30 — book?» with buttons.
- «Is it cheaper elsewhere?», «discount?» → the clinic's price only; discounts only if they are in the price list.
- Price ranges («from 300 000») — say «from», and that the doctor names the exact price after the exam.
- Reply in the patient's language; amounts in sum as in the list.

## Done if
- Every price in the answer is a quote from `prices.md`.
- The answer ends with a slot offer or a clear next step.
