from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from datetime import date, timedelta

DAYS_SHORT  = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
DAYS_FULL   = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"]
MONTHS_RU   = ["января","февраля","марта","апреля","мая","июня",
                "июля","августа","сентября","октября","ноября","декабря"]

ALL_TIMES = [
    "07:00","08:00","09:00","10:00","11:00","12:00","13:00",
    "14:00","15:00","16:00","17:00","18:00","19:00","20:00","21:00"
]


def fmt_date(d: date) -> str:
    return f"{d.day} {MONTHS_RU[d.month-1]} ({DAYS_SHORT[d.weekday()]})"


def get_week_dates(offset: int = 0):
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7  # 0 if today is Monday
    start = today + timedelta(days=days_ahead + offset * 7)
    return [start + timedelta(days=i) for i in range(7)]


# ─── START ──────────────────────────────────────────────────────────────────

def role_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏋️ Я тренер",  callback_data="role_trainer")
    b.button(text="👤 Я клиент",  callback_data="role_client")
    b.adjust(2)
    return b.as_markup()


# ─── MAIN MENUS ─────────────────────────────────────────────────────────────

def trainer_menu() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.button(text="📅 Моё расписание")
    b.button(text="➕ Добавить слоты")
    b.button(text="👥 Мои клиенты")
    b.button(text="⏳ Запросы на запись")
    b.button(text="👤 Мой профиль")
    b.button(text="✏️ Редактировать профиль")
    b.adjust(2, 2, 2)
    return b.as_markup(resize_keyboard=True)


def client_menu() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.button(text="📝 Записаться на тренировку")
    b.button(text="🗓 Мои записи")
    b.button(text="❌ Отменить запись")
    b.button(text="👤 Мой профиль")
    b.button(text="✏️ Редактировать профиль")
    b.adjust(1, 2, 2)
    return b.as_markup(resize_keyboard=True)


# ─── TRAINER SELECTION ──────────────────────────────────────────────────────

def trainers_keyboard(trainers: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in trainers:
        spec = f" · {t['specialization']}" if t['specialization'] else ""
        b.button(text=f"🏋️ {t['full_name']}{spec}", callback_data=f"picktrainer_{t['chat_id']}")
    b.adjust(1)
    return b.as_markup()


# ─── WEEK NAV ────────────────────────────────────────────────────────────────

def week_nav_kb(offset: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if offset > 0:
        b.button(text="◀️ Пред. неделя", callback_data=f"week_{offset-1}")
    b.button(text="▶️ След. неделя", callback_data=f"week_{offset+1}")
    b.adjust(2)
    return b.as_markup()


# ─── SLOT MANAGEMENT ─────────────────────────────────────────────────────────

def days_kb(offset: int = 0) -> InlineKeyboardMarkup:
    dates = get_week_dates(offset)
    b = InlineKeyboardBuilder()
    for d in dates:
        b.button(text=fmt_date(d), callback_data=f"slotday_{d.strftime('%Y-%m-%d')}")
    if offset > 0:
        b.button(text="◀️ Назад", callback_data=f"slotnav_{offset-1}")
    b.button(text="▶️ Вперёд", callback_data=f"slotnav_{offset+1}")
    b.adjust(2)
    return b.as_markup()


def times_kb(selected: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in ALL_TIMES:
        label = f"✅ {t}" if t in selected else t
        b.button(text=label, callback_data=f"addtime_{t}")
    b.button(text="💾 Сохранить", callback_data="times_done")
    b.adjust(3, 3, 3, 3, 3, 1)
    return b.as_markup()


# ─── BOOKING ─────────────────────────────────────────────────────────────────

def booking_days_kb(offset: int = 0) -> InlineKeyboardMarkup:
    dates = get_week_dates(offset)
    today = date.today()
    b = InlineKeyboardBuilder()
    for d in dates:
        if d >= today:
            b.button(text=fmt_date(d), callback_data=f"bookday_{d.strftime('%Y-%m-%d')}")
    if offset > 0:
        b.button(text="◀️ Пред. неделя", callback_data=f"bookweek_{offset-1}")
    b.button(text="▶️ След. неделя", callback_data=f"bookweek_{offset+1}")
    b.adjust(2)
    return b.as_markup()


def available_slots_kb(slots: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in slots:
        b.button(text=f"🕐 {s['slot_time']}", callback_data=f"bookslot_{s['id']}")
    b.button(text="🔙 Назад", callback_data="book_back")
    b.adjust(3)
    return b.as_markup()


def confirm_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=f"confirm_{booking_id}")
    b.button(text="❌ Отклонить",   callback_data=f"reject_{booking_id}")
    b.adjust(2)
    return b.as_markup()


def cancel_booking_kb(bookings: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for bk in bookings:
        b.button(
            text=f"{bk['slot_date']}  {bk['slot_time']}",
            callback_data=f"cancelbook_{bk['id']}"
        )
    b.adjust(1)
    return b.as_markup()


def confirm_cancel_kb(booking_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Да, отменить", callback_data=f"docancelbook_{booking_id}")
    b.button(text="🔙 Нет",          callback_data="cancelbook_back")
    b.adjust(2)
    return b.as_markup()


# ─── EDIT PROFILE ────────────────────────────────────────────────────────────

def trainer_edit_fields_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 ФИО",            callback_data="editfield_full_name")
    b.button(text="📞 Телефон",         callback_data="editfield_phone")
    b.button(text="📧 Email",           callback_data="editfield_email")
    b.button(text="🏋️ Специализация",  callback_data="editfield_specialization")
    b.button(text="🔙 Отмена",          callback_data="editfield_cancel")
    b.adjust(2, 2, 1)
    return b.as_markup()


def client_edit_fields_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👤 ФИО",     callback_data="editfield_full_name")
    b.button(text="📞 Телефон", callback_data="editfield_phone")
    b.button(text="📧 Email",   callback_data="editfield_email")
    b.button(text="🩹 Травмы",  callback_data="editfield_injuries")
    b.button(text="🎯 Цели",    callback_data="editfield_goals")
    b.button(text="🔙 Отмена",  callback_data="editfield_cancel")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()
