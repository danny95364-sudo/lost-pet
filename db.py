
import sqlite3
import os
from datetime import datetime
import json

DB_NAME = "pets.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化資料庫表格"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 走失寵物表
    c.execute('''
        CREATE TABLE IF NOT EXISTS lost_pets (
            id TEXT PRIMARY KEY,
            chip_num TEXT,
            pet_name TEXT,
            pet_type TEXT,
            breed TEXT,
            sex TEXT,
            color TEXT,
            lost_place TEXT,
            lost_time TEXT,
            owner_name TEXT,
            phone TEXT,
            picture_url TEXT,
            created_at TEXT,
            status TEXT DEFAULT 'Open',
            notified INTEGER DEFAULT 0
        )
    ''')
    
    # 用戶訂閱表 (用於通知功能)
    c.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT,  -- 'line', 'discord'
            webhook_url TEXT,
            city_filter TEXT, -- e.g., '台北市'
            created_at TEXT
        )
    ''')

    # 動物醫院表
    c.execute('''
        CREATE TABLE IF NOT EXISTS vet_clinics (
            id TEXT PRIMARY KEY,
            name TEXT,
            tel TEXT,
            address TEXT,
            doctor_name TEXT,
            google_map_link TEXT,
            updated_at TEXT
        )
    ''')
    
    # 加上索引以加速查詢
    c.execute("CREATE INDEX IF NOT EXISTS idx_status_time ON lost_pets (status, lost_time)")
    
    conn.commit()
    conn.close()
    print(f"[{datetime.now()}] ✅ 資料庫 {DB_NAME} 初始化完成 (含索引)")

def upsert_pet(pet_data: dict):
    """
    新增或更新寵物資料
    :param pet_data: 字典格式的寵物資料
    :return: is_new (Boolean) - 是否為新案件
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    pet_id = pet_data.get("UniqueKey")
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 檢查是否存在
    c.execute('SELECT id FROM lost_pets WHERE id = ?', (pet_id,))
    exists = c.fetchone()
    
    is_new = False
    
    if not exists:
        # 新增
        c.execute('''
            INSERT INTO lost_pets (
                id, chip_num, pet_name, pet_type, breed, sex, color, 
                lost_place, lost_time, owner_name, phone, picture_url, 
                created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            pet_id,
            pet_data.get("ChipNum", ""),
            pet_data.get("PetName", ""),
            pet_data.get("PetType", ""),
            pet_data.get("Breed", ""),
            pet_data.get("Sex", ""),
            pet_data.get("Color", ""),
            pet_data.get("LostPlace", ""),
            pet_data.get("LostTime", ""),
            pet_data.get("OwnerName", ""),
            pet_data.get("Phone", ""),
            pet_data.get("Picture", ""),
            now,
            'Open'
        ))
        is_new = True
    else:
        # 更新 (通常政府資料會變動不多，但可以更新狀態或圖片)
        c.execute('''
            UPDATE lost_pets SET 
                status = 'Open',
                lost_place = ?,
                phone = ?,
                picture_url = ?
            WHERE id = ?
        ''', (
            pet_data.get("LostPlace", ""),
            pet_data.get("Phone", ""),
            pet_data.get("Picture", ""),
            pet_id
        ))
    
    conn.commit()
    conn.close()
    return is_new

def upsert_clinic(clinic_data: dict):
    """新增或更新動物醫院"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 使用 名稱+地址 作為唯一ID (未必完美但堪用)
    unique_id = f"{clinic_data.get('name')}_{clinic_data.get('address')}"
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    c.execute('''
        INSERT OR REPLACE INTO vet_clinics (
            id, name, tel, address, doctor_name, google_map_link, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        unique_id,
        clinic_data.get('name', ''),
        clinic_data.get('tel', ''),
        clinic_data.get('address', ''),
        clinic_data.get('doctor_name', ''),
        clinic_data.get('google_map_link', ''),
        now
    ))
    
    conn.commit()
    conn.close()

def close_missing_pets(active_ids: list):
    """
    將不在 active_ids 列表中的 Open 案件標記為 Close (代表已尋獲或撤銷)
    """
    if not active_ids:
        return
        
    conn = get_db_connection()
    c = conn.cursor()
    
    # 用 batch 更新比較快，但 SQLite 限制 SQL 長度
    # 這裡反向操作：先撈出所有狀態為 Open 的 ID
    c.execute("SELECT id FROM lost_pets WHERE status = 'Open'")
    db_open_rows = c.fetchall()
    db_open_ids = {row[0] for row in db_open_rows}
    
    # 找出 DB 有但 API 沒有的 ID (即需關閉者)
    active_set = set(active_ids)
    to_close_ids = list(db_open_ids - active_set)
    
    if to_close_ids:
        print(f"[{datetime.now()}] 🧹 清理: 發現 {len(to_close_ids)} 筆案件已從來源撤銷，標記為 Close")
        # 批次更新
        # 分批處理以免太多參數
        batch_size = 900
        for i in range(0, len(to_close_ids), batch_size):
            batch = to_close_ids[i:i+batch_size]
            placeholders = ','.join(['?'] * len(batch))
            sql = f"UPDATE lost_pets SET status = 'Close' WHERE id IN ({placeholders})"
            c.execute(sql, batch)
        
        conn.commit()
    
    conn.close()

def get_recent_pets(days=14, city_filter=None, type_filter=None, status='Open'):
    """取得最近的走失案件 (SQL 優化版)"""
    conn = get_db_connection()
    c = conn.cursor()
    
    query = "SELECT * FROM lost_pets WHERE status = ?"
    params = [status]
    
    # 日期過濾 (SQL層級)
    if days:
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        query += " AND lost_time >= ?"
        params.append(cutoff_date)
    
    if city_filter:
        query += " AND lost_place LIKE ?"
        params.append(f"%{city_filter}%")
        
    if type_filter:
        query += " AND pet_type LIKE ?"
        params.append(f"%{type_filter}%")

    query += " ORDER BY lost_time DESC"
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

if __name__ == "__main__":
    init_db()
