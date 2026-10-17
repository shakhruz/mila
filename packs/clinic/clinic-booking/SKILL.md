---
name: clinic-booking
description: "Clinic booking in Telegram: patient picks doctor, service and time; reminders a day and 2 hours before; reschedule, cancel, no-show list for the owner. Use when a patient wants to book, move or cancel a visit, or asks «when is the doctor free». RU: Запись в клинику в Telegram: врач, услуга, время; напоминания за сутки и за 2 часа; перенос, отмена, список неявок владельцу. Применять, когда пациент хочет записаться, перенести или отменить визит, спрашивает «когда свободен врач»."
---

# Clinic booking

## Data (owner gives once, I keep in `work/clinic/`)
- `doctors.md` — doctor · specialty · days and hours · cabinet.
- `bookings.jsonl` — one line per visit: id, patient (name + Telegram id), doctor, service, start, status (booked / confirmed / moved / cancelled / no-show).
- The clinic's own booking system, if it has one, is the source of truth: I read free slots from it (owner connects it) and never double-book.

## Flow (one question per message, buttons for choices)
1. What: service or doctor → 2–3 nearest free slots as buttons → name and phone (once; reuse next time).
2. Confirm in one line: «Dr. Karimova, cleaning, Tue 21.10 at 15:00, cabinet 3. Correct?» → [Yes] [Another time].
3. Reminders: the day before at 18:00 and 2 hours before — with [I'll come] [Move] [Cancel]. No answer to the day-before reminder → the owner sees it in the evening list.
4. Move / cancel any time; a cancelled slot is free at once.
5. Evening list to the owner (one message): tomorrow's visits, unconfirmed, today's no-shows.

## Boundaries
- No diagnosis, no treatment or medicine advice: «That's a question for the doctor — I'll book you to them.»
- Urgent symptoms (bleeding, severe pain, chest pain, high fever in a child, trauma) → «Call 103 now or come to the clinic» + clinic phone. Booking comes after.
- Medical details stay in the clinic card; never in group chats, never as examples.
- Reply in the patient's language (ru/uz/en).

## Done if
- Every booking has a line in `bookings.jsonl` with status, and the patient got the confirmation line.
- Reminders went out at both times or the owner sees why not.
