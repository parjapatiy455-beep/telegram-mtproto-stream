# 🚀 Telegram MTProto File Storage & Video Streaming Server

Ye ek high-performance **Telegram MTProto File Storage aur Video Streaming Server** hai jo Telegram ke unlimited cloud storage ko as a backend use karta hai. Isme ek **Admin Web Dashboard** diya gaya hai jisse aap browser se hi login karke settings, files, aur streaming manage kar sakte hain.

---

## 🌟 Key Features

1. **⚡ Real-Time Video Streaming (HTTP 206 Range Requests):**
   - Video bina download hue turant stream hoti hai.
   - Forward/rewind (seeking) buffer-free kaam karta hai.
2. **🔐 Admin Web Dashboard & File Manager:**
   - Web panel se **Admin Login** karein (Default: `admin123`).
   - Stored files browse karein, search karein, stream karein ya delete karein.
   - **Settings Manager:** Server ko restart kiye bina web dashboard se `API_ID`, `BOT_TOKEN`, `BIN_CHANNEL` update karein.
   - **Server Health:** CPU, OS, Uptime aur Telegram Bot status live dekhein.
3. **📁 Unlimited Telegram Cloud Storage:**
   - 2GB (Telegram Free) ya 4GB (Telegram Premium) tak ki files ek baar me upload karein.
4. **🤖 Telegram Bot Integration:**
   - Bot par koi bhi video/document forward karein, bot turant **Stream Link**, **Embed Code**, aur **Download Link** generate karke dega.
5. **💻 Website Embedding (Iframe & HTML5 Video):**
   - Ready-made `<iframe>` embed code aur `<video>` tag jo kisi bhi website me directly paste ho sakta hai.
6. **🐳 Botkeep & Docker Ready:**
   - `Dockerfile` aur `Procfile` pre-configured hain jisse Botkeep, Koyeb, Render, VPS ya Docker par 1-click deploy ho sakta hai.

---

## 📁 Project Structure

```
mp proto/
│
├── .env.example          # Sample environment credentials
├── config.py             # Configuration with dynamic env update & safe int
├── bot.py                # Telegram MTProto client, channel explorer & bot listener
├── streamer.py           # Core HTTP Range streaming engine
├── main.py               # FastAPI application, auth & web routes
├── requirements.txt      # Python dependencies
├── Dockerfile            # Docker container config for Botkeep/Cloud
├── Procfile              # PaaS process file (web: python main.py)
├── .dockerignore         # Docker ignore rules
├── .gitignore            # Git ignore rules (secrets protected)
│
├── templates/            # HTML Web Templates
│   ├── index.html        # Tabbed Dashboard (Files, Upload, Settings, Stats)
│   ├── login.html        # Admin authentication page
│   ├── player.html       # Video Player with metadata & controls
│   └── embed.html        # Clean iframe video player for external websites
│
└── static/               # Assets
    ├── style.css         # Modern Dark Glassmorphism CSS
    └── script.js         # Tab switching, file explorer, settings & upload JS
```

---

## 🛠️ Botkeep / Cloud Deployment Guide

Aap is project ko **Botkeep** ya kisi bhi cloud platform (Render, Koyeb, Railway, VPS) par aasani se deploy kar sakte hain.

### Step 1: GitHub Par Upload Karein
1. GitHub par ek **New Repository** banayein (e.g. `telegram-mtproto-stream`).
2. Apne computer me terminal khol kar ye commands run karein:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Telegram MTProto Stream Server"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

### Step 2: Botkeep / Cloud Server Par Deploy Karein
1. Botkeep dashboard me login karein.
2. **New App / Project** create karein aur apna GitHub repo connect karein.
3. Build pack me **Docker** ya **Python** select karein (repo me `Dockerfile` aur `Procfile` already included hain).
4. Environment Variables me aap ye daal sakte hain (ya baad me Web Dashboard se direct set kar sakte hain):
   - `PORT`: `8000`
   - `ADMIN_PASSWORD`: `ApnaSecretPassword`
   - `BASE_URL`: `https://your-botkeep-app-url.com`
   - `API_ID`: `12345678`
   - `API_HASH`: `your_api_hash`
   - `BOT_TOKEN`: `your_bot_token`
   - `BIN_CHANNEL`: `-1001234567890`
5. **Deploy** par click karein!

---

## 🖥️ Web Dashboard Se Login & Manage Karna

Deploy hone ke baad aapko terminal ya code chhoone ki zaroorat nahi hai:
1. Apni website open karein: `https://your-domain.com/login`
2. Default password: **`admin123`**
3. Login karne ke baad:
   - **📂 File Explorer:** Telegram storage channel me stored files ki list dekhein, search karein, stream karein ya delete karein.
   - **⚙️ Settings & Credentials:** Agar aapne environment variables nahi daale the, toh yahan se `API_ID`, `BOT_TOKEN`, `BIN_CHANNEL` daal kar **Save & Connect** dabayein. MTProto turant live connect ho jayega!
   - **📊 Server Stats:** Bot status, username, uptime aur system health monitor karein.

---

## 🌐 Website Par Video Stream Kaise Karein

### Option 1: `<iframe>` Embed (Sabse Aasan)
```html
<iframe 
    src="https://your-domain.com/embed/123" 
    width="100%" 
    height="480" 
    frameborder="0" 
    allowfullscreen>
</iframe>
```

### Option 2: HTML5 `<video>` Tag
```html
<video controls width="100%" preload="metadata">
    <source src="https://your-domain.com/stream/123/myvideo.mp4" type="video/mp4">
    Your browser does not support the video tag.
</video>
```
