import logging
import re
import urllib.parse
from datetime import datetime
from telethon import TelegramClient, events, types, Button
from config import Config
from db import load_files_db, save_file_record, delete_file_record

logger = logging.getLogger("telegram_bot")

client = None
bot_me = None
recently_forwarded_ids = set()


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
        bot_me = await client.get_me()
        setup_bot_handlers(client)
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


def is_bin_channel(chat_id: int) -> bool:
    """Checks whether the given chat_id matches the configured BIN_CHANNEL."""
    if not Config.BIN_CHANNEL or not chat_id:
        return False
    try:
        bin_id = int(Config.BIN_CHANNEL)
        c_id = int(chat_id)
        if bin_id == c_id:
            return True
        bin_str = str(bin_id).replace("-100", "").replace("-", "")
        c_str = str(c_id).replace("-100", "").replace("-", "")
        return bin_str == c_str
    except Exception:
        return False


def make_file_links(msg_id: int, file_name: str, file_size: int, mime_type: str, date_str: str = None):
    """
    Constructs URLs, saves record into database, and prepares formatted message with buttons.
    """
    encoded_name = urllib.parse.quote(file_name)
    watch_url = f"{Config.BASE_URL}/watch/{msg_id}"
    stream_url = f"{Config.BASE_URL}/stream/{msg_id}/{encoded_name}"
    download_url = f"{Config.BASE_URL}/download/{msg_id}/{encoded_name}"
    embed_url = f"{Config.BASE_URL}/embed/{msg_id}"

    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save to persistent files DB
    save_file_record(msg_id, {
        "id": msg_id,
        "name": file_name,
        "size": file_size,
        "size_human": human_readable_size(file_size),
        "mime_type": mime_type,
        "date": date_str,
        "is_video": (mime_type or "").startswith("video/"),
        "stream_url": stream_url,
        "watch_url": watch_url,
        "download_url": download_url,
        "embed_url": embed_url
    })

    reply_text = (
        f"✅ **Stream Links Ready!**\n\n"
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

    return reply_text, buttons


def setup_bot_handlers(tg_client: TelegramClient):
    global bot_me

    # ============================================================
    # 1. /start & /help Command Handler
    # ============================================================
    @tg_client.on(events.NewMessage(pattern=r"(?i)^(/|\!|\.)?(start|help)$"))
    async def start_handler(event):
        sender = await event.get_sender()
        name = sender.first_name if sender else "User"
        welcome_text = (
            f"👋 **Namaste {name}!**\n\n"
            f"Main aapka **MTProto File Storage aur Video Streaming Bot** hoon.\n\n"
            f"⚡ **Features & Usage:**\n"
            f"1. **Direct DM:** Mujhe koi bhi video ya file send ya forward karein.\n"
            f"2. **Channel Post:** Storage channel me kuch bhi upload ya forward karein — links turant generate ho jayenge!\n"
            f"3. **Reply Tagging:** Kisi bhi video/file ko **Reply** karke `link` ya `/link` likhein — bot uska stream link de dega!\n"
            f"4. **Quick ID:** `/link <id>` (jaise `/link 9`) likhkar kisi bhi file ka link le sakte hain.\n\n"
            f"🌐 **Web Dashboard:** [Open Dashboard]({Config.BASE_URL})"
        )
        buttons = [
            [Button.url("🌐 Open Web Dashboard", Config.BASE_URL)]
        ]
        await event.reply(welcome_text, buttons=buttons, link_preview=False)

    # ============================================================
    # 2. Tag / Reply with "link" or "/link" or "/link <id>"
    # ============================================================
    @tg_client.on(events.NewMessage(pattern=r"(?i)^(/|\!|\.)?links?(\s+\d+)?$"))
    async def link_command_handler(event):
        # Ignore messages sent by bot itself
        if bot_me and getattr(event, 'sender_id', None) == bot_me.id:
            return

        # Case A: User replied to a message
        if event.is_reply:
            target_msg = await event.get_reply_message()
            if not target_msg or not target_msg.media:
                await event.reply("⚠️ **Media Nahi Mila:**\nAapne jis message ko reply kiya hai usme koi video ya file nahi hai. Kripya kisi video/file ko reply (tag) karke `link` likhein.")
                return

            status_msg = await event.reply("⏳ Stream links generate kiye ja rahe hain...")

            try:
                # If message is already in BIN_CHANNEL
                if is_bin_channel(event.chat_id):
                    msg_id = target_msg.id
                else:
                    # Forward to BIN_CHANNEL storage
                    saved_msg = await tg_client.send_message(
                        Config.BIN_CHANNEL,
                        message=target_msg
                    )
                    recently_forwarded_ids.add(saved_msg.id)
                    msg_id = saved_msg.id

                file_name = "file"
                file_size = 0
                mime_type = "application/octet-stream"
                if target_msg.file:
                    file_name = target_msg.file.name or f"file_{msg_id}.dat"
                    file_size = target_msg.file.size or 0
                    mime_type = target_msg.file.mime_type or "application/octet-stream"

                d_str = target_msg.date.strftime("%Y-%m-%d %H:%M:%S") if target_msg.date else ""
                reply_text, buttons = make_file_links(msg_id, file_name, file_size, mime_type, d_str)
                await status_msg.edit(reply_text, buttons=buttons, link_preview=False)
            except Exception as e:
                logger.error(f"Error handling reply link: {e}", exc_info=True)
                await status_msg.edit(f"❌ Error aayi: `{str(e)}`")
            return

        # Case B: User specified message ID directly: /link <id> or link <id>
        text_parts = event.raw_text.strip().split()
        if len(text_parts) > 1 and text_parts[1].isdigit():
            target_id = int(text_parts[1])
            status_msg = await event.reply(f"⏳ File ID `{target_id}` check ki ja rahi hai...")
            try:
                msg = await tg_client.get_messages(Config.BIN_CHANNEL, ids=target_id)
                if not msg or not msg.file:
                    await status_msg.edit(f"⚠️ Message ID `{target_id}` storage channel me nahi mila ya usme koi media nahi hai.")
                    return

                file_name = msg.file.name or f"file_{msg.id}.dat"
                file_size = msg.file.size or 0
                mime_type = msg.file.mime_type or "application/octet-stream"
                d_str = msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else ""

                reply_text, buttons = make_file_links(msg.id, file_name, file_size, mime_type, d_str)
                await status_msg.edit(reply_text, buttons=buttons, link_preview=False)
            except Exception as e:
                logger.error(f"Error fetching msg {target_id}: {e}", exc_info=True)
                await status_msg.edit(f"❌ Error aayi: `{str(e)}`")
            return

        # Case C: User simply typed "link" without replying or providing an ID
        usage_guide = (
            "💡 **Links Kaise Banayein:**\n\n"
            "1. Kisi bhi video ya file ko **Reply (Tag)** karein aur likhein `link` ya `/link`.\n"
            "2. Ya fir `/link <id>` likhein (Jaise: `/link 9`).\n"
            "3. Ya seedha mujhe koi bhi video/file forward karein!"
        )
        await event.reply(usage_guide)

    # ============================================================
    # 3. Direct Channel Upload / Forward Auto-Link Handler
    # ============================================================
    @tg_client.on(events.NewMessage)
    async def channel_media_handler(event):
        # Only process messages inside the BIN_CHANNEL with media
        if not is_bin_channel(event.chat_id) or not event.media:
            return

        # Ignore messages sent by the bot itself
        if bot_me and getattr(event, 'sender_id', None) == bot_me.id:
            return

        # Ignore messages forwarded by the bot from private chats
        if event.id in recently_forwarded_ids:
            recently_forwarded_ids.discard(event.id)
            return

        file_name = "file"
        file_size = 0
        mime_type = "application/octet-stream"
        if event.file:
            file_name = event.file.name or f"file_{event.id}.dat"
            file_size = event.file.size or 0
            mime_type = event.file.mime_type or "application/octet-stream"

        d_str = event.date.strftime("%Y-%m-%d %H:%M:%S") if event.date else ""

        try:
            reply_text, buttons = make_file_links(event.id, file_name, file_size, mime_type, d_str)
            # Reply to the uploaded/forwarded message directly in the channel
            await event.reply(reply_text, buttons=buttons, link_preview=False)
            logger.info(f"Auto-generated stream links for Channel message {event.id}: {file_name}")
        except Exception as e:
            logger.error(f"Error replying in channel for msg {event.id}: {e}", exc_info=True)

    # ============================================================
    # 4. Private DM Upload / Forward Media Handler
    # ============================================================
    @tg_client.on(events.NewMessage(func=lambda e: e.is_private and e.media))
    async def private_media_handler(event):
        # Check authorization if ADMINS is configured
        if Config.ADMINS and event.sender_id not in Config.ADMINS:
            await event.reply("⚠️ Aap is bot ko use karne ke liye authorized nahi hain.")
            return

        # Skip if message text is already handled as link command
        if event.raw_text and re.match(r"(?i)^(/|\!|\.)?links?(\s+\d+)?$", event.raw_text.strip()):
            return

        status_msg = await event.reply("⏳ File process ho rahi hai, Telegram storage channel me save kiya ja raha hai...")

        try:
            # Forward the media to storage BIN_CHANNEL
            saved_msg = await tg_client.send_message(
                Config.BIN_CHANNEL,
                message=event.message
            )
            recently_forwarded_ids.add(saved_msg.id)

            file_name = "file"
            file_size = 0
            mime_type = "application/octet-stream"

            if saved_msg.file:
                file_name = saved_msg.file.name or f"file_{saved_msg.id}.dat"
                file_size = saved_msg.file.size or 0
                mime_type = saved_msg.file.mime_type or "application/octet-stream"

            d_str = saved_msg.date.strftime("%Y-%m-%d %H:%M:%S") if saved_msg.date else ""
            reply_text, buttons = make_file_links(saved_msg.id, file_name, file_size, mime_type, d_str)

            await status_msg.edit(reply_text, buttons=buttons, link_preview=False)
            logger.info(f"Processed private media message, saved as ID {saved_msg.id}: {file_name}")
        except Exception as e:
            logger.error(f"Error handling private media: {e}", exc_info=True)
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
                        encoded_f_name = urllib.parse.quote(f_name)
                        rec = {
                            "id": msg.id,
                            "name": f_name,
                            "size": f_size,
                            "size_human": human_readable_size(f_size),
                            "mime_type": m_type,
                            "date": d_str,
                            "is_video": m_type.startswith("video/"),
                            "stream_url": f"{Config.BASE_URL}/stream/{msg.id}/{encoded_f_name}",
                            "watch_url": f"{Config.BASE_URL}/watch/{msg.id}",
                            "download_url": f"{Config.BASE_URL}/download/{msg.id}/{encoded_f_name}",
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
