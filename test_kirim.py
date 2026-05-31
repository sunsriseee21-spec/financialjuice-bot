import requests

BOT_TOKEN = "8921896859:AAF7biUHKm_sD5rdpVvB9ybnxMYXCzvfozk"
CHAT_ID = "-1003890278221"
THREAD_ID = 11480

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHAT_ID,
    "message_thread_id": THREAD_ID,
    "text": "🤖 TEST - Bot berhasil!"
}

response = requests.post(url, json=payload)
print(response.status_code)
print(response.text)
