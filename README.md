# 股息投資組合追蹤 — 網頁版（Alpha Vantage）

可在手機／任何電腦開啟。使用 **Alpha Vantage 免費 API** 更新股價與派息資料。

---

## 重要限制（請先看）

| 項目 | 說明 |
|------|------|
| 免費額度 | 約 **25 次請求／天** |
| 每次更新 | 每檔股票約用 **2 次** 請求（價格 + 派息） |
| 建議 | 一次最多 8 檔，每天更新 1～2 次即可 |
| 市場支援 | **美股最完整**；港股／台股常無資料或不完整 |

---

## 一、取得免費 API Key（必做）

1. 打開：https://www.alphavantage.co/support/#api-key
2. 輸入簡單資料（或用 Google 登入）
3. 立刻拿到一組 API Key（一串英數字）
4. **複製保存**，等等要貼到 Render

---

## 二、更新程式碼到 GitHub

把新的這些檔案覆蓋上傳到你的 GitHub 倉庫：

- `app.py`（已改為 Alpha Vantage）
- `requirements.txt`
- `templates/index.html`
- `Procfile`、`runtime.txt`（可維持不動）

上傳方式與之前相同（Add file → Upload files，或 Create new file 覆蓋）。

---

## 三、在 Render 設定 API Key

1. 打開 Render 控制台：https://dashboard.render.com
2. 點你的 Web Service（dividend-tracker-gah7）
3. 左側選 **Environment**
4. 點 **Add Environment Variable**
5. 填寫：
   - **Key**：`ALPHA_VANTAGE_API_KEY`
   - **Value**：你剛才申請到的 API Key
6. 儲存後，Render 會自動重新部署一次

---

## 四、使用方式

1. 打開：https://dividend-tracker-gah7.onrender.com
2. 輸入美股代號、股數、成本
3. 點「更新股價與派息」
4. 第一次可能要等服務醒來（20～60 秒）

---

## 本機測試

```bash
export ALPHA_VANTAGE_API_KEY=你的Key
cd dividend_web
pip install -r requirements.txt
python app.py
```

---

## 檔案

```
dividend_web/
├── app.py
├── requirements.txt
├── Procfile
├── runtime.txt
├── templates/index.html
└── README.md
```
