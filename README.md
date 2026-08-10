# 股息投資組合追蹤 — 網頁版

可在手機／任何電腦用瀏覽器開啟使用。支援自動更新股價、派息日期、金額與息率，並計算總投資與組合息率。

---

## 一、本機測試（可選）

```bash
cd dividend_web
pip install -r requirements.txt
python app.py
```

瀏覽器開啟：http://127.0.0.1:5000

---

## 二、部署到網路上（推薦：Render 免費）

完成後會得到類似 `https://你的名字.onrender.com` 的網址，手機、電腦都能開。

### 步驟 1：準備 GitHub

1. 到 [github.com](https://github.com) 註冊／登入
2. 新建一個 **Public** Repository（例如取名 `dividend-tracker`）
3. 把 `dividend_web` 資料夾裡的所有檔案上傳到這個 Repo  
   （可用 GitHub 網頁上傳，或用 Git 指令）

需要上傳的檔案：
- `app.py`
- `requirements.txt`
- `Procfile`
- `runtime.txt`
- `templates/index.html`
- `README.md`（可選）

### 步驟 2：在 Render 部署

1. 到 [render.com](https://render.com) 用 GitHub 帳號登入（免費用）
2. 點 **New +** → **Web Service**
3. 選擇你剛建好的 GitHub Repo
4. 設定如下：

| 欄位 | 填寫內容 |
|------|----------|
| Name | 隨意（例如 `dividend-tracker`） |
| Region | 選離你近的（Singapore 或 Oregon 都行） |
| Branch | `main`（或你的主分支） |
| Runtime | **Python 3** |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120` |
| Instance Type | **Free** |

5. 點 **Create Web Service**
6. 等 2～5 分鐘建置完成，會出現一個網址（例如 `https://dividend-tracker-xxxx.onrender.com`）

### 步驟 3：開始使用

用手機或電腦瀏覽器打開那個網址即可。

- 資料存在**你自己的瀏覽器**（LocalStorage），不會上傳到伺服器
- 換裝置／換瀏覽器需要重新輸入持股（或自己匯出後再貼）

---

## 注意事項（Render 免費方案）

- **閒置約 15 分鐘會休眠**，下次開啟可能要等 20～60 秒才會醒來（這是免費方案限制）
- 若需要「永遠不休眠」，可升級付費方案，或改用其他平台
- 一次最多查詢約 30 檔股票，避免請求過快被限制

---

## 其他可用的免費／便宜平台

| 平台 | 說明 |
|------|------|
| [Render](https://render.com) | 最簡單，本說明以此為主 |
| [Railway](https://railway.app) | 也很方便，有免費額度 |
| [PythonAnywhere](https://www.pythonanywhere.com) | 專為 Python 設計 |

---

## 檔案說明

```
dividend_web/
├── app.py              # Flask 後端 + 抓取 Yahoo Finance
├── requirements.txt    # 依賴套件
├── Procfile            # 給 Render / Heroku 用的啟動指令
├── runtime.txt         # 指定 Python 版本
├── templates/
│   └── index.html      # 前端介面
└── README.md
```

資料來源：Yahoo Finance（可能有延遲）。本工具僅供參考，不構成投資建議。
