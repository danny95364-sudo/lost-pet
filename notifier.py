
import requests
import json

# 設定 - 在實際部屬時建議移至環境變數
DISCORD_WEBHOOK_URL = ""  # 使用者需填入自己的 Webhook
LINE_NOTIFY_TOKEN = ""    # 使用者需填入自己的 Token

def send_notification(pet_data, platform='all'):
    """
    發送新走失案件通知
    """
    message = f"🚨 【急尋】{pet_data['PetName']} ({pet_data['PetType']})\n" \
              f"📅 時間: {pet_data['LostTime']}\n" \
              f"📍 地點: {pet_data['LostPlace']}\n" \
              f"🐶 品種: {pet_data['Breed']} / {pet_data['Color']}\n" \
              f"📞 聯絡: {pet_data['OwnerName']} {pet_data['Phone']}\n" \
              f"🖼 照片: {pet_data['Picture']}"

    if platform in ['discord', 'all'] and DISCORD_WEBHOOK_URL:
        _send_discord(message, pet_data['Picture'])
        
    if platform in ['line', 'all'] and LINE_NOTIFY_TOKEN:
        _send_line(message, pet_data['Picture'])

def _send_discord(text, image_url):
    try:
        payload = {
            "content": text,
            "embeds": [{
                "image": {"url": image_url}
            }]
        }
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"❌ Discord 發送失敗: {e}")

def _send_line(text, image_url):
    try:
        headers = {"Authorization": "Bearer " + LINE_NOTIFY_TOKEN}
        payload = {"message": text, "imageThumbnail": image_url, "imageFullsize": image_url}
        requests.post("https://notify-api.line.me/api/notify", headers=headers, data=payload)
    except Exception as e:
        print(f"❌ LINE 發送失敗: {e}")

if __name__ == "__main__":
    # Test
    fake_pet = {
        "PetName": "測試狗狗", "PetType": "狗",
        "LostTime": "2023-10-01", "LostPlace": "測試地點",
        "Breed": "柴犬", "Color": "黃色",
        "OwnerName": "王大明", "Phone": "0912345678",
        "Picture": "https://via.placeholder.com/300"
    }
    print("發送測試通知...")
    send_notification(fake_pet)
