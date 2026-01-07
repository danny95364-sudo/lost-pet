
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Optional
from db import get_recent_pets, get_db_connection

app = FastAPI(title="Pet Hunter API", description="搜集全台走失寵物資料", version="2.1")

# 允許跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 整合爬蟲 Daemon (For Render Free Tier)
import threading
from pet_crawler_daemon import PetCrawlerDaemon

@app.on_event("startup")
def startup_event():
    print("🚀 Server starting... Launching Background Crawler...")
    try:
        daemon = PetCrawlerDaemon()
        # 使用 daemon thread，主程式結束時它也會跟著結束
        t = threading.Thread(target=daemon.start_daemon, daemon=True)
        t.start()
        print("✅ Background Crawler started!")
    except Exception as e:
        print(f"❌ Failed to start crawler: {e}")

@app.get("/")
def home():
    return {"message": "Welcome to Pet Hunter API v2.0 - Use /pets to search"}

@app.get("/pets")
def search_pets(
    city: Optional[str] = Query(None, description="縣市篩選 (e.g. 台北)"),
    type: Optional[str] = Query(None, description="種類篩選 (e.g. 狗, 貓)"),
    days: int = Query(14, description="搜尋最近幾天 (預設14)")
):
    """
    搜尋走失寵物
    """
    pets = get_recent_pets(days=days, city_filter=city, type_filter=type)
    return {
        "count": len(pets),
        "data": pets
    }

@app.get("/clinics")
def search_clinics(city: Optional[str] = Query(None)):
    """
    搜尋動物醫院
    """
    conn = get_db_connection()
    c = conn.cursor()
    query = "SELECT * FROM vet_clinics"
    params = []
    
    if city:
        query += " WHERE address LIKE ?"
        params.append(f"%{city}%")
        
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return {
        "count": len(rows),
        "data": [dict(r) for r in rows]
    }

@app.get("/stats")
def get_stats(days: int = Query(30, description="統計最近幾天 (預設30)")):
    """
    取得統計數據
    """
    from datetime import datetime, timedelta
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # 統計總數 (加上 lost_time >= cutoff_date)
    c.execute("SELECT COUNT(*) FROM lost_pets WHERE status='Open' AND lost_time >= ?", (cutoff_date,))
    total_open = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM lost_pets WHERE status='Open' AND pet_type LIKE '%狗%' AND lost_time >= ?", (cutoff_date,))
    dogs = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM lost_pets WHERE status='Open' AND pet_type LIKE '%貓%' AND lost_time >= ?", (cutoff_date,))
    cats = c.fetchone()[0]
    
    conn.close()
    
    return {
        "days": days,
        "total_active_cases": total_open,
        "dogs": dogs,
        "cats": cats,
        "others": total_open - dogs - cats
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
