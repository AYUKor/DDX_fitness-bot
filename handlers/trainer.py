import os
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

import database as db
from keyboards import (
    trainer_menu, days_kb, times_kb, week_nav_kb,
    confirm_booking_kb, trainer_edit_fields_kb,
    get_week_dates, fmt_date, DAYS_FULL, MONTHS_RU
)
from states import TrainerRegistration, AddSlots, EditProfile

router = Router()
logger = logging.getLogger(__name__)

TRAINER_SECRET = os.getenv("TRAINER_SECRET", "")


# ═══════════════════════════════════════════════════════════
#  REGISTRATION
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "role_trainer")
async def trainer_role(call: CallbackQuery, state: FSMContext):
    existing = await db.get_trainer(call.from_user.id)
    if existing and existing["registered"]:
        await call.message.edit_text("✅ Вы уже зарегистрированы как тренер.")
        await call.message.answer("Главное меню:", reply_markup=trainer_menu())
        return
    await call.message.edit_text(
        "🔐 <b>Регистрация тренера</b>\n\n"
        "Введите <b>секретный код</b> для тренеров\n"
        "(его выдаёт администратор зала):",
        parse_mode="HTML"
    )
    await state.set_state(TrainerRegistration.secret)


@router.message(TrainerRegistration.secret)
async def trainer_check_secret(message: Message, state: FSMContext):
    if message.text.strip() != TRAINER_SECRET:
        await message.answer("❌ Неверный код. Попробуйте ещё раз или обратитесь к администратору.")
        return
    await message.answer("✅ Код верный!\n\nВведите ваше <b>ФИО</b>:", parse_mode="HTML")
    await state.set_state(TrainerRegistration.full_name)


@router.message(TrainerRegistration.full_name)
async def trainer_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("📞 Ваш <b>номер телефона</b>:", parse_mode="HTML")
    await state.set_state(TrainerRegistration.phone)


@router.message(TrainerRegistration.phone)
async def trainer_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("📧 Ваш <b>email</b> (или «нет»):", parse_mode="HTML")
    await state.set_state(TrainerRegistration.email)


@router.message(TrainerRegistration.email)
async def trainer_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await message.answer(
        "🏋️ Ваша <b>специализация</b>\n(например: силовые тренировки, йога, кардио):",
        parse_mode="HTML"
    )
    await state.set_state(TrainerRegistration.specialization)


@router.message(TrainerRegistration.specialization)
async def trainer_specialization(message: Message, state: FSMContext):
    data = await state.get_data()
    # Берём только те поля, которые есть в таблице trainers
    trainer_data = {
        "full_name": data.get("full_name"),
        "phone": data.get("phone"),
        "email": data.get("email"),
        "specialization": message.text.strip(),
        "registered": 1
    }
    await db.upsert_trainer(message.from_user.id, **trainer_data)
    await state.clear()
    await message.answer(
        f"✅ <b>Профиль тренера сохранён!</b>\n\n"
        f"👤 {trainer_data['full_name']}\n"
        f"📞 {trainer_data['phone']}\n"
        f"📧 {trainer_data['email']}\n"
        f"🏋️ {trainer_data['specialization']}",
        parse_mode="HTML",
        reply_markup=trainer_menu()
    )


# ═══════════════════════════════════════════════════════════
#  PROFILE
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "👤 Мой профиль")
async def trainer_profile(message: Message):
    t = await db.get_trainer(message.from_user.id)
    if not t:
        return
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>ФИО:</b> {t['full_name']}\n"
        f"<b>Телефон:</b> {t['phone']}\n"
        f"<b>Email:</b> {t['email']}\n"
        f"<b>Специализация:</b> {t['specialization']}",
        parse_mode="HTML"
    )


@router.message(F.text == "✏️ Редактировать профиль")
async def trainer_edit_start(message: Message, state: FSMContext):
    t = await db.get_trainer(message.from_user.id)
    if not t:
        return
    await message.answer("✏️ <b>Что изменить?</b>", parse_mode="HTML",
                         reply_markup=trainer_edit_fields_kb())
    await state.set_state(EditProfile.choose_field)


@router.callback_query(F.data.startswith("editfield_"), EditProfile.choose_field)
async def trainer_edit_field(call: CallbackQuery, state: FSMContext):
    field = call.data.split("_", 1)[1]
    if field == "cancel":
        await call.message.edit_text("Редактирование отменено.")
        await state.clear()
        return
    labels = {
        "full_name": "ФИО",
        "phone": "номер телефона",
        "email": "email",
        "specialization": "специализацию"
    }
    await state.update_data(edit_field=field)
    await call.message.edit_text(f"Введите новое значение для «{labels.get(field, field)}»:")
    await state.set_state(EditProfile.enter_value)


@router.message(EditProfile.enter_value)
async def trainer_save_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["edit_field"]
    # Check if it's a trainer or client edit
    t = await db.get_trainer(message.from_user.id)
    if t:
        await db.upsert_trainer(message.from_user.id, **{field: message.text.strip()})
    else:
        await db.upsert_client(message.from_user.id, **{field: message.text.strip()})
    await state.clear()
    await message.answer("✅ Данные обновлены!", reply_markup=trainer_menu())


# ═══════════════════════════════════════════════════════════
#  SCHEDULE
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "📅 Моё расписание")
async def trainer_schedule(message: Message):
    t = await db.get_trainer(message.from_user.id)
    if not t:
        return
    await show_schedule(message, message.from_user.id, 0)


async def show_schedule(message: Message, trainer_id: int, offset: int):
    dates = get_week_dates(offset)
    date_strs = [d.strftime("%Y-%m-%d") for d in dates]
    slots = await db.get_slots_for_week(trainer_id, date_strs)

    if not slots:
        text = "📅 <b>На эту неделю слотов нет.</b>\nДобавьте их через «➕ Добавить слоты»."
    else:
        by_date = {}
        for s in slots:
            by_date.setdefault(s["slot_date"], []).append(s)
        lines = [f"📅 <b>Расписание:</b> {fmt_date(dates[0])} — {fmt_date(dates[-1])}\n"]
        for d in dates:
            ds = d.strftime("%Y-%m-%d")
            day_slots = by_date.get(ds, [])
            lines.append(f"\n<b>{DAYS_FULL[d.weekday()]}, {d.day} {MONTHS_RU[d.month-1]}</b>")
            if not day_slots:
                lines.append("  — выходной")
            else:
                for s in day_slots:
                    icon = "🟢" if s["is_available"] else "🔴"
                    lines.append(f"  {icon} {s['slot_time']}")
        text = "\n".join(lines)

    await message.answer(text, parse_mode="HTML", reply_markup=week_nav_kb(offset))


@router.callback_query(F.data.startswith("week_"))
async def week_nav(call: CallbackQuery):
    offset = int(call.data.split("_")[1])
    await call.message.delete()
    await show_schedule(call.message, call.from_user.id, offset)
    await call.answer()


# ═══════════════════════════════════════════════════════════
#  ADD SLOTS
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "➕ Добавить слоты")
async def add_slots_start(message: Message, state: FSMContext):
    t = await db.get_trainer(message.from_user.id)
    if not t:
        return
    await state.set_state(AddSlots.select_day)
    await state.update_data(slot_offset=0)
    await message.answer("📅 <b>Выберите день:</b>", parse_mode="HTML", reply_markup=days_kb(0))


@router.callback_query(F.data.startswith("slotnav_"), AddSlots.select_day)
async def slotnav(call: CallbackQuery, state: FSMContext):
    offset = int(call.data.split("_")[1])
    await state.update_data(slot_offset=offset)
    await call.message.edit_reply_markup(reply_markup=days_kb(offset))
    await call.answer()


@router.callback_query(F.data.startswith("slotday_"), AddSlots.select_day)
async def slot_day_chosen(call: CallbackQuery, state: FSMContext):
    day = call.data.split("_", 1)[1]
    await state.update_data(selected_day=day, selected_times=[])
    await state.set_state(AddSlots.select_times)
    await call.message.edit_text(
        f"🕐 <b>Выберите время для {day}:</b>",
        parse_mode="HTML",
        reply_markup=times_kb([])
    )


@router.callback_query(F.data.startswith("addtime_"), AddSlots.select_times)
async def toggle_time(call: CallbackQuery, state: FSMContext):
    t = call.data.split("_", 1)[1]
    data = await state.get_data()
    times = data.get("selected_times", [])
    if t in times:
        times.remove(t)
    else:
        times.append(t)
        times.sort()
    await state.update_data(selected_times=times)
    await call.message.edit_reply_markup(reply_markup=times_kb(times))
    await call.answer()


@router.callback_query(F.data == "times_done", AddSlots.select_times)
async def times_done(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    day, times = data["selected_day"], data.get("selected_times", [])
    if not times:
        await call.answer("Выберите хотя бы одно время!", show_alert=True)
        return

    # Подсчёт успешно добавленных слотов через цикл
    added = 0
    for t in times:
        if await db.add_slot(call.from_user.id, day, t):
            added += 1

    await state.clear()
    await call.message.edit_text(
        f"✅ Добавлено <b>{added}</b> слотов на <b>{day}</b>\n"
        f"Время: {', '.join(times)}",
        parse_mode="HTML"
    )
    await call.message.answer("Главное меню:", reply_markup=trainer_menu())


# ═══════════════════════════════════════════════════════════
#  CLIENTS LIST
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "👥 Мои клиенты")
async def trainer_clients(message: Message):
    t = await db.get_trainer(message.from_user.id)
    if not t:
        return
    clients = await db.get_clients_by_trainer(message.from_user.id)
    if not clients:
        await message.answer("👥 У вас пока нет клиентов.")
        return
    lines = [f"👥 <b>Ваши клиенты ({len(clients)}):</b>\n"]
    for i, c in enumerate(clients, 1):
        lines.append(
            f"<b>{i}. {c['full_name']}</b>\n"
            f"   📞 {c['phone']}\n"
            f"   🎯 {c['goals'] or '—'}\n"
            f"   🩹 {c['injuries'] or 'нет травм'}\n"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════
#  BOOKING REQUESTS
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "⏳ Запросы на запись")
async def trainer_requests(message: Message):
    t = await db.get_trainer(message.from_user.id)
    if not t:
        return
    pending = await db.get_pending_bookings_for_trainer(message.from_user.id)
    if not pending:
        await message.answer("✅ Нет новых запросов.")
        return
    for b in pending:
        note_line = f"\n📝 <b>Заметка:</b> {b['note']}" if b["note"] else ""
        await message.answer(
            f"🆕 <b>Запрос на запись</b>\n\n"
            f"👤 <b>{b['client_name']}</b>\n"
            f"📅 {b['slot_date']}  🕐 {b['slot_time']}"
            f"{note_line}",
            parse_mode="HTML",
            reply_markup=confirm_booking_kb(b["id"])
        )


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_booking(call: CallbackQuery, bot: Bot):
    booking_id = int(call.data.split("_")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена.", show_alert=True)
        return
    await db.update_booking_status(booking_id, "confirmed")
    await call.message.edit_text(
        f"✅ Запись <b>подтверждена</b>\n"
        f"👤 {booking['client_name']}  📅 {booking['slot_date']}  🕐 {booking['slot_time']}",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            booking["client_chat_id"],
            f"✅ <b>Ваша запись подтверждена!</b>\n\n"
            f"📅 <b>{booking['slot_date']}</b>  🕐 <b>{booking['slot_time']}</b>\n\n"
            f"Ждём вас! 💪",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Cannot notify client: {e}")
    await call.answer()


@router.callback_query(F.data.startswith("reject_"))
async def reject_booking(call: CallbackQuery, bot: Bot):
    booking_id = int(call.data.split("_")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена.", show_alert=True)
        return
    await db.update_booking_status(booking_id, "rejected")
    await call.message.edit_text(
        f"❌ Запрос <b>отклонён</b>\n"
        f"👤 {booking['client_name']}  📅 {booking['slot_date']}  🕐 {booking['slot_time']}",
        parse_mode="HTML"
    )
    try:
        await bot.send_message(
            booking["client_chat_id"],
            f"❌ <b>Запрос отклонён тренером.</b>\n\n"
            f"📅 {booking['slot_date']}  🕐 {booking['slot_time']}\n\n"
            f"Попробуйте выбрать другое время.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Cannot notify client: {e}")
    await call.answer()
