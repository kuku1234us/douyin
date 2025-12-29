from __future__ import annotations

"""
Count total number of published videos for a Douyin user URL.

Run:
  python count_user_videos.py
"""

import asyncio
from typing import Optional, Tuple

from crawlers.douyin.web.web_crawler import DouyinWebCrawler


# Hardcoded target channel URL for convenience
CHANNEL_URL = "https://www.douyin.com/user/MS4wLjABAAAAkE8F-tN4K_kZnkRI8_udCDU_IdY28aLOgMf_fuzJc18"


async def count_user_videos(url: str) -> Tuple[str, int, Optional[int]]:
    """
    Returns (sec_user_id, counted_total, profile_aweme_count_if_available)
    """
    crawler = DouyinWebCrawler()

    # Resolve sec_user_id from profile URL
    sec_user_id = await crawler.get_sec_user_id(url)
    if not sec_user_id:
        raise RuntimeError("Failed to resolve sec_user_id from URL")

    # Optional: also fetch profile to read 'aweme_count' for comparison
    profile_aweme_count: Optional[int] = None
    try:
        profile = await crawler.handler_user_profile(sec_user_id)
        user_obj = (profile or {}).get('user') or {}
        if isinstance(user_obj, dict):
            val = user_obj.get('aweme_count')
            if isinstance(val, int):
                profile_aweme_count = val
    except Exception:
        pass

    # Page through posts until has_more is false
    total = 0
    seen = set()
    max_cursor = 0
    while True:
        resp = await crawler.fetch_user_post_videos(sec_user_id=sec_user_id, max_cursor=max_cursor, count=35)
        aweme_list = (resp or {}).get('aweme_list') or []
        for aweme in aweme_list:
            aweme_id = str((aweme or {}).get('aweme_id') or '')
            if aweme_id and aweme_id not in seen:
                seen.add(aweme_id)
        total = len(seen)
        has_more = (resp or {}).get('has_more')
        new_cursor = int((resp or {}).get('max_cursor') or 0)
        if not has_more or new_cursor == max_cursor:
            break
        max_cursor = new_cursor

    return sec_user_id, total, profile_aweme_count


def main() -> int:
    sec_user_id, counted, aweme_count = asyncio.run(count_user_videos(CHANNEL_URL))
    print(f"sec_user_id: {sec_user_id}")
    if aweme_count is not None:
        print(f"profile.aweme_count: {aweme_count}")
    print(f"counted (via paging): {counted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


