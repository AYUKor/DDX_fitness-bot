from aiogram.fsm.state import State, StatesGroup


class TrainerRegistration(StatesGroup):
    secret       = State()
    full_name    = State()
    phone        = State()
    email        = State()
    specialization = State()


class ClientRegistration(StatesGroup):
    choose_trainer = State()
    full_name      = State()
    phone          = State()
    email          = State()
    injuries       = State()
    goals          = State()


class AddSlots(StatesGroup):
    select_day   = State()
    select_times = State()


class BookingFlow(StatesGroup):
    select_day  = State()
    select_slot = State()
    add_note    = State()


class EditProfile(StatesGroup):
    choose_field = State()
    enter_value  = State()
