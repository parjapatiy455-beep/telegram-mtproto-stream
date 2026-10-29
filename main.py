import os
import sys
import time
import shutil
import hashlib
import logging
import platform
import urllib.parse
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Response, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

from config import Config
from bot import get_client, start_client, stop_client, get_channel_files, delete_channel_file, human_readable_size
from db import save_file_record
import bot as bot_module
from streamer import stream_telegram_file

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")

TEMP_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "temp_uploads")
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

START_TIME = time.time()

def make_session_token(password: str) -> str:
    salt = Config.SECRET_KEY
    return hashlib.sha256(f"{password}:{salt}".encode()).hexdigest()

def is_admin_request(request: Request) -> bool:
    token = request.cookies.get("admin_session") or request.headers.get("X-Admin-Token")
    expected = make_session_token(Config.ADMIN_PASSWORD)
    return token == expected

def require_admin(request: Request):
    if not is_admin_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized. Please log in as admin.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing server...")
    success, msg = await start_client()
    if success:
        logger.info(f"✅ Telegram Client initialized: {msg}")
    else:
        logger.warning(f"⚠️ Telegram client not connected: {msg}")

    yield

    logger.info("Shutting down server...")
    await stop_client()
    logger.info("Server shutdown complete.")

app = FastAPI(title="Telegram MTProto Stream & Storage Server", lifespan=lifespan)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ============================================================
# Web Page Routes
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    tg_client = get_client()
    is_connected = bool(tg_client and tg_client.is_connected())
    is_admin = is_admin_request(request)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "base_url": Config.BASE_URL,
            "bot_connected": is_connected,
            "is_admin": is_admin,
            "bot_username": bot_module.bot_me.username if bot_module.bot_me else None
        }
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_admin_request(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "base_url": Config.BASE_URL}
    )


# ============================================================
# Authentication APIs
# ============================================================
class LoginRequest(BaseModel):
    password: str

@app.post("/api/login")
async def api_login(data: LoginRequest, response: Response):
    if data.password == Config.ADMIN_PASSWORD:
        token = make_session_token(Config.ADMIN_PASSWORD)
        response.set_cookie(
            key="admin_session",
            value=token,
            httponly=True,
            max_age=86400 * 30, # 30 days
            samesite="lax"
        )
        return {"success": True, "token": token}
    raise HTTPException(status_code=401, detail="Invalid admin password")


@app.post("/api/logout")
async def api_logout(response: Response):
    response.delete_cookie(key="admin_session")
    return {"success": True}


@app.get("/api/auth/me")
async def api_auth_me(request: Request):
    return {"authenticated": is_admin_request(request)}


# ============================================================
# Admin Management APIs
# ============================================================
@app.get("/api/admin/files")
async def api_admin_files(request: Request, limit: int = 50):
    require_admin(request)
    files = await get_channel_files(limit=limit)
    return {"files": files, "count": len(files)}


@app.delete("/api/admin/files/{msg_id}")
async def api_admin_delete_file(request: Request, msg_id: int):
    require_admin(request)
    deleted = await delete_channel_file(msg_id)
    if deleted:
        return {"success": True, "msg_id": msg_id}
    raise HTTPException(status_code=500, detail="Failed to delete message from Telegram channel")


class SettingsUpdate(BaseModel):
    api_id: str | None = None
    api_hash: str | None = None
    bot_token: str | None = None
    bin_channel: str | None = None
    base_url: str | None = None
    admin_password: str | None = None

@app.get("/api/admin/settings")
async def api_admin_get_settings(request: Request):
    require_admin(request)
    # Mask bot_token and api_hash for privacy
    masked_token = (Config.BOT_TOKEN[:6] + "..." + Config.BOT_TOKEN[-4:]) if len(Config.BOT_TOKEN) > 10 else ""
    masked_hash = (Config.API_HASH[:4] + "..." + Config.API_HASH[-4:]) if len(Config.API_HASH) > 8 else ""

    return {
        "api_id": Config.API_ID if Config.API_ID else "",
        "api_hash_masked": masked_hash,
        "bot_token_masked": masked_token,
        "bin_channel": Config.BIN_CHANNEL if Config.BIN_CHANNEL else "",
        "base_url": Config.BASE_URL,
        "is_configured": len(Config.validate()) == 0
    }


@app.post("/api/admin/settings")
async def api_admin_update_settings(request: Request, data: SettingsUpdate):
    require_admin(request)
    updates = {}
    if data.api_id is not None and data.api_id.strip():
        updates["API_ID"] = data.api_id.strip()
    if data.api_hash is not None and data.api_hash.strip():
        updates["API_HASH"] = data.api_hash.strip()
    if data.bot_token is not None and data.bot_token.strip():
        updates["BOT_TOKEN"] = data.bot_token.strip()
    if data.bin_channel is not None and data.bin_channel.strip():
        updates["BIN_CHANNEL"] = data.bin_channel.strip()
    if data.base_url is not None and data.base_url.strip():
        updates["BASE_URL"] = data.base_url.strip().rstrip("/")
    if data.admin_password is not None and data.admin_password.strip():
        updates["ADMIN_PASSWORD"] = data.admin_password.strip()

    Config.save_to_env(updates)

    # Reconnect telegram client with updated settings
    success, msg = await start_client()

    return {
        "success": True,
        "reconnected": success,
        "message": msg
    }


@app.post("/api/admin/reconnect")
async def api_admin_reconnect(request: Request):
    require_admin(request)
    success, msg = await start_client()
    return {"success": success, "message": msg}


@app.get("/api/admin/stats")
async def api_admin_stats(request: Request):
    require_admin(request)
    tg_client = get_client()
    is_connected = bool(tg_client and tg_client.is_connected())
    uptime_sec = int(time.time() - START_TIME)
    uptime_human = f"{uptime_sec // 3600}h {(uptime_sec % 3600) // 60}m {uptime_sec % 60}s"

    return {
        "status": "online",
        "uptime": uptime_human,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "telegram_connected": is_connected,
        "bot_username": bot_module.bot_me.username if bot_module.bot_me else None,
        "bot_id": bot_module.bot_me.id if bot_module.bot_me else None,
        "bin_channel": Config.BIN_CHANNEL
    }


# ============================================================
# File Upload & Streaming Endpoints
# ============================================================
@app.get("/api/status")
async def get_status():
    tg_client = get_client()
    is_connected = bool(tg_client and tg_client.is_connected())
    return {
        "status": "online",
        "telegram_connected": is_connected,
        "bot_username": bot_module.bot_me.username if bot_module.bot_me else None,
        "bin_channel": Config.BIN_CHANNEL
    }


@app.post("/api/upload")
async def upload_file_api(file: UploadFile = File(...)):
    tg_client = get_client()
    if not tg_client or not tg_client.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Telegram MTProto client is not connected. Please configure your credentials in the Admin Dashboard."
        )

    file_path = os.path.join(TEMP_UPLOAD_DIR, file.filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Uploading {file.filename} to Telegram Storage Channel {Config.BIN_CHANNEL}...")
        sent_msg = await tg_client.send_file(
            Config.BIN_CHANNEL,
            file_path,
            caption=f"📁 Uploaded via Web: `{file.filename}`",
            force_document=False
        )
        logger.info(f"File uploaded. Saved message ID: {sent_msg.id}")

        msg_id = sent_msg.id
        file_name = file.filename
        file_size = os.path.getsize(file_path)

        encoded_name = urllib.parse.quote(file_name)
        watch_url = f"{Config.BASE_URL}/watch/{msg_id}"
        stream_url = f"{Config.BASE_URL}/stream/{msg_id}/{encoded_name}"
        download_url = f"{Config.BASE_URL}/download/{msg_id}/{encoded_name}"
        embed_url = f"{Config.BASE_URL}/embed/{msg_id}"

        # Save to persistent database
        save_file_record(msg_id, {
            "id": msg_id,
            "name": file_name,
            "size": file_size,
            "size_human": human_readable_size(file_size),
            "mime_type": sent_msg.file.mime_type if sent_msg.file else "application/octet-stream",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "is_video": (sent_msg.file.mime_type or "").startswith("video/"),
            "stream_url": stream_url,
            "watch_url": watch_url,
            "download_url": download_url,
            "embed_url": embed_url
        })

        return {
            "success": True,
            "msg_id": msg_id,
            "file_name": file_name,
            "file_size": file_size,
            "file_size_human": human_readable_size(file_size),
            "watch_url": watch_url,
            "stream_url": stream_url,
            "download_url": download_url,
            "embed_url": embed_url
        }
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass


@app.get("/watch/{msg_id}", response_class=HTMLResponse)
async def watch_page(request: Request, msg_id: int):
    tg_client = get_client()
    if not tg_client or not tg_client.is_connected():
        raise HTTPException(status_code=503, detail="Telegram client not connected")

    try:
        msg = await tg_client.get_messages(Config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch file: {e}")

    if not msg or not msg.file:
        raise HTTPException(status_code=404, detail="File not found")

    file_name = msg.file.name or f"video_{msg_id}.mp4"
    file_size = msg.file.size or 0
    mime_type = msg.file.mime_type or "video/mp4"

    encoded_name = urllib.parse.quote(file_name)
    stream_url = f"{Config.BASE_URL}/stream/{msg_id}/{encoded_name}"
    download_url = f"{Config.BASE_URL}/download/{msg_id}/{encoded_name}"
    embed_url = f"{Config.BASE_URL}/embed/{msg_id}"

    return templates.TemplateResponse(
        request=request,
        name="player.html",
        context={
            "file_name": file_name,
            "file_size_human": human_readable_size(file_size),
            "mime_type": mime_type,
            "stream_url": stream_url,
            "download_url": download_url,
            "embed_url": embed_url
        }
    )


@app.get("/embed/{msg_id}", response_class=HTMLResponse)
async def embed_page(request: Request, msg_id: int):
    tg_client = get_client()
    if not tg_client or not tg_client.is_connected():
        raise HTTPException(status_code=503, detail="Telegram client not connected")

    try:
        msg = await tg_client.get_messages(Config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch file: {e}")

    if not msg or not msg.file:
        raise HTTPException(status_code=404, detail="File not found")

    file_name = msg.file.name or f"video_{msg_id}.mp4"
    mime_type = msg.file.mime_type or "video/mp4"
    encoded_name = urllib.parse.quote(file_name)
    stream_url = f"{Config.BASE_URL}/stream/{msg_id}/{encoded_name}"

    return templates.TemplateResponse(
        request=request,
        name="embed.html",
        context={
            "file_name": file_name,
            "mime_type": mime_type,
            "stream_url": stream_url
        }
    )


@app.get("/stream/{msg_id}")
@app.get("/stream/{msg_id}/{file_name:path}")
async def stream_endpoint(request: Request, msg_id: int, file_name: str = ""):
    tg_client = get_client()
    if not tg_client or not tg_client.is_connected():
        raise HTTPException(status_code=503, detail="Telegram client not connected")

    return await stream_telegram_file(request, tg_client, msg_id, as_attachment=False)


@app.get("/download/{msg_id}")
@app.get("/download/{msg_id}/{file_name:path}")
async def download_endpoint(request: Request, msg_id: int, file_name: str = ""):
    tg_client = get_client()
    if not tg_client or not tg_client.is_connected():
        raise HTTPException(status_code=503, detail="Telegram client not connected")

    return await stream_telegram_file(request, tg_client, msg_id, as_attachment=True)


if __name__ == "__main__":
    port_str = (
        os.environ.get("PORT") or 
        os.environ.get("SERVER_PORT") or 
        os.environ.get("APP_PORT") or 
        str(Config.PORT or 8000)
    )
    port = int(port_str.strip())
    print(f"[*] Starting Server on 0.0.0.0:{port}...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
