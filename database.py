import aiosqlite

DB_PATH = "fitness_bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS trainers (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER UNIQUE NOT NULL,
                full_name TEXT,
                phone TEXT,
                email TEXT,
                specialization TEXT,
                registered INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY,
                chat_id INTEGER UNIQUE NOT NULL,
                trainer_chat_id INTEGER,
                full_name TEXT,
                phone TEXT,
                email TEXT,
                injuries TEXT,
                goals TEXT,
                registered INTEGER DEFAULT 0,
                FOREIGN KEY (trainer_chat_id) REFERENCES trainers(chat_id)
            );

            CREATE TABLE IF NOT EXISTS slots (
                id INTEGER PRIMARY KEY,
                trainer_chat_id INTEGER NOT NULL,
                slot_date TEXT NOT NULL,
                slot_time TEXT NOT NULL,
                is_available INTEGER DEFAULT 1,
                UNIQUE(trainer_chat_id, slot_date, slot_time)
            );

            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY,
                client_chat_id INTEGER NOT NULL,
                trainer_chat_id INTEGER NOT NULL,
                slot_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (slot_id) REFERENCES slots(id)
            );
        """)
        await db.commit()


# ═══════════════════════════════════════════════════════════
#  TRAINERS
# ═══════════════════════════════════════════════════════════

async def get_trainer(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM trainers WHERE chat_id=?", (chat_id,)) as cur:
            return await cur.fetchone()


async def get_all_trainers():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM trainers WHERE registered=1") as cur:
            return await cur.fetchall()


async def upsert_trainer(chat_id: int, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        updates = ", ".join(f"{k}=?" for k in kwargs)
        values = list(kwargs.values())
        await db.execute(
            f"INSERT INTO trainers (chat_id, {fields}) VALUES (?, {placeholders}) "
            f"ON CONFLICT(chat_id) DO UPDATE SET {updates}",
            [chat_id] + values + values
        )
        await db.commit()


# ═══════════════════════════════════════════════════════════
#  CLIENTS
# ═══════════════════════════════════════════════════════════

async def get_client(chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clients WHERE chat_id=?", (chat_id,)) as cur:
            return await cur.fetchone()


async def upsert_client(chat_id: int, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ", ".join(kwargs.keys())
        placeholders = ", ".join("?" for _ in kwargs)
        updates = ", ".join(f"{k}=?" for k in kwargs)
        values = list(kwargs.values())
        await db.execute(
            f"INSERT INTO clients (chat_id, {fields}) VALUES (?, {placeholders}) "
            f"ON CONFLICT(chat_id) DO UPDATE SET {updates}",
            [chat_id] + values + values
        )
        await db.commit()


async def get_clients_by_trainer(trainer_chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM clients WHERE trainer_chat_id=? AND registered=1",
            (trainer_chat_id,)
        ) as cur:
            return await cur.fetchall()


async def get_all_registered_clients():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clients WHERE registered=1") as cur:
            return await cur.fetchall()


# ═══════════════════════════════════════════════════════════
#  SLOTS
# ═══════════════════════════════════════════════════════════

async def add_slot(trainer_chat_id: int, slot_date: str, slot_time: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO slots (trainer_chat_id, slot_date, slot_time) VALUES (?,?,?)",
                (trainer_chat_id, slot_date, slot_time)
            )
            await db.commit()
            return True
        except Exception:
            return False


async def get_available_slots(trainer_chat_id: int, slot_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM slots WHERE trainer_chat_id=? AND slot_date=? AND is_available=1 ORDER BY slot_time",
            (trainer_chat_id, slot_date)
        ) as cur:
            return await cur.fetchall()


async def get_slots_for_week(trainer_chat_id: int, dates: list):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ",".join("?" for _ in dates)
        async with db.execute(
            f"SELECT * FROM slots WHERE trainer_chat_id=? AND slot_date IN ({placeholders}) ORDER BY slot_date, slot_time",
            [trainer_chat_id] + dates
        ) as cur:
            return await cur.fetchall()


async def delete_slot(slot_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM slots WHERE id=?", (slot_id,))
        await db.commit()


# ═══════════════════════════════════════════════════════════
#  BOOKINGS
# ═══════════════════════════════════════════════════════════

async def create_booking(client_chat_id: int, trainer_chat_id: int, slot_id: int, note: str = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO bookings (client_chat_id, trainer_chat_id, slot_id, note) VALUES (?,?,?,?)",
            (client_chat_id, trainer_chat_id, slot_id, note)
        )
        await db.commit()
        return cur.lastrowid


async def get_booking(booking_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.slot_date, s.slot_time,
                      c.full_name  AS client_name,
                      c.phone      AS client_phone,
                      c.chat_id    AS client_chat_id
               FROM bookings b
               JOIN slots   s ON b.slot_id      = s.id
               JOIN clients c ON b.client_chat_id = c.chat_id
               WHERE b.id=?""",
            (booking_id,)
        ) as cur:
            return await cur.fetchone()


async def update_booking_status(booking_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE bookings SET status=? WHERE id=?", (status, booking_id))
        if status == "confirmed":
            async with db.execute("SELECT slot_id FROM bookings WHERE id=?", (booking_id,)) as cur:
                row = await cur.fetchone()
                if row:
                    await db.execute("UPDATE slots SET is_available=0 WHERE id=?", (row[0],))
        elif status in ("cancelled", "rejected"):
            async with db.execute("SELECT slot_id FROM bookings WHERE id=?", (booking_id,)) as cur:
                row = await cur.fetchone()
                if row:
                    await db.execute("UPDATE slots SET is_available=1 WHERE id=?", (row[0],))
        await db.commit()


async def get_bookings_for_date(trainer_chat_id: int, slot_date: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.slot_date, s.slot_time,
                      c.full_name AS client_name,
                      c.phone    AS client_phone
               FROM bookings b
               JOIN slots   s ON b.slot_id        = s.id
               JOIN clients c ON b.client_chat_id = c.chat_id
               WHERE b.trainer_chat_id=? AND s.slot_date=? AND b.status='confirmed'
               ORDER BY s.slot_time""",
            (trainer_chat_id, slot_date)
        ) as cur:
            return await cur.fetchall()


async def get_client_booking_today(client_chat_id: int, today: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.slot_date, s.slot_time
               FROM bookings b
               JOIN slots s ON b.slot_id = s.id
               WHERE b.client_chat_id=? AND s.slot_date=? AND b.status='confirmed'""",
            (client_chat_id, today)
        ) as cur:
            return await cur.fetchone()


async def get_client_upcoming_bookings(client_chat_id: int, today: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.slot_date, s.slot_time
               FROM bookings b
               JOIN slots s ON b.slot_id = s.id
               WHERE b.client_chat_id=? AND s.slot_date>=?
                 AND b.status IN ('confirmed','pending')
               ORDER BY s.slot_date, s.slot_time""",
            (client_chat_id, today)
        ) as cur:
            return await cur.fetchall()


async def get_pending_bookings_for_trainer(trainer_chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT b.*, s.slot_date, s.slot_time,
                      c.full_name AS client_name
               FROM bookings b
               JOIN slots   s ON b.slot_id        = s.id
               JOIN clients c ON b.client_chat_id = c.chat_id
               WHERE b.trainer_chat_id=? AND b.status='pending'
               ORDER BY s.slot_date, s.slot_time""",
            (trainer_chat_id,)
        ) as cur:
            return await cur.fetchall()
