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


async def list_user_posts(crawler: DouyinWebCrawler, sec_user_id: str, since_unix: int, should_stop=None, progress=None) -> List[Tuple[str, int]]:
    """
    Return list of (aweme_id, create_time) for items newer than since_unix.
    Stops early when reaching older items.
    """
    max_cursor = 0
    has_more = True
    results: List[Tuple[str, int]] = []
    while has_more:
        if callable(should_stop) and should_stop():
            break
        resp = await crawler.fetch_user_post_videos(sec_user_id=sec_user_id, max_cursor=max_cursor, count=20)
        aweme_list = (resp or {}).get('aweme_list')
        if not aweme_list:
            break
        for aweme in aweme_list:
            if callable(should_stop) and should_stop():
                break
            try:
                aweme_id = str(aweme.get('aweme_id'))
                ct = int(aweme.get('create_time') or 0)
            except Exception:
                continue
            if since_unix and ct and ct <= int(since_unix):
                has_more = False
                break
            results.append((aweme_id, ct))
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
    crawler: DouyinWebCrawler,
    headers: dict,
    base_dir: Path,
    aweme_id: str,
    create_time: int,
) -> int:
    """Download one aweme; return create_time on success else 0."""
    try:
        detail_resp = await crawler.fetch_one_video(aweme_id)
        detail = detail_resp.get('aweme_detail') or detail_resp
        video = (detail or {}).get('video', {})
        width = int(video.get('width') or 0)
        height = int(video.get('height') or 0)
        uri = (video.get('play_addr') or {}).get('uri')
        nwm_url = None
        if uri:
            nwm_url = f"https://aweme.snssdk.com/aweme/v1/play/?video_id={uri}&ratio=1080p&line=0"
        else:
            url0 = (video.get('play_addr') or {}).get('url_list', [None])[0]
            if url0:
                nwm_url = url0.replace('playwm', 'play')
        if not nwm_url:
            return 0
        folder = 'landscape' if (width and height and width >= height) else 'portrait'
        target_dir = base_dir / folder
        filename = f"{create_time}_{aweme_id}.mp4"
        target_path = target_dir / filename
        if target_path.exists():
            return create_time
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=120) as client:
            r = await client.get(nwm_url)
            r.raise_for_status()
            with open(target_path, 'wb') as f:
                f.write(r.content)
        return create_time
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

    crawler = FirefoxDouyinWebCrawler()
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

    async def bounded_download(aweme_id: str, ct: int) -> int:
        if callable(should_stop) and should_stop():
            return 0
        async with sem:
            return await download_aweme_video(crawler, headers, base_dir, aweme_id, ct)

    tasks = [bounded_download(aid, ct) for (aid, ct) in to_download]
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
    final_ts = max([int(last_ts or 0)] + [ts for ts in results if isinstance(ts, int)] + [ct for (_, ct) in to_download])
    if sec:
        DatabaseManager.set_latest_download_unix_by_secuid(working_dir, sec, final_ts)
    else:
        DatabaseManager.set_latest_download_unix_by_url(working_dir, task.url, final_ts)


