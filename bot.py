import asyncio
import os
import sqlite3
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise Exception("BOT_TOKEN не задан!")

DB_PATH = "game.db"
TOTAL_QUESTIONS = 5
# ===================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            score INTEGER DEFAULT 0,
            total_answers INTEGER DEFAULT 0,
            correct_answers INTEGER DEFAULT 0,
            streak INTEGER DEFAULT 0,
            last_played TEXT,
            achievements TEXT DEFAULT '',
            coins INTEGER DEFAULT 0,
            theme TEXT DEFAULT 'default',
            badge TEXT DEFAULT 'none'
        )
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row

def create_user(user_id, name):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()

def update_user_stats(user_id, name, correct, total):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    user = get_user(user_id)
    if not user:
        create_user(user_id, name)
        user = get_user(user_id)
    
    streak = user[5] if user[5] else 0
    last_played = user[6]
    
    if last_played == today:
        pass
    elif last_played == yesterday:
        streak += 1
    else:
        streak = 1
    
    coins_multiplier = 1.5 if streak >= 3 else 1.0
    earned_coins = int(correct * coins_multiplier)
    
    cur.execute("""
        UPDATE users SET 
            score = score + ?,
            total_answers = total_answers + ?,
            correct_answers = correct_answers + ?,
            streak = ?,
            last_played = ?,
            coins = coins + ?
        WHERE user_id = ?
    """, (correct, total, correct, streak, today, earned_coins, user_id))
    
    conn.commit()
    conn.close()
    return streak, earned_coins

def buy_item(user_id, item_type, item_value, price):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    user = get_user(user_id)
    if user[8] >= price:
        if item_type == "theme":
            cur.execute("UPDATE users SET coins = coins - ?, theme = ? WHERE user_id = ?", (price, item_value, user_id))
        else:
            cur.execute("UPDATE users SET coins = coins - ?, badge = ? WHERE user_id = ?", (price, item_value, user_id))
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

def add_achievement(user_id, ach):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    user = get_user(user_id)
    if user:
        achs = user[7] if user[7] else ""
        if ach not in achs:
            achs = achs + f"|{ach}" if achs else ach
            cur.execute("UPDATE users SET achievements = ? WHERE user_id = ?", (achs, user_id))
            conn.commit()
            conn.close()
            return True
    conn.close()
    return False

def get_top():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name, score, streak, badge FROM users ORDER BY score DESC LIMIT 5")
    rows = cur.fetchall()
    conn.close()
    return rows

# ==================== РАНГИ И БЕЙДЖИ ====================
def get_rank(score):
    if score >= 500: return "👑 Бог Математики"
    if score >= 250: return "🔥 Гроссмейстер"
    if score >= 100: return "⚡ Мастер"
    if score >= 50: return "💎 Профессионал"
    if score >= 20: return "⚔️ Воин чисел"
    if score >= 5: return "🛡️ Ученик"
    return "🐣 Новичок"

def get_badge_emoji(badge):
    badges = {"star": "⭐", "rocket": "🚀", "skull": "💀", "crown": "👑", "none": ""}
    return badges.get(badge, "")

def get_theme_style(theme):
    # Возвращает (цвет_текста, эмодзи_рамки)
    styles = {
        "default": ("<b>", "</b>"),  # Жирный по умолчанию
        "dark": ("<i><b>", "</b></i>"), # Курсив + жирный
        "neon": ("<u><b>", "</b></u>"), # Подчеркнутый + жирный
        "gold": ("<b>", "</b>"),  # Жирный (золотой цвет через эмодзи)
    }
    return styles.get(theme, ("<b>", "</b>"))

# ==================== ГЕНЕРАТОР ====================
def generate_question(difficulty):
    if difficulty == "easy":
        op = random.choice(['+', '-'])
        if op == '+':
            a, b = random.randint(10, 50), random.randint(10, 50)
            return f"{a} + {b}", a + b
        else:
            a, b = random.randint(20, 99), random.randint(10, 19)
            return f"{a} - {b}", a - b
    elif difficulty == "medium":
        op = random.choice(['+', '-', '*'])
        if op == '+':
            a, b = random.randint(10, 99), random.randint(10, 99)
            return f"{a} + {b}", a + b
        elif op == '-':
            a, b = random.randint(20, 99), random.randint(10, a - 1)
            return f"{a} - {b}", a - b
        else:
            a, b = random.randint(2, 12), random.randint(2, 12)
            return f"{a} × {b}", a * b
    else:
        op = random.choice(['+', '-', '*', '/'])
        if op == '+':
            a, b = random.randint(50, 200), random.randint(50, 200)
            return f"{a} + {b}", a + b
        elif op == '-':
            a, b = random.randint(50, 200), random.randint(20, 50)
            return f"{a} - {b}", a - b
        elif op == '*':
            a, b = random.randint(3, 15), random.randint(3, 15)
            return f"{a} × {b}", a * b
        else:
            b = random.randint(2, 10)
            res = random.randint(2, 10)
            a = b * res
            return f"{a} ÷ {b}", res

# ==================== МЕНЮ ====================
def main_menu(user):
    badge = get_badge_emoji(user[10])
    kb = [
        [InlineKeyboardButton(text="🚀 Начать игру", callback_data="play")],
        [InlineKeyboardButton(text="🏪 Магазин", callback_data="shop")],
        [InlineKeyboardButton(text="🏆 Зал Славы", callback_data="top")],
        [InlineKeyboardButton(text=f"👤 Профиль {badge}", callback_data="profile")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def shop_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎨 Темы (50 монет)", callback_data="shop_themes")],
        [InlineKeyboardButton(text="🏅 Бейджи (100 монет)", callback_data="shop_badges")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
    ])

def themes_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌑 Тёмная (50)", callback_data="buy_theme_dark")],
        [InlineKeyboardButton(text="🌈 Неон (50)", callback_data="buy_theme_neon")],
        [InlineKeyboardButton(text="🥇 Золото (50)", callback_data="buy_theme_gold")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")],
    ])

def badges_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Звезда (100)", callback_data="buy_badge_star")],
        [InlineKeyboardButton(text="🚀 Ракета (100)", callback_data="buy_badge_rocket")],
        [InlineKeyboardButton(text="💀 Череп (100)", callback_data="buy_badge_skull")],
        [InlineKeyboardButton(text="👑 Корона (100)", callback_data="buy_badge_crown")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="shop")],
    ])

def difficulty_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Легко (+, -)", callback_data="diff_easy")],
        [InlineKeyboardButton(text="🟡 Средне (+, -, ×)", callback_data="diff_medium")],
        [InlineKeyboardButton(text="🔴 Хард (+, -, ×, ÷)", callback_data="diff_hard")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
    ])

def profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="🏅 Достижения", callback_data="achs")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
    ])

def cancel_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Прервать игру", callback_data="cancel")]])

# ==================== СТАРТ ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    create_user(message.from_user.id, message.from_user.first_name or "Игрок")
    user = get_user(message.from_user.id)
    rank = get_rank(user[2])
    badge = get_badge_emoji(user[10])
    _, close_tag = get_theme_style(user[9])
    
    text = (
        f"👋 <b>Привет, {user[1]} {badge}!</b>\n\n"
        f"Это <b>Математическая Дуэль</b> — тренажёр скорости и ума.\n"
        f"Твой ранг: <b>{rank}</b>\n\n"
        f"🔥 Стрик: <b>{user[5]} дней</b>\n"
        f"📈 Рекорд: <b>{user[2]} очков</b>\n"
        f"💰 Баланс: <b>{user[8]} монет</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu(user))

# ==================== МЕНЮ И МАГАЗИН ====================
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = get_user(call.from_user.id)
    await call.message.edit_text("Главное меню:", reply_markup=main_menu(user))
    await call.answer()

@dp.callback_query(F.data == "shop")
async def show_shop(call: CallbackQuery):
    user = get_user(call.from_user.id)
    text = f"🏪 <b>Магазин</b>\n\n💰 Твой баланс: <b>{user[8]} монет</b>\n\nВыбери категорию:"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=shop_menu())
    await call.answer()

@dp.callback_query(F.data == "shop_themes")
async def show_themes(call: CallbackQuery):
    await call.message.edit_text("🎨 <b>Темы оформления</b>\n\nВыбери тему:", reply_markup=themes_menu())
    await call.answer()

@dp.callback_query(F.data == "shop_badges")
async def show_badges(call: CallbackQuery):
    await call.message.edit_text("🏅 <b>Бейджи</b>\n\nВыбери бейдж:", reply_markup=badges_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("buy_theme_"))
async def buy_theme(call: CallbackQuery):
    theme = call.data.replace("buy_theme_", "")
    if buy_item(call.from_user.id, "theme", theme, 50):
        await call.answer("✅ Тема куплена и надета!", show_alert=True)
    else:
        await call.answer("❌ Недостаточно монет!", show_alert=True)
    user = get_user(call.from_user.id)
    await call.message.edit_text("Главное меню:", reply_markup=main_menu(user))

@dp.callback_query(F.data.startswith("buy_badge_"))
async def buy_badge(call: CallbackQuery):
    badge = call.data.replace("buy_badge_", "")
    if buy_item(call.from_user.id, "badge", badge, 100):
        await call.answer("✅ Бейдж куплен и надет!", show_alert=True)
    else:
        await call.answer("❌ Недостаточно монет!", show_alert=True)
    user = get_user(call.from_user.id)
    await call.message.edit_text("Главное меню:", reply_markup=main_menu(user))

# ==================== ПРОФИЛЬ ====================
@dp.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery):
    user = get_user(call.from_user.id)
    rank = get_rank(user[2])
    badge = get_badge_emoji(user[10])
    text = (
        f"👤 <b>Профиль {user[1]} {badge}</b>\n\n"
        f"Ранг: <b>{rank}</b>\n"
        f"🔥 Стрик: <b>{user[5]} дней</b>\n"
        f"📈 Очки: <b>{user[2]}</b>\n"
        f"💰 Монеты: <b>{user[8]}</b>\n\n"
        f"Выбери, что хочешь посмотреть:"
    )
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=profile_menu())
    await call.answer()

@dp.callback_query(F.data == "stats")
async def show_stats(call: CallbackQuery):
    user = get_user(call.from_user.id)
    total = user[3] if user[3] else 0
    correct = user[4] if user[4] else 0
    accuracy = round((correct / total * 100), 1) if total > 0 else 0
    text = (
        f"📊 <b>Статистика {user[1]}</b>\n\n"
        f"🎯 Точность: <b>{accuracy}%</b>\n"
        f"✅ Правильных: <b>{correct}</b>\n"
        f"❌ Ошибок: <b>{total - correct}</b>\n"
        f"📈 Всего ответов: <b>{total}</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "achs")
async def show_achs(call: CallbackQuery):
    user = get_user(call.from_user.id)
    achs = user[7].split("|") if user[7] else ["Пока нет достижений"]
    text = "🏅 <b>Твои достижения:</b>\n\n"
    for a in achs:
        text += f"🔸 {a}\n"
    text += "\n<i>Продолжай играть, чтобы открыть новые!</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]])
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "top")
async def show_top(call: CallbackQuery):
    top = get_top()
    user = get_user(call.from_user.id)
    if not top:
        await call.message.edit_text("Пока никто не играл. Будь первым! 🚀", reply_markup=main_menu(user))
        return
    text = "🏆 <b>Зал Славы (Топ-5):</b>\n\n"
    for i, (name, score, streak, badge) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
        b_emoji = get_badge_emoji(badge)
        text += f"{medal} {i}. {name} {b_emoji} — <b>{score}</b> очков (🔥{streak})\n"
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu(user))
    await call.answer()

# ==================== ИГРА ====================
@dp.callback_query(F.data == "play")
async def choose_difficulty(call: CallbackQuery):
    await call.message.edit_text("Выбери уровень сложности:", reply_markup=difficulty_menu())
    await call.answer()

@dp.callback_query(F.data.startswith("diff_"))
async def start_game(call: CallbackQuery, state: FSMContext):
    difficulty = call.data.replace("diff_", "")
    await state.clear()
    await state.update_data(difficulty=difficulty, current_round=1, correct_answers=0, timer_task=None)
    await call.message.edit_text("🔥 Поехали! Приготовься...", reply_markup=cancel_menu())
    await asyncio.sleep(1)
    await next_question(call.message, state)

async def next_question(message: Message, state: FSMContext):
    data = await state.get_data()
    current_round = data.get("current_round", 1)
    difficulty = data.get("difficulty", "easy")
    if current_round > TOTAL_QUESTIONS:
        await finish_game(message, state)
        return
    old_task = data.get("timer_task")
    if old_task: old_task.cancel()
    
    question_text, answer = generate_question(difficulty)
    await state.update_data(answer=answer)
    
    # Красивый прогресс-бар
    progress = "🟩" * current_round + "⬜" * (TOTAL_QUESTIONS - current_round)
    
    await message.edit_text(
        f"<b>┏━━━━━━━━━━━━━━━┓</b>\n"
        f"<b>  ВОПРОС {current_round}/{TOTAL_QUESTIONS}</b>\n"
        f"<b>┗━━━━━━━━━━━━━━━┛</b>\n\n"
        f"{progress}\n\n"
        f"❓ <code>{question_text} = ?</code>\n\n"
        f"⏱ <i>У тебя 15 секунд!</i>",
        parse_mode="HTML", reply_markup=cancel_menu()
    )
    await state.set_state(GameStates.waiting_answer)
    task = asyncio.create_task(timeout_task(message, state, current_round))
    await state.update_data(timer_task=task)

async def timeout_task(message: Message, state: FSMContext, round_num: int):
    await asyncio.sleep(15)
    current_state = await state.get_state()
    if current_state == GameStates.waiting_answer:
        data = await state.get_data()
        if data.get("current_round") == round_num:
            correct = data.get("answer")
            await message.answer(f"⏰ <b>Время вышло!</b>\nПравильный ответ: <b>{correct}</b>", parse_mode="HTML")
            await asyncio.sleep(2)
            await state.update_data(current_round=round_num + 1)
            await next_question(message, state)

@dp.message(GameStates.waiting_answer)
async def check_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    correct = data.get("answer")
    current_round = data.get("current_round", 1)
    correct_answers = data.get("correct_answers", 0)
    old_task = data.get("timer_task")
    if old_task: old_task.cancel()
    try:
        user_answer = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Введи <b>число</b>!", parse_mode="HTML")
        task = asyncio.create_task(timeout_task(message, state, current_round))
        await state.update_data(timer_task=task)
        return
    if user_answer == correct:
        correct_answers += 1
        await message.answer(f"✅ <b>Верно!</b>", parse_mode="HTML")
    else:
        await message.answer(f"❌ <b>Ошибка.</b> Ответ: <b>{correct}</b>", parse_mode="HTML")
    try: await message.delete()
    except: pass
    await state.update_data(correct_answers=correct_answers, current_round=current_round + 1)
    await asyncio.sleep(1.5)
    await next_question(message, state)

async def finish_game(message: Message, state: FSMContext):
    data = await state.get_data()
    correct_answers = data.get("correct_answers", 0)
    user_id = message.chat.id
    name = message.chat.first_name or "Игрок"
    streak, earned_coins = update_user_stats(user_id, name, correct_answers, TOTAL_QUESTIONS)
    
    new_ach = []
    if correct_answers == TOTAL_QUESTIONS:
        if add_achievement(user_id, "🏆 Идеальный раунд"): new_ach.append("🏆 Идеальный раунд")
    if streak >= 3:
        if add_achievement(user_id, "🔥 В ударе (3 дня)"): new_ach.append("🔥 В ударе (3 дня)")
    
    user = get_user(user_id)
    if user[2] >= 100:
        if add_achievement(user_id, "💯 100 очков"): new_ach.append("💯 100 очков")
    if user[2] >= 500:
        if add_achievement(user_id, "👑 Бог Математики"): new_ach.append("👑 Бог Математики")

    await state.clear()
    rank = get_rank(user[2])
    badge = get_badge_emoji(user[10])
    
    if correct_answers == TOTAL_QUESTIONS: emoji, title = "🏆", "ИДЕАЛЬНО!"
    elif correct_answers >= 3: emoji, title = "🔥", "ОТЛИЧНО!"
    elif correct_answers >= 2: emoji, title = "👍", "ХОРОШО!"
    else: emoji, title = "💪", "ЕСТЬ КУДА РАСТИ"
    
    text = (
        f"<b>┏━━━━━━━━━━━━━━━┓</b>\n"
        f"<b>  {emoji} {title}</b>\n"
        f"<b>┗━━━━━━━━━━━━━━━┛</b>\n\n"
        f"Правильных: <b>{correct_answers} из {TOTAL_QUESTIONS}</b>\n"
        f"💰 Заработано: <b>+{earned_coins} монет</b>\n\n"
        f"🔥 Стрик: <b>{streak} дней</b>\n"
        f"📈 Рекорд: <b>{user[2]}</b> | Ранг: <b>{rank} {badge}</b>"
    )
    if new_ach:
        text += "\n\n🏅 <b>Новые достижения:</b>\n"
        for a in new_ach: text += f"🔸 {a}\n"
            
    await message.edit_text(text, parse_mode="HTML", reply_markup=main_menu(user))

@dp.callback_query(F.data == "cancel")
async def cancel_game(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    old_task = data.get("timer_task")
    if old_task: old_task.cancel()
    await state.clear()
    await call.message.edit_text("🛑 Игра прервана.", reply_markup=main_menu(get_user(call.from_user.id)))
    await call.answer()

# ==================== ЗАПУСК ====================
async def main():
    init_db()
    print("МЕГА-БОТ ЗАПУЩЕН...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
