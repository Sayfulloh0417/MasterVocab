import sqlite3
import os
from datetime import datetime, date

DB_PATH = os.environ.get("DB_PATH", "vocab.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            translation TEXT NOT NULL,
            example TEXT DEFAULT '',
            added_date TEXT DEFAULT '',
            times_seen INTEGER DEFAULT 0,
            times_correct INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            total INTEGER,
            correct INTEGER
        )
    """)
    conn.commit()
    conn.close()

def add_word(word: str, translation: str, example: str = ""):
    conn = get_conn()
    c = conn.cursor()
    # Check duplicate
    c.execute("SELECT id FROM words WHERE LOWER(word)=LOWER(?)", (word,))
    if c.fetchone():
        conn.close()
        return False
    c.execute(
        "INSERT INTO words (word, translation, example, added_date) VALUES (?,?,?,?)",
        (word, translation, example, date.today().isoformat())
    )
    conn.commit()
    conn.close()
    return True

def get_all_words():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM words ORDER BY added_date DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_today_words():
    conn = get_conn()
    c = conn.cursor()
    today = date.today().isoformat()
    c.execute("SELECT * FROM words WHERE added_date=?", (today,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_words_for_quiz(limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM words ORDER BY times_seen ASC, RANDOM() LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

def update_word_stats(word_id: int, correct: bool):
    conn = get_conn()
    c = conn.cursor()
    if correct:
        c.execute("UPDATE words SET times_seen=times_seen+1, times_correct=times_correct+1 WHERE id=?", (word_id,))
    else:
        c.execute("UPDATE words SET times_seen=times_seen+1 WHERE id=?", (word_id,))
    conn.commit()
    conn.close()

def delete_word(word_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM words WHERE id=?", (word_id,))
    conn.commit()
    conn.close()

def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM words")
    total = c.fetchone()["total"]
    today = date.today().isoformat()
    c.execute("SELECT COUNT(*) as cnt FROM words WHERE added_date=?", (today,))
    today_count = c.fetchone()["cnt"]
    c.execute("SELECT SUM(times_seen) as ts, SUM(times_correct) as tc FROM words")
    row = c.fetchone()
    ts = row["ts"] or 0
    tc = row["tc"] or 0
    conn.close()
    return {"total": total, "today": today_count, "times_seen": ts, "times_correct": tc}

def save_quiz_result(total: int, correct: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO quiz_results (date, total, correct) VALUES (?,?,?)",
              (date.today().isoformat(), total, correct))
    conn.commit()
    conn.close()

def search_word(query: str):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM words WHERE LOWER(word) LIKE LOWER(?) OR LOWER(translation) LIKE LOWER(?)",
              (f"%{query}%", f"%{query}%"))
    rows = c.fetchall()
    conn.close()
    return rows
