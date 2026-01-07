
import requests
import urllib3
import pandas as pd
from datetime import datetime
import time

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MOAClient:
    def __init__(self):
        # 農業部走失動物 API
        self.url = "https://data.moa.gov.tw/Service/OpenData/TransService.aspx?UnitId=IFJomqVzyB0i"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def fetch_all_lost_pets(self, limit=2000):
        """
        抓取最新走失資料
        :param limit: 抓取筆數上限
        :return: List of clean dictionaries
        """
        print(f"[{datetime.now()}] 📥 [Fetcher] 開始抓取農業部資料 (Limit={limit})...")
        
        all_data = []
        skip = 0
        batch_size = 1000
        
        while True:
            if skip >= limit:
                break
                
            params = {"$top": batch_size, "$skip": skip}
            try:
                response = requests.get(self.url, headers=self.headers, params=params, verify=False, timeout=30)
                data = response.json()
                
                if not data:
                    break
                    
                all_data.extend(data)
                skip += batch_size
                time.sleep(0.5) # 禮貌性暫停
            except Exception as e:
                print(f"   ❌ 抓取錯誤 (Skip={skip}): {e}")
                break
        
        print(f"   ✅ 共抓取 {len(all_data)} 筆原始資料，開始清洗...")
        return self._clean_data(all_data)

    def _clean_data(self, raw_data):
        if not raw_data:
            return []

        df = pd.DataFrame(raw_data)
        
        # 1. 欄位重新命名 (統一英文字段)
        col_map = {
            "晶片號碼": "ChipNum",
            "寵物名": "PetName",
            "寵物別": "PetType",
            "性別": "Sex",
            "品種": "Breed",
            "毛色": "Color",
            "遺失時間": "LostTime",
            "遺失地點": "LostPlace",
            "飼主姓名": "OwnerName",
            "連絡電話": "Phone",
            "PICTURE": "Picture"
        }
        
        # 處理有些欄位名稱可能帶有空白的情況
        df.columns = df.columns.str.strip()
        # 只改名我們有定義的，其他保留或忽略
        df.rename(columns=col_map, inplace=True)
        
        # 2. 補全必要欄位
        required_cols = ["ChipNum", "PetName", "LostTime", "Picture"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = "" # 補空字串
        
        # 3. 欄位值清洗
        df['ChipNum'] = df['ChipNum'].fillna('').astype(str).str.strip()
        df['PetName'] = df['PetName'].fillna('未知').astype(str).str.strip()
        df['UniqueKey'] = df['ChipNum'] + "_" + df['PetName'] # 產生唯一鍵值
        
        # 時間格式標準化 (嘗試轉為 YYYY-MM-DD format)
        df['LostTime'] = df['LostTime'].apply(self._parse_date)
        
        # 4. 排序 (最新的在前)
        df = df.sort_values(by='LostTime', ascending=False)
        
        # 轉回 List of Dict
        clean_list = df.to_dict(orient='records')
        return clean_list

    def _parse_date(self, date_str):
        if pd.isna(date_str) or str(date_str).strip() == '':
            return ""
            
        s = str(date_str).strip().replace(".", "/").replace("-", "/")
        try:
            # 嘗試解析正常格式
            dt = pd.to_datetime(s, errors='coerce')
            if pd.notna(dt):
                return dt.strftime('%Y-%m-%d')
        except:
            pass
            
        # 處理民國年 (e.g. 112/01/01)
        try:
            parts = s.split('/')
            if len(parts) == 3:
                year = int(parts[0])
                if year < 1911: 
                    year += 1911
                return f"{year}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        except:
            pass
            
        return ""

if __name__ == "__main__":
    # Test Run
    client = MOAClient()
    data = client.fetch_all_lost_pets(limit=100)
    print(f"Top 1 Result: {data[0] if data else 'None'}")
