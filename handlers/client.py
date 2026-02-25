import logging
from datetime import date
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import database as db
from keyboards import (
    client_menu, trainers_keyboard, booking_days_kb,
    available_slots_kb, cancel_booking_kb, confirm_cancel_kb,
    client_edit_fields_kb, trainer_menu
)
from states import ClientRegistration, BookingFlow, EditProfile

router = Router()
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
#  REGISTRATION
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "role_client")
async def client_role(call: CallbackQuery, state: FSMContext):
    existing = await db.get_client(call.from_user.id)
    if existing and existing["registered"]:
        await call.message.edit_text("✅ Вы уже зарегистрированы!")
        await call.message.answer("Главное меню:", reply_markup=client_menu())
        return
    # Choose trainer
    trainers = await db.get_all_trainers()
    if not trainers:
        await call.message.edit_text(
            "⚠️ Пока ни один тренер не зарегистрирован в боте.\n"
            "Попробуйте позже или обратитесь к администратору."
        )
        return
    await call.message.edit_text(
        "👋 Добро пожаловать!\n\n"
        "Для начала выберите <b>вашего тренера</b>:",
        parse_mode="HTML",
        reply_markup=trainers_keyboard(trainers)
    )
    await state.set_state(ClientRegistration.choose_trainer)


@router.callback_query(F.data.startswith("picktrainer_"), ClientRegistration.choose_trainer)
async def client_pick_trainer(call: CallbackQuery, state: FSMContext):
    trainer_id = int(call.data.split("_")[1])
    await state.update_data(trainer_chat_id=trainer_id)
    await call.message.edit_text("Введите ваше <b>ФИО</b>:", parse_mode="HTML")
    await state.set_state(ClientRegistration.full_name)


@router.message(ClientRegistration.full_name)
async def client_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text.strip())
    await message.answer("📞 Ваш <b>номер телефона</b>:", parse_mode="HTML")
    await state.set_state(ClientRegistration.phone)


@router.message(ClientRegistration.phone)
async def client_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("📧 Ваш <b>email</b> (или «нет»):", parse_mode="HTML")
    await state.set_state(ClientRegistration.email)


@router.message(ClientRegistration.email)
async def client_email(message: Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await message.answer(
        "🩹 <b>Травмы или ограничения по здоровью</b>?\n(или «нет»)",
        parse_mode="HTML"
    )
    await state.set_state(ClientRegistration.injuries)


@router.message(ClientRegistration.injuries)
async def client_injuries(message: Message, state: FSMContext):
    val = message.text.strip()
    await state.update_data(injuries=None if val.lower() in ("нет", "no", "-") else val)
    await message.answer(
        "🎯 Ваша <b>цель тренировок</b>?\n(похудение, набор массы, выносливость…)",
        parse_mode="HTML"
    )
    await state.set_state(ClientRegistration.goals)


@router.message(ClientRegistration.goals)
async def client_goals(message: Message, state: FSMContext):
    data = await state.get_data()
    client_data = {
        "trainer_chat_id": data.get("trainer_chat_id"),
        "full_name": data.get("full_name"),
        "phone": data.get("phone"),
        "email": data.get("email"),
        "injuries": data.get("injuries"),
        "goals": message.text.strip(),
        "registered": 1
    }
    await db.upsert_client(message.from_user.id, **client_data)
    await state.clear()
    # Получаем имя тренера для красивого ответа
    trainer = await db.get_trainer(client_data["trainer_chat_id"])
    trainer_name = trainer["full_name"] if trainer else "—"
    await message.answer(
        f"✅ <b>Профиль сохранён!</b>\n\n"
        f"👤 {client_data['full_name']}\n"
        f"📞 {client_data['phone']}\n"
        f"📧 {client_data['email']}\n"
        f"🩹 Травмы: {client_data.get('injuries') or 'нет'}\n"
        f"🎯 Цель: {client_data['goals']}\n\n"
        f"🏋️ Ваш тренер: <b>{trainer_name}</b>",
        parse_mode="HTML",
        reply_markup=client_menu()
    )


# ═══════════════════════════════════════════════════════════
#  PROFILE & EDIT
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "👤 Мой профиль")
async def client_profile(message: Message):
    c = await db.get_client(message.from_user.id)
    if not c or not c["registered"]:
        await message.answer("Профиль не найден. Напишите /start")
        return
    trainer = await db.get_trainer(c["trainer_chat_id"]) if c["trainer_chat_id"] else None
    trainer_name = trainer["full_name"] if trainer else "не выбран"
    await message.answer(
        f"👤 <b>Ваш профиль</b>\n\n"
        f"<b>ФИО:</b> {c['full_name']}\n"
        f"<b>Телефон:</b> {c['phone']}\n"
        f"<b>Email:</b> {c['email']}\n"
        f"<b>Травмы:</b> {c['injuries'] or 'нет'}\n"
        f"<b>Цель:</b> {c['goals']}\n\n"
        f"🏋️ <b>Тренер:</b> {trainer_name}",
        parse_mode="HTML"
    )


@router.message(F.text == "✏️ Редактировать профиль")
async def client_edit_start(message: Message, state: FSMContext):
    c = await db.get_client(message.from_user.id)
    if not c:
        return
    await message.answer("✏️ <b>Что изменить?</b>", parse_mode="HTML",
                         reply_markup=client_edit_fields_kb())
    await state.set_state(EditProfile.choose_field)


@router.callback_query(F.data.startswith("editfield_"), EditProfile.choose_field)
async def client_edit_field(call: CallbackQuery, state: FSMContext):
    field = call.data.split("_", 1)[1]
    if field == "cancel":
        await call.message.edit_text("Редактирование отменено.")
        await state.clear()
        return
    labels = {
        "full_name": "ФИО",
        "phone": "номер телефона",
        "email": "email",
        "injuries": "травмы и ограничения",
        "goals": "цели тренировок"
    }
    await state.update_data(edit_field=field)
    await call.message.edit_text(f"Введите новое значение для «{labels.get(field, field)}»:")
    await state.set_state(EditProfile.enter_value)


@router.message(EditProfile.enter_value)
async def client_save_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data["edit_field"]
    # Determine if trainer or client
    t = await db.get_trainer(message.from_user.id)
    if t:
        await db.upsert_trainer(message.from_user.id, **{field: message.text.strip()})
        await message.answer("✅ Данные обновлены!", reply_markup=trainer_menu())
    else:
        await db.upsert_client(message.from_user.id, **{field: message.text.strip()})
        await message.answer("✅ Данные обновлены!", reply_markup=client_menu())
    await state.clear()


# ═══════════════════════════════════════════════════════════
#  BOOKING FLOW
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "📝 Записаться на тренировку")
async def book_start(message: Message, state: FSMContext):
    c = await db.get_client(message.from_user.id)
    if not c or not c["registered"]:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    await state.set_state(BookingFlow.select_day)
    await state.update_data(book_offset=0, trainer_id=c["trainer_chat_id"])
    await message.answer("📅 <b>Выберите день:</b>", parse_mode="HTML",
                         reply_markup=booking_days_kb(0))


@router.callback_query(F.data.startswith("bookweek_"), BookingFlow.select_day)
async def bookweek_nav(call: CallbackQuery, state: FSMContext):
    offset = int(call.data.split("_")[1])
    await state.update_data(book_offset=offset)
    await call.message.edit_reply_markup(reply_markup=booking_days_kb(offset))
    await call.answer()


@router.callback_query(F.data.startswith("bookday_"), BookingFlow.select_day)
async def book_day(call: CallbackQuery, state: FSMContext):
    day = call.data.split("_", 1)[1]
    data = await state.get_data()
    slots = await db.get_available_slots(data["trainer_id"], day)
    if not slots:
        await call.answer("На этот день нет свободных слотов.", show_alert=True)
        return
    await state.update_data(selected_day=day)
    await state.set_state(BookingFlow.select_slot)
    await call.message.edit_text(
        f"🕐 <b>Свободные слоты на {day}:</b>",
        parse_mode="HTML",
        reply_markup=available_slots_kb(slots)
    )


@router.callback_query(F.data == "book_back", BookingFlow.select_slot)
async def book_back(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.set_state(BookingFlow.select_day)
    await call.message.edit_text("📅 <b>Выберите день:</b>", parse_mode="HTML",
                                  reply_markup=booking_days_kb(data.get("book_offset", 0)))


@router.callback_query(F.data.startswith("bookslot_"), BookingFlow.select_slot)
async def book_slot(call: CallbackQuery, state: FSMContext):
    slot_id = int(call.data.split("_")[1])
    await state.update_data(selected_slot_id=slot_id)
    await state.set_state(BookingFlow.add_note)
    await call.message.edit_text(
        "📝 <b>Заметка тренеру</b> (необязательно)\n\n"
        "Напишите что-нибудь или отправьте «-» чтобы пропустить.\n\n"
        "<i>Например: «планирую работать над ногами» или «болит плечо»</i>",
        parse_mode="HTML"
    )


@router.message(BookingFlow.add_note)
async def book_note(message: Message, state: FSMContext, bot: Bot):
    note = message.text.strip()
    if note == "-":
        note = None
    data = await state.get_data()
    slot_id = data["selected_slot_id"]
    day = data["selected_day"]
    trainer_id = data["trainer_id"]

    # Verify slot still available
    slots = await db.get_available_slots(trainer_id, day)
    slot = next((s for s in slots if s["id"] == slot_id), None)
    if not slot:
        await message.answer("❌ Этот слот уже занят. Выберите другое время.",
                             reply_markup=client_menu())
        await state.clear()
        return

    booking_id = await db.create_booking(message.from_user.id, trainer_id, slot_id, note)
    client = await db.get_client(message.from_user.id)
    await state.clear()

    await message.answer(
        f"✅ <b>Запрос отправлен тренеру!</b>\n\n"
        f"📅 <b>{day}</b>  🕐 <b>{slot['slot_time']}</b>\n\n"
        f"Ждите подтверждения.",
        parse_mode="HTML",
        reply_markup=client_menu()
    )

    note_line = f"\n📝 <b>Заметка:</b> {note}" if note else ""
    try:
        from keyboards import confirm_booking_kb
        await bot.send_message(
            trainer_id,
            f"🆕 <b>Новый запрос на запись!</b>\n\n"
            f"👤 <b>{client['full_name']}</b>\n"
            f"📞 {client['phone']}\n"
            f"📅 {day}  🕐 {slot['slot_time']}"
            f"{note_line}",
            parse_mode="HTML",
            reply_markup=confirm_booking_kb(booking_id)
        )
    except Exception as e:
        logger.warning(f"Cannot notify trainer: {e}")


# ═══════════════════════════════════════════════════════════
#  MY BOOKINGS
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "🗓 Мои записи")
async def my_bookings(message: Message):
    today = date.today().strftime("%Y-%m-%d")
    bookings = await db.get_client_upcoming_bookings(message.from_user.id, today)
    if not bookings:
        await message.answer("У вас пока нет предстоящих записей.")
        return
    STATUS = {"confirmed": "✅ подтверждено", "pending": "⏳ ожидает"}
    lines = ["🗓 <b>Ваши записи:</b>\n"]
    for b in bookings:
        lines.append(f"📅 <b>{b['slot_date']}</b>  🕐 {b['slot_time']}  —  {STATUS.get(b['status'], b['status'])}")
    await message.answer("\n".join(lines), parse_mode="HTML")


# ═══════════════════════════════════════════════════════════
#  CANCEL BOOKING
# ═══════════════════════════════════════════════════════════

@router.message(F.text == "❌ Отменить запись")
async def cancel_start(message: Message):
    today = date.today().strftime("%Y-%m-%d")
    bookings = await db.get_client_upcoming_bookings(message.from_user.id, today)
    active = [b for b in bookings if b["status"] in ("confirmed", "pending")]
    if not active:
        await message.answer("Нет активных записей для отмены.")
        return
    await message.answer("❌ <b>Выберите запись:</b>", parse_mode="HTML",
                         reply_markup=cancel_booking_kb(active))


@router.callback_query(F.data.startswith("cancelbook_"))
async def cancel_confirm(call: CallbackQuery):
    raw = call.data.split("_")[1]
    if raw == "back":
        await call.message.edit_text("Отмена отменена 😊")
        return
    booking_id = int(raw)
    booking = await db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена.", show_alert=True)
        return
    await call.message.edit_text(
        f"❓ <b>Подтвердите отмену:</b>\n\n📅 {booking['slot_date']}  🕐 {booking['slot_time']}",
        parse_mode="HTML",
        reply_markup=confirm_cancel_kb(booking_id)
    )


@router.callback_query(F.data.startswith("docancelbook_"))
async def do_cancel(call: CallbackQuery, bot: Bot):
    booking_id = int(call.data.split("_")[1])
    booking = await db.get_booking(booking_id)
    if not booking:
        await call.answer("Запись не найдена.", show_alert=True)
        return
    await db.update_booking_status(booking_id, "cancelled")
    await call.message.edit_text(
        f"✅ Запись отменена.\n📅 {booking['slot_date']}  🕐 {booking['slot_time']}",
        parse_mode="HTML"
    )
    try:
        client = await db.get_client(call.from_user.id)
        await bot.send_message(
            booking["trainer_chat_id"],
            f"⚠️ <b>Клиент отменил запись</b>\n\n"
            f"👤 {client['full_name']}\n"
            f"📅 {booking['slot_date']}  🕐 {booking['slot_time']}",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Cannot notify trainer: {e}")
    await call.answer()


@router.callback_query(F.data == "cancelbook_back")
async def cancel_back(call: CallbackQuery):
    await call.message.edit_text("Хорошо, ничего не отменяем 😊")
    await call.answer()
