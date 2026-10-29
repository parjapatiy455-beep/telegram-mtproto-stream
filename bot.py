import logging
from datetime import datetime
from telethon import TelegramClient, events, types, Button
from config import Config
from db import load_files_db, save_file_record, delete_file_record

logger = logging.getLogger("telegram_bot")

client = None
bot_me = None

def get_client():
    global client
    if not Config.API_ID or not Config.API_HASH:
        return None
    if client is None:
        try:
            client = TelegramClient('stream_bot', Config.API_ID, Config.API_HASH)
        except Exception as e:
            logger.error(f"Error initializing TelegramClient: {e}")
            return None
    return client

async def start_client():
    global client, bot_me
    missing = Config.validate()
    if missing:
        logger.warning(f"Cannot start bot, missing config: {missing}")
        return False, f"Missing configuration: {', '.join(missing)}"

    try:
        if client and client.is_connected():
            await client.disconnect()

        client = TelegramClient('stream_bot', Config.API_ID, Config.API_HASH)
        await client.start(bot_token=Config.BOT_TOKEN)
        setup_bot_handlers(client)
        bot_me = await client.get_me()
        logger.info(f"Bot connected successfully as @{bot_me.username}")
        return True, f"Connected as @{bot_me.username}"
    except Exception as e:
        logger.error(f"Error starting client: {e}", exc_info=True)
        return False, str(e)

async def stop_client():
    global client, bot_me
    if client:
        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            pass
    bot_me = None

def human_readable_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def setup_bot_handlers(tg_client: TelegramClient):
    @tg_client.on(events.NewMessage(pattern="/start"))
    async def start_handler(event):
        sender = await event.get_sender()
        name = sender.first_name if sender else "User"
        welcome_text = (
            f"👋 **Namaste {name}!**\n\n"
            f"Main aapka **MTProto File Storage aur Video Streaming Bot** hoon.\n\n"
            f"⚡ **Aap kya kar sakte hain:**\n"
            f"1. Mujhe koi bhi **Video ya File** send ya forward karein.\n"
            f"2. File Telegram ke private cloud storage me save ho jayegi.\n"
            f"3. Aapko instant **High-Speed Stream Link**, **Web Video Player Link**, aur **Download Link** mil jayega!\n\n"
            f"🌐 **Web Dashboard:** [Open Dashboard]({Config.BASE_URL})\n\n"
            f"Bhejiye koi video/document test karne ke liye!"
        )
        buttons = [
            [Button.url("🌐 Open Web Dashboard", Config.BASE_URL)]
        ]
        await event.reply(welcome_text, buttons=buttons, link_preview=False)

    @tg_client.on(events.NewMessage(func=lambda e: e.is_private and e.media))
    async def media_handler(event):
        # Ensure only authorized users if ADMINS is configured
        if Config.ADMINS and event.sender_id not in Config.ADMINS:
            await event.reply("⚠️ Aap is bot ko use karne ke liye authorized nahi hain.")
            return

        status_msg = await event.reply("⏳ File process ho rahi hai, Telegram storage channel me save kiya ja raha hai...")

        try:
            # Forward the media to storage BIN_CHANNEL
            saved_msg = await tg_client.send_message(
                Config.BIN_CHANNEL,
                message=event.message
            )

            file_name = "file"
            file_size = 0
            mime_type = "application/octet-stream"

            if saved_msg.file:
                file_name = saved_msg.file.name or f"file_{saved_msg.id}.dat"
                file_size = saved_msg.file.size or 0
                mime_type = saved_msg.file.mime_type or "application/octet-stream"

            # Construct URLs
            watch_url = f"{Config.BASE_URL}/watch/{saved_msg.id}"
            stream_url = f"{Config.BASE_URL}/stream/{saved_msg.id}/{file_name}"
            download_url = f"{Config.BASE_URL}/download/{saved_msg.id}/{file_name}"
            embed_url = f"{Config.BASE_URL}/embed/{saved_msg.id}"

            # Save to persistent files DB
            save_file_record(saved_msg.id, {
                "id": saved_msg.id,
                "name": file_name,
                "size": file_size,
                "size_human": human_readable_size(file_size),
                "mime_type": mime_type,
                "date": saved_msg.date.strftime("%Y-%m-%d %H:%M:%S") if saved_msg.date else "",
                "is_video": mime_type.startswith("video/"),
                "stream_url": stream_url,
                "watch_url": watch_url,
                "download_url": download_url,
                "embed_url": embed_url
            })

            reply_text = (
                f"✅ **File Successfully Stored!**\n\n"
                f"📁 **Name:** `{file_name}`\n"
                f"📦 **Size:** `{human_readable_size(file_size)}`\n"
                f"🏷️ **Type:** `{mime_type}`\n\n"
                f"🔗 **Direct Links:**\n"
                f"🎬 **Watch Online:** {watch_url}\n"
                f"📥 **Fast Download:** {download_url}\n"
                f"⚡ **Direct Stream:** `{stream_url}`\n\n"
                f"💻 **Website Embed Code (iframe):**\n"
                f"`<iframe src=\"{embed_url}\" width=\"100%\" height=\"450\" frameborder=\"0\" allowfullscreen></iframe>`"
            )

            buttons = [
                [Button.url("▶️ Watch Online", watch_url), Button.url("📥 Download", download_url)],
                [Button.url("🌐 Web Dashboard", Config.BASE_URL)]
            ]

            await status_msg.edit(reply_text, buttons=buttons, link_preview=False)
        except Exception as e:
            logger.error(f"Error handling media: {e}", exc_info=True)
            await status_msg.edit(f"❌ Error aayi: `{str(e)}`\nKripya check karein ki Bot aapke BIN_CHANNEL me Admin hai ya nahi.")

async def get_channel_files(limit: int = 50):
    tg_client = get_client()
    db_records = load_files_db()
    files_map = {int(k): v for k, v in db_records.items()}

    # Scan and discover recent Telegram channel messages by ID
    if tg_client and tg_client.is_connected() and Config.BIN_CHANNEL:
        try:
            highest_id = max(files_map.keys()) if files_map else 1
            # Scan a healthy range of recent IDs to discover existing files
            search_ids = list(range(1, max(highest_id + 10, 30)))
            missing_ids = [mid for mid in search_ids if mid not in files_map]

            if missing_ids:
                msgs = await tg_client.get_messages(Config.BIN_CHANNEL, ids=missing_ids)
                if not isinstance(msgs, list):
                    msgs = [msgs]
                for msg in msgs:
                    if msg and msg.file:
                        f_name = msg.file.name or f"file_{msg.id}.dat"
                        f_size = msg.file.size or 0
                        m_type = msg.file.mime_type or "application/octet-stream"
                        d_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else ""
                        rec = {
                            "id": msg.id,
                            "name": f_name,
                            "size": f_size,
                            "size_human": human_readable_size(f_size),
                            "mime_type": m_type,
                            "date": d_str,
                            "is_video": m_type.startswith("video/"),
                            "stream_url": f"{Config.BASE_URL}/stream/{msg.id}/{f_name}",
                            "watch_url": f"{Config.BASE_URL}/watch/{msg.id}",
                            "download_url": f"{Config.BASE_URL}/download/{msg.id}/{f_name}",
                            "embed_url": f"{Config.BASE_URL}/embed/{msg.id}"
                        }
                        files_map[msg.id] = rec
                        save_file_record(msg.id, rec)
        except Exception as e:
            logger.error(f"Error scanning channel files: {e}", exc_info=True)

    sorted_files = sorted(files_map.values(), key=lambda x: x.get("id", 0), reverse=True)
    return sorted_files[:limit]

async def delete_channel_file(msg_id: int) -> bool:
    delete_file_record(msg_id)
    tg_client = get_client()
    if not tg_client or not tg_client.is_connected():
        return True
    try:
        await tg_client.delete_messages(Config.BIN_CHANNEL, [msg_id])
        return True
    except Exception as e:
        logger.error(f"Error deleting message {msg_id}: {e}")
        return True
