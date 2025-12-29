from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

import httpx

from crawlers.douyin.web.web_crawler import DouyinWebCrawler
from douyin_app.models.firefox_douyin_crawler import FirefoxDouyinWebCrawler
from douyin_app.models.database import DatabaseManager


@dataclass
class ChannelTask:
    id: int
    url: str
    title: str
    sec_user_id: Optional[str]
    latest_download_unix: Optional[int]


async def build_headers(crawler: DouyinWebCrawler) -> dict:
    return (await crawler.get_douyin_headers())["headers"]


async def list_user_posts(
    crawler: DouyinWebCrawler,
    sec_user_id: str,
    since_unix: int,
    should_stop=None,
    progress=None,
) -> List[Tuple[str, int, int, int, Optional[str]]]:
    """
    Return list of (aweme_id, create_time, width, height, nwm_url) for items newer than since_unix.
    Stops early when reaching older items.
    """
    max_cursor = 0
    has_more = True
    results: List[Tuple[str, int, int, int, Optional[str]]] = []
    while has_more:
        if callable(should_stop) and should_stop():
            break
        # Try base crawler first; if it fails (anti-bot empty body), fall back to Firefox cookies
        try:
            resp = await crawler.fetch_user_post_videos(sec_user_id=sec_user_id, max_cursor=max_cursor, count=35)
        except Exception:
            resp = None
        if not resp:
            try:
                alt = FirefoxDouyinWebCrawler()
                resp = await alt.fetch_user_post_videos(sec_user_id=sec_user_id, max_cursor=max_cursor, count=35)
            except Exception:
                resp = None
        if not resp:
            raise RuntimeError("Douyin returned an empty response for USER_POST. Cookie/msToken likely invalid or blocked.")
        aweme_list = (resp or {}).get('aweme_list')
        if not aweme_list:
            # If we got a structured response but no list, treat as end-of-list.
            break
        for aweme in aweme_list:
            if callable(should_stop) and should_stop():
                break
            try:
                aweme_id = str(aweme.get('aweme_id'))
                ct = int(aweme.get('create_time') or 0)
                video = (aweme or {}).get('video') or {}
                width = int((video or {}).get('width') or 0)
                height = int((video or {}).get('height') or 0)
                play_addr = (video or {}).get('play_addr') or {}
                uri = play_addr.get('uri')
                nwm_url: Optional[str] = None
                if uri:
                    nwm_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={uri}&ratio=1080p&line=0"
                else:
                    url0 = (play_addr.get('url_list') or [None])[0]
                    if url0:
                        nwm_url = str(url0).replace('playwm', 'play')
            except Exception:
                continue
            if since_unix and ct and ct <= int(since_unix):
                has_more = False
                break
            results.append((aweme_id, ct, width, height, nwm_url))
        has_more_val = (resp or {}).get('has_more')
        has_more = bool(has_more_val) and (has_more_val != 0)
        max_cursor = int((resp or {}).get('max_cursor') or 0)
        if not has_more:
            break
    return results


async def resolve_sec_user_id(crawler: DouyinWebCrawler, url: str) -> Optional[str]:
    try:
        return await crawler.get_sec_user_id(url)
    except Exception:
        return None


async def download_aweme_video(
    base_headers: dict,
    base_dir: Path,
    aweme_id: str,
    create_time: int,
    width: int,
    height: int,
    nwm_url: Optional[str],
) -> int:
    """Download one aweme using provided URL/metadata; return create_time on success else 0."""
    try:
        if not nwm_url:
            return 0
        folder = 'landscape' if (width and height and width >= height) else 'portrait'
        target_dir = base_dir / folder
        filename = f"{create_time}_{aweme_id}.mp4"
        target_path = target_dir / filename
        if target_path.exists():
            return create_time
        # Try with base headers
        try:
            async with httpx.AsyncClient(headers=base_headers, follow_redirects=True, timeout=120) as client:
                r = await client.get(nwm_url)
                r.raise_for_status()
                if not r.content:
                    raise RuntimeError("empty content")
                with open(target_path, 'wb') as f:
                    f.write(r.content)
            return create_time
        except Exception:
            # Fallback to Firefox cookies
            try:
                alt_crawler = FirefoxDouyinWebCrawler()
                alt_headers = await build_headers(alt_crawler)
                async with httpx.AsyncClient(headers=alt_headers, follow_redirects=True, timeout=120) as client:
                    r = await client.get(nwm_url)
                    r.raise_for_status()
                    if not r.content:
                        return 0
                    with open(target_path, 'wb') as f:
                        f.write(r.content)
                return create_time
            except Exception:
                return 0
    except Exception:
        return 0


async def download_channel_new_items(
    working_dir: Path,
    task: ChannelTask,
    max_concurrency: int,
    should_stop=None,
    progress=None,
) -> None:
    """
    Download new items for a channel and update latest timestamp in DB.
    """
    base_dir = working_dir
    (base_dir / 'portrait').mkdir(parents=True, exist_ok=True)
    (base_dir / 'landscape').mkdir(parents=True, exist_ok=True)

    crawler = DouyinWebCrawler()
    headers = await build_headers(crawler)

    sec = task.sec_user_id or await resolve_sec_user_id(crawler, task.url)
    last_ts = None
    if sec:
        last_ts = DatabaseManager.get_latest_download_unix_by_secuid(working_dir, sec)
    if last_ts is None:
        last_ts = DatabaseManager.get_latest_download_unix_by_url(working_dir, task.url) or 0

    to_download = await list_user_posts(crawler, sec_user_id=sec, since_unix=int(last_ts or 0), should_stop=should_stop, progress=progress) if sec else []
    if not to_download:
        return

    sem = asyncio.Semaphore(max(1, int(max_concurrency)))

    async def bounded_download(aweme_id: str, ct: int, w: int, h: int, url: Optional[str]) -> int:
        if callable(should_stop) and should_stop():
            return 0
        async with sem:
            return await download_aweme_video(headers, base_dir, aweme_id, ct, w, h, url)

    tasks = [bounded_download(aid, ct, w, h, url) for (aid, ct, w, h, url) in to_download]
    results: List[int] = []
    try:
        # Chunk to allow cooperative cancellation/progress updates
        chunk_size = 10
        for i in range(0, len(tasks)):
            if callable(should_stop) and should_stop():
                break
            res = await tasks[i]
            if isinstance(res, int):
                results.append(res)
            if callable(progress):
                try:
                    msg = f"Downloaded {min(i+1, len(tasks))}/{len(tasks)} for {task.title or task.url}"
                    print(f"[download_workers] {msg}")
                    progress(msg)
                except Exception:
                    pass
    except Exception:
        pass
    final_ts = max([int(last_ts or 0)] + [ts for ts in results if isinstance(ts, int)] + [ct for (_, ct, *_rest) in to_download])
    if sec:
        DatabaseManager.set_latest_download_unix_by_secuid(working_dir, sec, final_ts)
    else:
        DatabaseManager.set_latest_download_unix_by_url(working_dir, task.url, final_ts)


