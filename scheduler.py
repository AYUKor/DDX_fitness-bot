import os
import logging
from datetime import date, datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import database as db

TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
logger = logging.getLogger(__name__)


async def send_morning_reminders(bot):
    """7:00 AM — send schedule to each trainer, remind each client."""
    today = date.today().strftime("%Y-%m-%d")
    trainers = await db.get_all_trainers()

    for trainer in trainers:
        tid = trainer["chat_id"]
        bookings = await db.get_bookings_for_date(tid, today)

        if not bookings:
            text = (
                f"☀️ <b>Доброе утро, {trainer['full_name'].split()[0]}!</b>\n\n"
                f"📅 На сегодня (<b>{today}</b>) записей нет.\nСвободный день! 🏖"
            )
        else:
            lines = [
                f"☀️ <b>Доброе утро, {trainer['full_name'].split()[0]}!</b>\n",
                f"📋 <b>Расписание на сегодня ({today}):</b>\n"
            ]
            for b in bookings:
                note_line = f"\n   📝 {b['note']}" if b["note"] else ""
                lines.append(
                    f"🕐 <b>{b['slot_time']}</b> — {b['client_name']}"
                    f"\n   📞 {b['client_phone']}"
                    f"{note_line}\n"
                )
            lines.append(f"💪 Всего клиентов: <b>{len(bookings)}</b>")
            text = "\n".join(lines)

        try:
            await bot.send_message(tid, text, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Cannot send morning reminder to trainer {tid}: {e}")

    # Remind clients
    clients = await db.get_all_registered_clients()
    for client in clients:
        booking = await db.get_client_booking_today(client["chat_id"], today)
        if booking:
            try:
                await bot.send_message(
                    client["chat_id"],
                    f"☀️ <b>Доброе утро, {client['full_name'].split()[0]}!</b>\n\n"
                    f"Напоминаем: сегодня у вас тренировка! 💪\n"
                    f"🕐 <b>Время:</b> {booking['slot_time']}\n\n"
                    f"Удачи! 🏋️",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Cannot send reminder to client {client['chat_id']}: {e}")


async def send_onehour_reminders(bot):
    """Every hour — remind clients whose training starts in 1 hour."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    target = (now + timedelta(hours=1)).strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    clients = await db.get_all_registered_clients()
    for client in clients:
        booking = await db.get_client_booking_today(client["chat_id"], today)
        if booking and booking["slot_time"] == target:
            try:
                await bot.send_message(
                    client["chat_id"],
                    f"⏰ <b>Через 1 час тренировка!</b>\n\n"
                    f"🕐 <b>{booking['slot_time']}</b>\n\n"
                    f"Не забудьте воду и форму! 💧",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Cannot send 1h reminder to {client['chat_id']}: {e}")


def setup_scheduler(bot) -> AsyncIOScheduler:
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        send_morning_reminders,
        CronTrigger(hour=7, minute=0, timezone=tz),
        args=[bot],
        id="morning_all",
        replace_existing=True
    )

    scheduler.add_job(
        send_onehour_reminders,
        CronTrigger(minute=0, timezone=tz),
        args=[bot],
        id="onehour_reminder",
        replace_existing=True
    )

    return scheduler
