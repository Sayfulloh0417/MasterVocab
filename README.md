# 📚 Vocabulary Bot

Ingliz so'zlarini o'rganish uchun Telegram bot.

## O'yinlar
- ❓ Quiz — 4 variant ichidan tanlash
- ✍️ Typing — tarjimasini o'zing yoz
- 🃏 Flashcard — bildim / bilmadim

## Buyruqlar
- `/start` — Botni boshlash
- `/add` — Yangi so'z qo'shish
- `/cancel` — Bekor qilish

---

## 🚀 Railway'ga Deploy qilish

### 1-qadam: GitHub repo yaratish
1. github.com ga kiring
2. "New repository" → nom bering (masalan: `vocab-bot`)
3. Bu fayllarni yuklang

### 2-qadam: Railway
1. railway.app ga kiring (GitHub bilan)
2. "New Project" → "Deploy from GitHub repo"
3. Repo'ni tanlang

### 3-qadam: Environment Variables
Railway dashboard → Variables bo'limiga qo'shing:

```
BOT_TOKEN = 8784167138:AAF_gTAGDIqf148pEM5d3W81U3YkBAtNFrE
OWNER_ID = sizning_telegram_id_ingiz
```

**OWNER_ID olish:** @userinfobot ga /start yuboring

### 4-qadam: Deploy
Railway avtomatik deploy qiladi. Bo'ldi! 🎉

---

## ⚠️ Muhim
- `BOT_TOKEN` ni hech kimga bermang
- Database (`vocab.db`) Railway'ning volume'ida saqlanadi
