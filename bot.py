import asyncio
import os
import sqlite3
import random
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
            score INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def add_score(user_id, name, points):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)", (user_id, name))
    cur.execute("UPDATE users SET score = score + ? WHERE user_id = ?", (points, user_id))
    conn.commit()
    conn.close()

def get_top():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 5")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_score(user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT score FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0

# ==================== СОСТОЯНИЯ ====================
class GameStates(StatesGroup):
    waiting_answer = State()

# ==================== ГЕНЕРАТОР ВОПРОСОВ ====================
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
    else: # hard
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

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Начать игру", callback_data="play")],
        [InlineKeyboardButton(text="🏆 Топ-5 игроков", callback_data="top")],
        [InlineKeyboardButton(text="📊 Мои очки", callback_data="my_score")],
    ])

def difficulty_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Легко (+, -)", callback_data="diff_easy")],
        [InlineKeyboardButton(text="🟡 Средне (+, -, ×)", callback_data="diff_medium")],
        [InlineKeyboardButton(text="🔴 Хард (+, -, ×, ÷)", callback_data="diff_hard")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")],
    ])

def cancel_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Прервать игру", callback_data="cancel")],
    ])

# ==================== СТАРТ ====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    name = message.from_user.first_name or "Игрок"
    text = (
        f"👋 <b>Привет, {name}!</b>\n\n"
        f"Это <b>Математическая Дуэль</b> — тренажёр скорости и ума.\n"
        f"В одной игре {TOTAL_QUESTIONS} вопросов, на каждый даётся <b>15 секунд</b>.\n"
        f"За правильный ответ — <b>+1 очко</b>. За ошибку или просрочку — <b>0 очков</b>, но игра продолжается.\n\n"
        f"📈 Твой текущий рекорд: <b>{get_score(message.from_user.id)} очков</b>."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())

# ==================== МЕНЮ ====================
@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Главное меню:", reply_markup=main_menu())
    await call.answer()

@dp.callback_query(F.data == "top")
async def show_top(call: CallbackQuery):
    top = get_top()
    if not top:
        await call.message.edit_text("Пока никто не играл. Будь первым! 🚀", reply_markup=main_menu())
        return
    
    text = "🏆 <b>Топ-5 игроков:</b>\n\n"
    for i, (name, score) in enumerate(top, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
        text += f"{medal} {i}. {name} — <b>{score}</b> очков\n"
    
    await call.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())
    await call.answer()

@dp.callback_query(F.data == "my_score")
async def show_my_score(call: CallbackQuery):
    score = get_score(call.from_user.id)
    await call.message.edit_text(f"📊 Твой рекорд: <b>{score} очков</b>", parse_mode="HTML", reply_markup=main_menu())
    await call.answer()

# ==================== ИГРА ====================
@dp.callback_query(F.data == "play")
async def choose_difficulty(call: CallbackQuery):
    await call.message.edit_text(
        "Выбери уровень сложности:\n\n"
        "🟢 <b>Легко</b> — простые примеры\n"
        "🟡 <b>Средне</b> — добавлено умножение\n"
        "🔴 <b>Хард</b> — всё вперемешку, включая деление",
        parse_mode="HTML",
        reply_markup=difficulty_menu()
    )
    await call.answer()

@dp.callback_query(F.data.startswith("diff_"))
async def start_game(call: CallbackQuery, state: FSMContext):
    difficulty = call.data.replace("diff_", "")
    await state.clear()
    await state.update_data(
        difficulty=difficulty,
        current_round=1,
        correct_answers=0,
        timer_task=None,
    )
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
    if old_task:
        old_task.cancel()
    
    question_text, answer = generate_question(difficulty)
    await state.update_data(answer=answer)
    
    progress = "🟩" * current_round + "⬜" * (TOTAL_QUESTIONS - current_round)
    
    await message.edit_text(
        f"{progress}\n"
        f"❓ <b>Вопрос {current_round} из {TOTAL_QUESTIONS}</b>\n\n"
        f"<code>{question_text} = ?</code>\n\n"
        f"⏱ У тебя 15 секунд!",
        parse_mode="HTML",
        reply_markup=cancel_menu()
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
            await message.answer(
                f"⏰ <b>Время вышло!</b>\n"
                f"Правильный ответ был: <b>{correct}</b>\n\n"
                f"Переходим к следующему...",
                parse_mode="HTML"
            )
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
    if old_task:
        old_task.cancel()
    
    try:
        user_answer = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введи <b>число</b>!", parse_mode="HTML")
        task = asyncio.create_task(timeout_task(message, state, current_round))
        await state.update_data(timer_task=task)
        return
    
    if user_answer == correct:
        correct_answers += 1
        await message.answer(f"✅ <b>Верно!</b> +1 очко", parse_mode="HTML")
    else:
        await message.answer(f"❌ <b>Ошибка.</b> Правильный ответ: <b>{correct}</b>", parse_mode="HTML")
    
    try:
        await message.delete()
    except:
        pass
    
    await state.update_data(
        correct_answers=correct_answers,
        current_round=current_round + 1,
    )
    await asyncio.sleep(1.5)
    await next_question(message, state)

async def finish_game(message: Message, state: FSMContext):
    data = await state.get_data()
    correct_answers = data.get("correct_answers", 0)
    user_id = message.chat.id
    name = message.chat.first_name or "Игрок"
    
    if correct_answers > 0:
        add_score(user_id, name, correct_answers)
    
    await state.clear()
    
    if correct_answers == TOTAL_QUESTIONS:
        emoji, title, comment = "🏆", "ИДЕАЛЬНО!", "Ты настоящий гений математики!"
    elif correct_answers >= TOTAL_QUESTIONS * 0.7:
        emoji, title, comment = "🔥", "ОТЛИЧНО!", "Быстрая реакция и светлая голова!"
    elif correct_answers >= TOTAL_QUESTIONS * 0.4:
        emoji, title, comment = "👍", "ХОРОШО!", "Неплохой результат, но можно лучше!"
    else:
        emoji, title, comment = "💪", "ЕСТЬ КУДА РАСТИ", "Тренируйся, и всё получится!"
    
    text = (
        f"{emoji} <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"Правильных ответов: <b>{correct_answers} из {TOTAL_QUESTIONS}</b>\n"
        f"<i>{comment}</i>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📈 Твой общий рекорд: <b>{get_score(user_id)} очков</b>."
    )
    await message.edit_text(text, parse_mode="HTML", reply_markup=main_menu())

@dp.callback_query(F.data == "cancel")
async def cancel_game(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    old_task = data.get("timer_task")
    if old_task:
        old_task.cancel()
    await state.clear()
    await call.message.edit_text("🛑 Игра прервана.", reply_markup=main_menu())
    await call.answer()

# ==================== ЗАПУСК ====================
async def main():
    init_db()
    print("Математический бот запущен...")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())