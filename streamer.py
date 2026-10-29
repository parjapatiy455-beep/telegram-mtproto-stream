import os
import re
import logging
import asyncio
import urllib.parse
from typing import AsyncGenerator
from fastapi import Request, HTTPException, Response
from fastapi.responses import StreamingResponse
from telethon import TelegramClient
from config import Config
from bot import human_readable_size

logger = logging.getLogger("streamer")

ALIGNMENT_BYTES = 4096  # Telegram MTProto offset must be a multiple of 4KB


def format_content_disposition(disposition: str, file_name: str, msg_id: int, mime_type: str) -> str:
    """
    Format Content-Disposition safely for HTTP/1.1 and modern browsers (RFC 6266 / RFC 5987).
    Standard HTTP headers strictly reject non-Latin-1 characters (such as Hindi or emojis).
    We provide an ASCII safe fallback filename for older tools, and a UTF-8 percent-encoded
    filename* parameter so browsers download with the exact original Unicode name.
    """
    # 1. ASCII fallback name
    safe_ascii = re.sub(r'[^a-zA-Z0-9_\.-]', '_', file_name)
    safe_ascii = re.sub(r'_+', '_', safe_ascii).strip('_.')

    ext = os.path.splitext(file_name)[1]
    if not ext:
        ext = ".mp4" if (mime_type and mime_type.startswith("video/")) else ".dat"

    if not safe_ascii:
        safe_ascii = f"file_{msg_id}{ext}"
    elif not safe_ascii.lower().endswith(ext.lower()):
        safe_ascii = f"{safe_ascii}{ext}"

    # 2. RFC 5987 UTF-8 encoded filename for modern browsers
    encoded_name = urllib.parse.quote(file_name, encoding='utf-8')

    return f"{disposition}; filename=\"{safe_ascii}\"; filename*=UTF-8''{encoded_name}"


async def byte_range_generator(
    client: TelegramClient,
    media,
    start: int,
    end: int,
    part_size: int = Config.CHUNK_SIZE
) -> AsyncGenerator[bytes, None]:
    """
    Yields slices of chunks from Telegram MTProto to serve exact HTTP byte ranges.
    Offsets are aligned to 4KB (4096 bytes) to adhere strictly to Telegram MTProto specifications.
    """
    aligned_start = (start // ALIGNMENT_BYTES) * ALIGNMENT_BYTES
    skip_bytes = start - aligned_start
    total_needed = (end - start) + 1
    bytes_sent = 0

    try:
        async for chunk in client.iter_download(
            media,
            offset=aligned_start,
            request_size=part_size,
            limit=(skip_bytes + total_needed)
        ):
            # Skip unneeded prefix bytes from the 4KB alignment
            if skip_bytes > 0:
                if len(chunk) <= skip_bytes:
                    skip_bytes -= len(chunk)
                    continue
                else:
                    chunk = chunk[skip_bytes:]
                    skip_bytes = 0

            if not chunk:
                continue

            # Ensure we do not send more than requested
            remaining = total_needed - bytes_sent
            if len(chunk) > remaining:
                chunk = chunk[:remaining]

            bytes_sent += len(chunk)
            yield chunk

            if bytes_sent >= total_needed:
                break
    except (asyncio.CancelledError, ConnectionResetError):
        # Client closed tab or scrubbed playback
        return
    except Exception as e:
        logger.error(f"Error streaming from MTProto: {e}")
        raise


async def stream_telegram_file(
    request: Request,
    client: TelegramClient,
    msg_id: int,
    as_attachment: bool = False
):
    """
    Fetches message from the Telegram Storage Channel, parses HTTP Range headers,
    and returns a StreamingResponse with 206 Partial Content or 200 OK.
    """
    try:
        msg = await client.get_messages(Config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        logger.error(f"Failed to retrieve message {msg_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch file from Telegram storage")

    if not msg or not msg.file:
        raise HTTPException(status_code=404, detail="File not found or message has no media")

    file_size = msg.file.size or 0
    file_name = msg.file.name or f"file_{msg_id}.dat"
    mime_type = msg.file.mime_type or "application/octet-stream"

    # Default disposition
    disposition = "attachment" if as_attachment else "inline"
    content_disposition = format_content_disposition(disposition, file_name, msg_id, mime_type)

    range_header = request.headers.get("range", "").strip()

    if range_header.startswith("bytes="):
        # Handle Partial Content (Range Request)
        range_value = range_header.replace("bytes=", "").strip()
        parts = range_value.split("-")

        try:
            if not parts[0]:
                # Suffix range: bytes=-500 (last 500 bytes)
                suffix_length = int(parts[1])
                start = max(0, file_size - suffix_length)
                end = file_size - 1
            else:
                start = int(parts[0])
                end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Range header")

        if start >= file_size or start > end:
            return Response(
                status_code=416,  # Range Not Satisfiable
                headers={"Content-Range": f"bytes */{file_size}"}
            )

        end = min(end, file_size - 1)
        content_length = (end - start) + 1

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
            "Content-Disposition": content_disposition,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "max-age=3600, public",
        }

        return StreamingResponse(
            byte_range_generator(client, msg.media, start, end),
            status_code=206,
            headers=headers,
            media_type=mime_type
        )
    else:
        # Full content request
        headers = {
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Content-Type": mime_type,
            "Content-Disposition": content_disposition,
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "max-age=3600, public",
        }

        return StreamingResponse(
            byte_range_generator(client, msg.media, 0, file_size - 1),
            status_code=200,
            headers=headers,
            media_type=mime_type
        )
