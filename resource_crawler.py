
import pandas as pd
import requests
import io
import os
import urllib3
from db import upsert_clinic, init_db

# 關閉 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class PetResourcesCrawlerV11:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        init_db()

    def fetch_data_robust(self, url, name, target_columns_keywords):
        """
        最強韌的抓取函式 (V9核心)：同時支援 JSON/CSV，並具備自動欄位清洗功能
        """
        print(f"📥 正在下載【{name}】...")
        try:
            # 嘗試加入 &IsOD=1 參數，有時候能抓到更多資料
            if "?" in url:
                url += "&IsOD=1"
            else:
                url += "?IsOD=1"

            response = requests.get(url, headers=self.headers, verify=False, timeout=30)
            
            df = pd.DataFrame()
            is_json = False

            # 1. 嘗試當作 JSON 解析
            try:
                content_start = response.content[:10].decode('utf-8', errors='ignore').strip()
                if content_start.startswith('[') or content_start.startswith('{'):
                    json_data = response.json()
                    df = pd.DataFrame(json_data)
                    is_json = True
            except:
                pass

            # 2. 如果失敗，嘗試當作 CSV 解析
            if not is_json or df.empty:
                content = response.content
                encodings = ['utf-8', 'utf-8-sig', 'big5', 'cp950']
                for enc in encodings:
                    try:
                        df = pd.read_csv(io.StringIO(content.decode(enc)), on_bad_lines='skip')
                        if not df.empty and len(df.columns) > 1:
                            break
                    except:
                        continue

            if df.empty:
                print(f"   ❌ {name} 讀取失敗")
                return pd.DataFrame()

            # 清洗
            df.columns = df.columns.str.strip()
            final_col_map = {}
            for target_key, keywords in target_columns_keywords.items():
                for col in df.columns:
                    if any(k in col for k in keywords):
                        final_col_map[col] = target_key
                        break
            
            if not final_col_map:
                print(f"   ⚠️ {name} 欄位對應失敗")
                return pd.DataFrame()

            df.rename(columns=final_col_map, inplace=True)
            found_cols = [c for c in final_col_map.values() if c in df.columns]
            df = df[found_cols].fillna('')
            
            print(f"   ✅ 成功讀取 {len(df)} 筆原始資料")
            return df

        except Exception as e:
            print(f"   ❌ {name} 發生錯誤: {e}")
            return pd.DataFrame()

    def get_vet_clinics(self):
        url = "https://data.moa.gov.tw/Service/OpenData/DataFileService.aspx?UnitId=078"
        keywords = {"name": ["機構名稱"], "tel": ["電話"], "address": ["地址"], "doctor_name": ["獸醫", "負責人"]}

        df = self.fetch_data_robust(url, "動物醫院", keywords)

        if not df.empty:
            print(f"   🔨 正在生成 Google Maps 連結...")
            df['google_map_link'] = df.apply(
                lambda row: f"https://www.google.com/maps/search/?api=1&query={row['name']}", axis=1
            )
        return df

    def save_to_db(self, df, type_name):
        if df.empty:
            return
            
        print(f"   💾 正在存入資料庫 ({type_name})...")
        count = 0
        for _, row in df.iterrows():
            data = row.to_dict()
            if type_name == 'vet':
                upsert_clinic(data)
                count += 1
        print(f"   ✅ 已更新 {count} 筆 {type_name} 資料")


if __name__ == "__main__":
    crawler = PetResourcesCrawlerV11()
    print("=== 🚀 寵物資源爬蟲啟動 ===")

    # 1. 醫院
    df_vet = crawler.get_vet_clinics()
    crawler.save_to_db(df_vet, "vet")
    
    print("\n=== 🎉 資料更新完成 ===")