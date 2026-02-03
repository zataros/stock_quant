import sqlite3
import hashlib
import os
import pandas as pd
from datetime import datetime

DB_DIR = "Data"
# [변경] 데이터베이스 파일 2개로 분리
DB_USER_FILE = os.path.join(DB_DIR, "users.db")       # 유저, 즐겨찾기, 히스토리
DB_PRICE_FILE = os.path.join(DB_DIR, "stock_data.db") # 주가 데이터 (용량 큼)

def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    # 1. 유저 DB 초기화
    conn_user = sqlite3.connect(DB_USER_FILE, check_same_thread=False)
    c_user = conn_user.cursor()
    
    c_user.execute('''CREATE TABLE IF NOT EXISTS users 
                      (username TEXT PRIMARY KEY, password TEXT, email TEXT, role TEXT)''')
    
    c_user.execute('''CREATE TABLE IF NOT EXISTS favorites 
                      (username TEXT, code TEXT, PRIMARY KEY (username, code))''')
    
    # 마이그레이션 (유저 DB)
    try: c_user.execute("ALTER TABLE favorites ADD COLUMN added_date TEXT")
    except sqlite3.OperationalError: pass
    try: c_user.execute("ALTER TABLE favorites ADD COLUMN initial_price REAL DEFAULT 0")
    except sqlite3.OperationalError: pass
    try: c_user.execute("ALTER TABLE favorites ADD COLUMN strategies TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: c_user.execute("ALTER TABLE favorites ADD COLUMN name TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass

    c_user.execute('''CREATE TABLE IF NOT EXISTS scan_history 
                      (id INTEGER PRIMARY KEY AUTOINCREMENT,
                       scan_date TEXT,
                       strategy_name TEXT,
                       code TEXT,
                       name TEXT,
                       entry_price REAL,
                       market TEXT,
                       UNIQUE(scan_date, strategy_name, code))''')
                  
    c_user.execute('''CREATE TABLE IF NOT EXISTS strategy_stats 
                      (strategy_name TEXT PRIMARY KEY,
                       win_rate REAL,
                       total_count INTEGER,
                       last_updated TEXT)''')
    conn_user.commit()
    conn_user.close()

    # 2. 주가 데이터 DB 초기화
    conn_price = sqlite3.connect(DB_PRICE_FILE, check_same_thread=False)
    c_price = conn_price.cursor()
    
    c_price.execute('''CREATE TABLE IF NOT EXISTS stock_prices 
                       (code TEXT,
                        date TEXT,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume REAL,
                        PRIMARY KEY (code, date))''')
    
    c_price.execute('CREATE INDEX IF NOT EXISTS idx_stock_code ON stock_prices (code)')
    conn_price.commit()
    conn_price.close()

# --- 헬퍼 함수: DB 연결 ---
def get_user_conn():
    init_db() # 폴더 없으면 생성
    return sqlite3.connect(DB_USER_FILE, check_same_thread=False)

def get_price_conn():
    init_db()
    return sqlite3.connect(DB_PRICE_FILE, check_same_thread=False)

# =========================================================
# [Part 1] 유저 DB 관련 함수 (users.db 사용)
# =========================================================

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def sign_up(username, password, email):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users")
    user_count = c.fetchone()[0]
    role = 'admin' if user_count == 0 else 'user'
    try:
        c.execute("INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)", 
                  (username, hash_pw(password), email, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError: return False
    finally: conn.close()

def check_login(username, password):
    conn = get_user_conn()
    c = conn.cursor()
    hashed = hash_pw(password)
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed))
    res = c.fetchone()
    conn.close()
    return res is not None

def get_user_role(username):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT role FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 'user'

def verify_user_email(username, email):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND email = ?", (username, email))
    res = c.fetchone()
    conn.close()
    return res is not None

def update_password(username, new_password):
    conn = get_user_conn()
    c = conn.cursor()
    hashed = hash_pw(new_password)
    c.execute("UPDATE users SET password = ? WHERE username = ?", (hashed, username))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT username, email, role FROM users")
    res = c.fetchall()
    conn.close()
    return res

def delete_user(target_username):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username = ?", (target_username,))
    c.execute("DELETE FROM favorites WHERE username = ?", (target_username,))
    conn.commit()
    conn.close()

# --- 관심종목 ---
def get_favorites(username):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT code, added_date, initial_price, strategies, name FROM favorites WHERE username = ?", (username,))
    res = c.fetchall()
    conn.close()
    return res

def add_favorite(username, code, name="", price=0.0, strategies="Manual"):
    conn = get_user_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute('''INSERT OR IGNORE INTO favorites 
                 (username, code, added_date, initial_price, strategies, name) 
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (username, code, today, price, strategies, name))
    conn.commit()
    conn.close()

def remove_favorite(username, code):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("DELETE FROM favorites WHERE username = ? AND code = ?", (username, code))
    conn.commit()
    conn.close()

def update_favorite_price(username, code, new_price):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("UPDATE favorites SET initial_price = ? WHERE username = ? AND code = ?", 
              (new_price, username, code))
    conn.commit()
    conn.close()

def update_favorite_date(username, code, new_date_str):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("UPDATE favorites SET added_date = ? WHERE username = ? AND code = ?", 
              (new_date_str, username, code))
    conn.commit()
    conn.close()

# --- 스캔 히스토리 & 통계 ---
def save_scan_result(scan_date, strategy_name, code, name, entry_price, market):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO scan_history 
                 (scan_date, strategy_name, code, name, entry_price, market) 
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (scan_date, strategy_name, code, name, entry_price, market))
    conn.commit()
    conn.close()

def get_scan_history_dates():
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT scan_date FROM scan_history ORDER BY scan_date DESC")
    res = [row[0] for row in c.fetchall()]
    conn.close()
    return res

def get_history_by_date(target_date):
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT strategy_name, code, name, entry_price, market FROM scan_history WHERE scan_date = ?", (target_date,))
    res = c.fetchall()
    conn.close()
    return res

def update_strategy_stats(stats_dict):
    conn = get_user_conn()
    c = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for strat, data in stats_dict.items():
        win_rate = (data['win'] / data['total']) * 100 if data['total'] > 0 else 0
        c.execute('''INSERT OR REPLACE INTO strategy_stats 
                     (strategy_name, win_rate, total_count, last_updated)
                     VALUES (?, ?, ?, ?)''', 
                  (strat, win_rate, data['total'], today))
    conn.commit()
    conn.close()

def get_strategy_stats():
    conn = get_user_conn()
    c = conn.cursor()
    c.execute("SELECT strategy_name, win_rate FROM strategy_stats")
    res = {row[0]: row[1] for row in c.fetchall()}
    conn.close()
    return res

# =========================================================
# [Part 2] 주가 데이터 캐싱 관련 함수 (stock_data.db 사용)
# =========================================================

def get_last_price_date(code):
    """해당 종목의 가장 최근 저장된 날짜 반환"""
    conn = get_price_conn() # 주가 DB 연결
    c = conn.cursor()
    c.execute("SELECT max(date) FROM stock_prices WHERE code = ?", (code,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def save_daily_price(df, code):
    """DataFrame 저장"""
    if df is None or df.empty: return
    
    conn = get_price_conn() # 주가 DB 연결
    c = conn.cursor()
    
    data_to_insert = []
    for date_idx, row in df.iterrows():
        date_str = date_idx.strftime("%Y-%m-%d")
        if pd.isna(row['Open']) or pd.isna(row['Close']): continue
        
        data_to_insert.append((
            str(code),
            date_str,
            float(row['Open']),
            float(row['High']),
            float(row['Low']),
            float(row['Close']),
            float(row.get('Volume', 0))
        ))
    
    c.executemany('''INSERT OR IGNORE INTO stock_prices 
                     (code, date, open, high, low, close, volume) 
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', data_to_insert)
    conn.commit()
    conn.close()

def load_daily_price(code):
    """주가 데이터 로드"""
    conn = get_price_conn() # 주가 DB 연결
    query = "SELECT date, open, high, low, close, volume FROM stock_prices WHERE code = ? ORDER BY date ASC"
    df = pd.read_sql(query, conn, params=(code,))
    conn.close()
    
    if df.empty: return None
    
    df.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
    df['Date'] = pd.to_datetime(df['Date'])
    df.set_index('Date', inplace=True)
    
    return df