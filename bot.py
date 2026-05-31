import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)
from database import (
    init_db, add_word, get_all_words, get_today_words,
    get_words_for_quiz, update_word_stats, delete_word,
    get_stats, save_quiz_result, search_word
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# Conversation states
ADD_WORD, ADD_TRANSLATION, ADD_EXAMPLE = range(3)
QUIZ_ANSWER = 10
TYPING_ANSWER = 20
FLASHCARD_NEXT = 30
DELETE_CONFIRM = 40
SEARCH_QUERY = 50

# Temporary data store
user_data_store = {}

# ─── HELPERS ───────────────────────────────────────────────────────────────

def is_owner(update: Update) -> bool:
    return OWNER_ID == 0 or update.effective_user.id == OWNER_ID

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ So'z qo'shish", callback_data="menu_add"),
         InlineKeyboardButton("📋 So'zlar ro'yxati", callback_data="menu_list")],
        [InlineKeyboardButton("🎮 O'yinlar", callback_data="menu_games"),
         InlineKeyboardButton("📊 Statistika", callback_data="menu_stats")],
        [InlineKeyboardButton("🔍 Qidirish", callback_data="menu_search")]
    ])

def games_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ Quiz (4 variant)", callback_data="game_quiz")],
        [InlineKeyboardButton("✍️ Typing (yozib javob ber)", callback_data="game_typing")],
        [InlineKeyboardButton("🃏 Flashcard", callback_data="game_flashcard")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="menu_back")]
    ])

# ─── START / MENU ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_db()
    await update.message.reply_text(
        "👋 Salom! Men sizning *Vocabulary Bot*ingizman!\n\n"
        "Ingliz so'zlarini o'rganishga yordam beraman. Quyidan tanlang:",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu_back":
        await query.edit_message_text(
            "📚 Asosiy menyu:",
            reply_markup=main_menu_keyboard()
        )

    elif data == "menu_games":
        words = get_all_words()
        if len(words) < 4:
            await query.edit_message_text(
                "⚠️ O'yin uchun kamida 4 ta so'z kerak!\n"
                "Avval so'z qo'shing ➕",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Orqaga", callback_data="menu_back")
                ]])
            )
        else:
            await query.edit_message_text("🎮 Qaysi o'yinni tanlaysiz?", reply_markup=games_keyboard())

    elif data == "menu_stats":
        stats = get_stats()
        accuracy = 0
        if stats["times_seen"] > 0:
            accuracy = round(stats["times_correct"] / stats["times_seen"] * 100, 1)
        text = (
            f"📊 *Statistika*\n\n"
            f"📚 Jami so'zlar: *{stats['total']}*\n"
            f"📅 Bugun qo'shilgan: *{stats['today']}*\n"
            f"👁 Jami ko'rilgan: *{stats['times_seen']}*\n"
            f"✅ To'g'ri javoblar: *{stats['times_correct']}*\n"
            f"🎯 Aniqlik: *{accuracy}%*"
        )
        await query.edit_message_text(text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Orqaga", callback_data="menu_back")
            ]]))

    elif data == "menu_list":
        await show_word_list(query)

    elif data == "menu_add":
        user_data_store[query.from_user.id] = {}
        await query.edit_message_text(
            "➕ *Yangi so'z qo'shish*\n\n"
            "Inglizcha so'zni yozing:\n"
            "_(bekor qilish uchun /cancel)_",
            parse_mode="Markdown"
        )
        return ADD_WORD

    elif data == "menu_search":
        await query.edit_message_text(
            "🔍 Qidirmoqchi bo'lgan so'zni yozing:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Orqaga", callback_data="menu_back")
            ]])
        )
        return SEARCH_QUERY

# ─── WORD LIST ─────────────────────────────────────────────────────────────

async def show_word_list(query_or_message, page=0):
    words = get_all_words()
    if not words:
        text = "📋 Hali so'z qo'shilmagan.\n\n➕ So'z qo'shish uchun menyudan foydalaning."
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="menu_back")]])
        if hasattr(query_or_message, 'edit_message_text'):
            await query_or_message.edit_message_text(text, reply_markup=kb)
        else:
            await query_or_message.reply_text(text, reply_markup=kb)
        return

    per_page = 10
    total_pages = (len(words) - 1) // per_page + 1
    start_i = page * per_page
    end_i = start_i + per_page
    page_words = words[start_i:end_i]

    lines = [f"📋 *So'zlar ro'yxati* ({len(words)} ta) — Sahifa {page+1}/{total_pages}\n"]
    for i, w in enumerate(page_words, start=start_i+1):
        lines.append(f"{i}. *{w['word']}* — {w['translation']}")

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"list_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"list_page_{page+1}"))

    kb = []
    if nav_buttons:
        kb.append(nav_buttons)
    kb.append([
        InlineKeyboardButton("🗑 So'z o'chirish", callback_data="list_delete"),
        InlineKeyboardButton("🔙 Orqaga", callback_data="menu_back")
    ])

    text = "\n".join(lines)
    if hasattr(query_or_message, 'edit_message_text'):
        await query_or_message.edit_message_text(text, parse_mode="Markdown",
                                                  reply_markup=InlineKeyboardMarkup(kb))
    else:
        await query_or_message.reply_text(text, parse_mode="Markdown",
                                           reply_markup=InlineKeyboardMarkup(kb))

async def list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("list_page_"):
        page = int(data.split("_")[-1])
        await show_word_list(query, page)

    elif data == "list_delete":
        await query.edit_message_text(
            "🗑 O'chirmoqchi bo'lgan so'zni yozing\n"
            "_(masalan: apple)_\n\n"
            "_(bekor qilish uchun /cancel)_",
            parse_mode="Markdown"
        )
        return DELETE_CONFIRM

# ─── ADD WORD CONVERSATION ─────────────────────────────────────────────────

async def add_word_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update):
        await update.message.reply_text("❌ Siz bu botni ishlata olmaysiz.")
        return ConversationHandler.END
    user_data_store[update.effective_user.id] = {}
    await update.message.reply_text(
        "➕ *Yangi so'z qo'shish*\n\nInglizcha so'zni yozing:",
        parse_mode="Markdown"
    )
    return ADD_WORD

async def receive_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    word = update.message.text.strip()
    user_data_store[uid] = {"word": word}
    await update.message.reply_text(
        f"✅ So'z: *{word}*\n\nEndi o'zbekcha tarjimasini yozing:",
        parse_mode="Markdown"
    )
    return ADD_TRANSLATION

async def receive_translation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    translation = update.message.text.strip()
    user_data_store[uid]["translation"] = translation
    await update.message.reply_text(
        f"✅ Tarjima: *{translation}*\n\n"
        "Misol jumla qo'shmoqchimisiz? (ixtiyoriy)\n"
        "Misol: _She is very _*ambitious*_._\n\n"
        "Yo'q bo'lsa — /skip yozing",
        parse_mode="Markdown"
    )
    return ADD_EXAMPLE

async def receive_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    example = update.message.text.strip()
    data = user_data_store.get(uid, {})
    word = data.get("word", "")
    translation = data.get("translation", "")

    success = add_word(word, translation, example)
    if success:
        await update.message.reply_text(
            f"🎉 *{word}* — {translation}\nsaqlandi!\n\n📝 Misol: _{example}_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Yana qo'shish", callback_data="menu_add"),
                InlineKeyboardButton("🏠 Menyu", callback_data="menu_back")
            ]])
        )
    else:
        await update.message.reply_text(
            f"⚠️ *{word}* allaqachon mavjud!",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    user_data_store.pop(uid, None)
    return ConversationHandler.END

async def skip_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = user_data_store.get(uid, {})
    word = data.get("word", "")
    translation = data.get("translation", "")

    success = add_word(word, translation, "")
    if success:
        await update.message.reply_text(
            f"🎉 *{word}* — {translation} saqlandi!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("➕ Yana qo'shish", callback_data="menu_add"),
                InlineKeyboardButton("🏠 Menyu", callback_data="menu_back")
            ]])
        )
    else:
        await update.message.reply_text(f"⚠️ *{word}* allaqachon mavjud!", parse_mode="Markdown",
                                        reply_markup=main_menu_keyboard())
    user_data_store.pop(uid, None)
    return ConversationHandler.END

# ─── DELETE WORD ───────────────────────────────────────────────────────────

async def receive_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results = search_word(query_text)
    if not results:
        await update.message.reply_text("❌ Bunday so'z topilmadi.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    if len(results) == 1:
        w = results[0]
        delete_word(w["id"])
        await update.message.reply_text(
            f"🗑 *{w['word']}* o'chirildi.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        buttons = []
        for w in results[:5]:
            buttons.append([InlineKeyboardButton(
                f"🗑 {w['word']} — {w['translation']}",
                callback_data=f"del_{w['id']}"
            )])
        buttons.append([InlineKeyboardButton("🔙 Bekor qilish", callback_data="menu_back")])
        await update.message.reply_text(
            "Qaysi so'zni o'chirmoqchisiz?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    return ConversationHandler.END

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    word_id = int(query.data.split("_")[1])
    delete_word(word_id)
    await query.edit_message_text("🗑 So'z o'chirildi.", reply_markup=main_menu_keyboard())

# ─── SEARCH ────────────────────────────────────────────────────────────────

async def receive_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = update.message.text.strip()
    results = search_word(query_text)
    if not results:
        await update.message.reply_text(
            f"❌ *{query_text}* topilmadi.",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END

    lines = [f"🔍 *'{query_text}'* bo'yicha natijalar:\n"]
    for w in results[:10]:
        lines.append(f"• *{w['word']}* — {w['translation']}")
        if w['example']:
            lines.append(f"  _{w['example']}_")
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ─── QUIZ GAME ─────────────────────────────────────────────────────────────

async def start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    words = get_words_for_quiz(10)
    if len(words) < 4:
        await query.edit_message_text("⚠️ Kamida 4 ta so'z kerak!", reply_markup=games_keyboard())
        return

    uid = query.from_user.id
    user_data_store[uid] = {
        "quiz_words": [dict(w) for w in words],
        "quiz_index": 0,
        "quiz_correct": 0
    }
    await send_quiz_question(query.message, uid, edit=True)

async def send_quiz_question(message, uid, edit=False):
    data = user_data_store.get(uid, {})
    words = data.get("quiz_words", [])
    index = data.get("quiz_index", 0)

    if index >= len(words):
        correct = data.get("quiz_correct", 0)
        total = len(words)
        save_quiz_result(total, correct)
        emoji = "🏆" if correct == total else ("😊" if correct >= total // 2 else "😅")
        text = (f"{emoji} *Quiz tugadi!*\n\n"
                f"✅ To'g'ri: *{correct}/{total}*\n"
                f"🎯 Natija: *{round(correct/total*100)}%*")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Yana o'ynash", callback_data="game_quiz"),
            InlineKeyboardButton("🏠 Menyu", callback_data="menu_back")
        ]])
        if edit:
            await message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        user_data_store.pop(uid, None)
        return

    current = words[index]
    all_words = get_all_words()
    wrong_options = [w for w in all_words if w["id"] != current["id"]]
    random.shuffle(wrong_options)
    options = [{"word": w["word"], "translation": w["translation"], "correct": False}
               for w in wrong_options[:3]]
    options.append({"word": current["word"], "translation": current["translation"], "correct": True})
    random.shuffle(options)

    buttons = []
    for i, opt in enumerate(options):
        cb = f"quiz_correct_{current['id']}" if opt["correct"] else f"quiz_wrong_{current['id']}_{i}"
        buttons.append([InlineKeyboardButton(opt["translation"], callback_data=cb)])

    text = (f"❓ *Quiz* — {index+1}/{len(words)}\n\n"
            f"*{current['word']}* — tarjimasi qaysi?")

    if edit:
        await message.edit_text(text, parse_mode="Markdown",
                                 reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await message.reply_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def quiz_answer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = user_data_store.get(uid, {})
    cb = query.data

    if cb.startswith("quiz_correct_"):
        word_id = int(cb.split("_")[2])
        update_word_stats(word_id, True)
        data["quiz_correct"] = data.get("quiz_correct", 0) + 1
        data["quiz_index"] = data.get("quiz_index", 0) + 1
        user_data_store[uid] = data
        await query.answer("✅ To'g'ri!", show_alert=False)
    elif cb.startswith("quiz_wrong_"):
        parts = cb.split("_")
        word_id = int(parts[2])
        update_word_stats(word_id, False)
        words = data.get("quiz_words", [])
        index = data.get("quiz_index", 0)
        correct_word = words[index] if index < len(words) else {}
        data["quiz_index"] = index + 1
        user_data_store[uid] = data
        await query.answer(f"❌ Noto'g'ri! To'g'risi: {correct_word.get('translation','')}", show_alert=True)

    await send_quiz_question(query.message, uid, edit=True)

# ─── TYPING GAME ───────────────────────────────────────────────────────────

async def start_typing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    words = get_words_for_quiz(10)
    if len(words) < 2:
        await query.edit_message_text("⚠️ Kamida 2 ta so'z kerak!", reply_markup=games_keyboard())
        return

    uid = query.from_user.id
    user_data_store[uid] = {
        "typing_words": [dict(w) for w in words],
        "typing_index": 0,
        "typing_correct": 0
    }
    await send_typing_question(query.message, uid, edit=True)
    return TYPING_ANSWER

async def send_typing_question(message, uid, edit=False):
    data = user_data_store.get(uid, {})
    words = data.get("typing_words", [])
    index = data.get("typing_index", 0)

    if index >= len(words):
        correct = data.get("typing_correct", 0)
        total = len(words)
        save_quiz_result(total, correct)
        emoji = "🏆" if correct == total else ("😊" if correct >= total // 2 else "😅")
        text = (f"{emoji} *Typing o'yini tugadi!*\n\n"
                f"✅ To'g'ri: *{correct}/{total}*\n"
                f"🎯 Natija: *{round(correct/total*100)}%*")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Yana o'ynash", callback_data="game_typing"),
            InlineKeyboardButton("🏠 Menyu", callback_data="menu_back")
        ]])
        if edit:
            await message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        user_data_store.pop(uid, None)
        return

    current = words[index]
    text = (f"✍️ *Typing* — {index+1}/{len(words)}\n\n"
            f"*{current['word']}* — o'zbekcha tarjimasini yozing:\n\n"
            f"_(bekor qilish: /skip)_")

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data="typing_skip")]])

    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def receive_typing_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = user_data_store.get(uid)
    if not data or "typing_words" not in data:
        return ConversationHandler.END

    answer = update.message.text.strip().lower()
    words = data["typing_words"]
    index = data["typing_index"]
    current = words[index]
    correct_answer = current["translation"].lower()

    if answer == correct_answer or answer in correct_answer or correct_answer in answer:
        data["typing_correct"] += 1
        update_word_stats(current["id"], True)
        await update.message.reply_text(f"✅ *To'g'ri!* {current['word']} = {current['translation']}", parse_mode="Markdown")
    else:
        update_word_stats(current["id"], False)
        await update.message.reply_text(
            f"❌ *Noto'g'ri!*\n{current['word']} = *{current['translation']}*\nSiz yozdingiz: _{answer}_",
            parse_mode="Markdown"
        )

    data["typing_index"] += 1
    user_data_store[uid] = data
    await send_typing_question(update.message, uid)
    return TYPING_ANSWER

async def typing_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = user_data_store.get(uid, {})
    if "typing_words" in data:
        data["typing_index"] = data.get("typing_index", 0) + 1
        user_data_store[uid] = data
        await send_typing_question(query.message, uid, edit=True)

# ─── FLASHCARD GAME ────────────────────────────────────────────────────────

async def start_flashcard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    words = get_words_for_quiz(15)
    if not words:
        await query.edit_message_text("⚠️ So'z yo'q!", reply_markup=games_keyboard())
        return

    uid = query.from_user.id
    shuffled = [dict(w) for w in words]
    random.shuffle(shuffled)
    user_data_store[uid] = {
        "flash_words": shuffled,
        "flash_index": 0,
        "flash_known": 0,
        "flash_unknown": 0,
        "flash_revealed": False
    }
    await send_flashcard(query.message, uid, edit=True)

async def send_flashcard(message, uid, edit=False):
    data = user_data_store.get(uid, {})
    words = data.get("flash_words", [])
    index = data.get("flash_index", 0)
    revealed = data.get("flash_revealed", False)

    if index >= len(words):
        known = data.get("flash_known", 0)
        unknown = data.get("flash_unknown", 0)
        total = known + unknown
        text = (f"🃏 *Flashcard tugadi!*\n\n"
                f"✅ Bildim: *{known}*\n"
                f"❌ Bilmadim: *{unknown}*\n"
                f"📊 Jami: *{total}*")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Qayta o'ynash", callback_data="game_flashcard"),
            InlineKeyboardButton("🏠 Menyu", callback_data="menu_back")
        ]])
        if edit:
            await message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
        else:
            await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
        user_data_store.pop(uid, None)
        return

    current = words[index]
    if not revealed:
        text = (f"🃏 *Flashcard* — {index+1}/{len(words)}\n\n"
                f"*{current['word']}*\n\n"
                f"Tarjimasini bilasizmi?")
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("👁 Ko'rsat", callback_data="flash_reveal")
        ]])
    else:
        text = (f"🃏 *Flashcard* — {index+1}/{len(words)}\n\n"
                f"*{current['word']}* = *{current['translation']}*")
        if current.get("example"):
            text += f"\n\n_{current['example']}_"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Bildim", callback_data="flash_known"),
            InlineKeyboardButton("❌ Bilmadim", callback_data="flash_unknown")
        ]])

    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def flashcard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = user_data_store.get(uid, {})
    cb = query.data

    if cb == "flash_reveal":
        data["flash_revealed"] = True
        user_data_store[uid] = data
        await send_flashcard(query.message, uid, edit=True)

    elif cb == "flash_known":
        index = data.get("flash_index", 0)
        words = data.get("flash_words", [])
        if index < len(words):
            update_word_stats(words[index]["id"], True)
        data["flash_known"] = data.get("flash_known", 0) + 1
        data["flash_index"] = index + 1
        data["flash_revealed"] = False
        user_data_store[uid] = data
        await send_flashcard(query.message, uid, edit=True)

    elif cb == "flash_unknown":
        index = data.get("flash_index", 0)
        words = data.get("flash_words", [])
        if index < len(words):
            update_word_stats(words[index]["id"], False)
        data["flash_unknown"] = data.get("flash_unknown", 0) + 1
        data["flash_index"] = index + 1
        data["flash_revealed"] = False
        user_data_store[uid] = data
        await send_flashcard(query.message, uid, edit=True)

# ─── CANCEL ────────────────────────────────────────────────────────────────

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user_data_store.pop(uid, None)
    await update.message.reply_text("❌ Bekor qilindi.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ─── MAIN ──────────────────────────────────────────────────────────────────

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    # Add word conversation
    add_conv = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_word_start),
            CallbackQueryHandler(menu_callback, pattern="^menu_add$")
        ],
        states={
            ADD_WORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_word)],
            ADD_TRANSLATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_translation)],
            ADD_EXAMPLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_example),
                CommandHandler("skip", skip_example)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    # Delete word conversation
    delete_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(list_callback, pattern="^list_delete$")],
        states={
            DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    # Search conversation
    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(menu_callback, pattern="^menu_search$")],
        states={
            SEARCH_QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_search)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    # Typing game conversation
    typing_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_typing, pattern="^game_typing$")],
        states={
            TYPING_ANSWER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_typing_answer),
                CallbackQueryHandler(typing_skip_callback, pattern="^typing_skip$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv)
    app.add_handler(delete_conv)
    app.add_handler(search_conv)
    app.add_handler(typing_conv)

    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_(back|list|stats|games)$"))
    app.add_handler(CallbackQueryHandler(list_callback, pattern="^list_page_"))
    app.add_handler(CallbackQueryHandler(quiz_answer_callback, pattern="^quiz_"))
    app.add_handler(CallbackQueryHandler(start_quiz, pattern="^game_quiz$"))
    app.add_handler(CallbackQueryHandler(start_flashcard, pattern="^game_flashcard$"))
    app.add_handler(CallbackQueryHandler(flashcard_callback, pattern="^flash_"))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern="^del_"))

    logger.info("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
