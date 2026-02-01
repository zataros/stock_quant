import sqlite3
import hashlib
import os
from datetime import datetime

DB_DIR = "Data"
DB_FILE = os.path.join(DB_DIR, "quant_scanner.db")

def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, email TEXT, role TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS favorites 
                 (username TEXT, code TEXT, PRIMARY KEY (username, code))''')
    
    # [마이그레이션] 기존 컬럼들
    try: c.execute("ALTER TABLE favorites ADD COLUMN added_date TEXT")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE favorites ADD COLUMN initial_price REAL DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE favorites ADD COLUMN strategies TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE favorites ADD COLUMN name TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass

    # 성과 추적 히스토리
    c.execute('''CREATE TABLE IF NOT EXISTS scan_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  scan_date TEXT,
                  strategy_name TEXT,
                  code TEXT,
                  name TEXT,
                  entry_price REAL,
                  market TEXT,
                  UNIQUE(scan_date, strategy_name, code))''')
                  
    # [신규] 전략별 전역 승률 통계 저장 (공유 데이터)
    c.execute('''CREATE TABLE IF NOT EXISTS strategy_stats 
                 (strategy_name TEXT PRIMARY KEY,
                  win_rate REAL,
                  total_count INTEGER,
                  last_updated TEXT)''')

    conn.commit()
    return conn

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def sign_up(username, password, email):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users")
    user_count = c.fetchone()[0]
    role = 'admin' if user_count == 0 else 'user'
    
    try:
        c.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)", 
                  (username, hash_pw(password), email, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def check_login(username, password):
    conn = init_db()
    c = conn.cursor()
    hashed = hash_pw(password)
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed))
    return c.fetchone() is not None

def get_user_role(username):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    return result[0] if result else 'user'

def verify_user_email(username, email):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND email = ?", (username, email))
    return c.fetchone() is not None

def update_password(username, new_password):
    conn = init_db()
    c = conn.cursor()
    hashed = hash_pw(new_password)
    c.execute("UPDATE users SET password = ? WHERE username = ?", (hashed, username))
    conn.commit()

def get_all_users():
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT username, email, role FROM users")
    return c.fetchall()

def delete_user(target_username):
    conn = init_db()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (target_username,))
    c.execute("DELETE FROM favorites WHERE username = ?", (target_username,))
    conn.commit()

# --- 관심종목 기능 ---
def get_favorites(username):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT code, added_date, initial_price, strategies, name FROM favorites WHERE username = ?", (username,))
    return c.fetchall()

def add_favorite(username, code, name="", price=0.0, strategies="Manual"):
    conn = init_db()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute('''INSERT OR IGNORE INTO favorites 
                 (username, code, added_date, initial_price, strategies, name) 
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (username, code, today, price, strategies, name))
    conn.commit()

def remove_favorite(username, code):
    conn = init_db()
    c = conn.cursor()
    c.execute("DELETE FROM favorites WHERE username = ? AND code = ?", (username, code))
    conn.commit()

def update_favorite_price(username, code, new_price):
    conn = init_db()
    c = conn.cursor()
    c.execute("UPDATE favorites SET initial_price = ? WHERE username = ? AND code = ?", 
              (new_price, username, code))
    conn.commit()

def update_favorite_date(username, code, new_date_str):
    conn = init_db()
    c = conn.cursor()
    c.execute("UPDATE favorites SET added_date = ? WHERE username = ? AND code = ?", 
              (new_date_str, username, code))
    conn.commit()

# --- 성과 추적 (History) 기능 ---
def save_scan_result(scan_date, strategy_name, code, name, entry_price, market):
    conn = init_db()
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO scan_history 
                 (scan_date, strategy_name, code, name, entry_price, market) 
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (scan_date, strategy_name, code, name, entry_price, market))
    conn.commit()

def get_scan_history_dates():
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT scan_date FROM scan_history ORDER BY scan_date DESC")
    return [row[0] for row in c.fetchall()]

def get_history_by_date(target_date):
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT strategy_name, code, name, entry_price, market FROM scan_history WHERE scan_date = ?", (target_date,))
    return c.fetchall()

# [신규] 전역 승률 통계 관리
def update_strategy_stats(stats_dict):
    """
    stats_dict: {'전략명': {'win': 10, 'total': 20}, ...}
    """
    conn = init_db()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for strat, data in stats_dict.items():
        win_rate = (data['win'] / data['total']) * 100 if data['total'] > 0 else 0
        c.execute('''INSERT OR REPLACE INTO strategy_stats 
                     (strategy_name, win_rate, total_count, last_updated)
                     VALUES (?, ?, ?, ?)''', 
                  (strat, win_rate, data['total'], today))
    conn.commit()

def get_strategy_stats():
    """Returns: {'전략명': win_rate, ...}"""
    conn = init_db()
    c = conn.cursor()
    c.execute("SELECT strategy_name, win_rate FROM strategy_stats")
    return {row[0]: row[1] for row in c.fetchall()}