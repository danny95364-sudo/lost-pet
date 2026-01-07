
import time
import schedule
from datetime import datetime
from db import init_db, upsert_pet, close_missing_pets
from fetcher import MOAClient
from notifier import send_notification

class PetCrawlerDaemon:
    def __init__(self):
        self.client = MOAClient()
        # 初始化資料庫
        init_db()

    def run_task(self):
        """核心任務：更新資料庫並通知"""
        print(f"\n[{datetime.now()}] ⏰ 定時任務啟動：開始更新資料庫...")

        # 1. 抓取資料 (抓取全部，確保沒有遺漏)
        pets = self.client.fetch_all_lost_pets(limit=1000)
        if not pets:
            print("   ⚠️ 無法取得新資料或資料為空。")
            return

        active_ids = []
        new_count = 0
        updated_count = 0

        # 2. 存入資料庫
        for pet in pets:
            # 收集 ID 用於比對撤銷案件
            if "UniqueKey" in pet:
                active_ids.append(pet["UniqueKey"])

            # upsert_pet 會回傳 True 如果是新案件
            is_new = upsert_pet(pet)
            
            if is_new:
                new_count += 1
                print(f"   🔥 新案件發現！[{pet['PetName']}] @ {pet['LostPlace']}")
                try:
                    send_notification(pet)
                except:
                    pass
            else:
                updated_count += 1

        # 3. 標記已撤銷案件 (API 沒給但 DB 是 Open 的)
        close_missing_pets(active_ids)

        print(f"   ✅ 更新完成: 新增 {new_count} 筆 / 更新 {updated_count} 筆")
        
    def start_daemon(self):
        print("=== 🚀 寵物爬蟲 Daemon v2.0 啟動 (Ctrl+C 可停止) ===")
        print("   📅 設定排程：每 1 小時執行一次 (測試用)")
        
        # 立即先執行一次
        self.run_task()
        
        # 設定排程 (範例: 每小時)
        schedule.every(1).hours.do(self.run_task)
        # schedule.every().day.at("09:00").do(self.run_task)

        while True:
            schedule.run_pending()
            time.sleep(1)

if __name__ == "__main__":
    daemon = PetCrawlerDaemon()
    daemon.start_daemon()