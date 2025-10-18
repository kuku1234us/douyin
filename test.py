import asyncio, os
from typing import List
import httpx
from urllib.parse import urlencode

from crawlers.hybrid.hybrid_crawler import HybridCrawler
from crawlers.douyin.web.web_crawler import DouyinWebCrawler
from crawlers.douyin.web.models import UserPost
from crawlers.douyin.web.endpoints import DouyinAPIEndpoints
from crawlers.douyin.web.utils import BogusManager, TokenManager
from crawlers.base_crawler import BaseCrawler


# Set this to the Douyin user profile URL whose latest videos you want to download
userurl = "https://www.douyin.com/user/MS4wLjABAAAAuUo73Q5TQdi1N0sSi-kNcLeWpPg99gs1vOcdlTJm1s0"


async def find_aweme_items_in_response(response_dict: dict) -> List[dict]:
    """
    Try to locate the list of post dictionaries in the API response.
    We prefer keys that contain items with an 'aweme_id' field.
    """
    if not isinstance(response_dict, dict):
        return []

    # Common Douyin key
    aweme_list = response_dict.get("aweme_list")
    if isinstance(aweme_list, list) and aweme_list:
        return aweme_list

    # Fallback: search any list of dicts that has 'aweme_id'
    for key, value in response_dict.items():
        if isinstance(value, list) and value and isinstance(value[0], dict) and "aweme_id" in value[0]:
            return value
    return []


async def fetch_latest_aweme_ids_for_user(user_url: str, target_video_count: int = 3, ms_token: str | None = None) -> List[str]:
    """
    Resolve sec_user_id from profile URL, then fetch recent posts and return up to
    target_video_count aweme_ids (we’ll filter to videos later).
    """
    douyin = DouyinWebCrawler()
    sec_user_id = await douyin.get_sec_user_id(user_url)

    # Request more than needed to account for photo posts; adjust if necessary
    count_to_fetch = max(target_video_count * 3, 20)

    # Build endpoint with a real msToken to avoid empty responses
    kwargs = await douyin.get_douyin_headers()
    headers = kwargs["headers"]
    proxies = kwargs["proxies"]

    # Fallback: generate one if not provided
    if not ms_token:
        ms_token = TokenManager.gen_real_msToken()

    params_dict = UserPost(sec_user_id=sec_user_id, max_cursor=0, count=count_to_fetch).dict()
    params_dict["msToken"] = ms_token
    a_bogus = BogusManager.ab_model_2_endpoint(params_dict, headers["User-Agent"]) 
    endpoint = f"{DouyinAPIEndpoints.USER_POST}?{urlencode(params_dict)}&a_bogus={a_bogus}"

    base_crawler = BaseCrawler(proxies=proxies, crawler_headers=headers)
    async with base_crawler as crawler:
        response = await crawler.fetch_get_json(endpoint)
    items = await find_aweme_items_in_response(response)
    aweme_ids: List[str] = []
    for item in items:
        aweme_id = item.get("aweme_id") or item.get("awemeId")
        if isinstance(aweme_id, str):
            aweme_ids.append(aweme_id)
    return aweme_ids


async def fetch_minimal_video_data(hybrid: HybridCrawler, aweme_id: str) -> dict | None:
    """Return minimal hybrid data for a Douyin aweme_id, or None if not a video/unsupported."""
    url = f"https://www.douyin.com/video/{aweme_id}"
    data = await hybrid.hybrid_parsing_single_video(url, minimal=True)
    if data.get("platform") != "douyin" or data.get("type") != "video":
        return None
    return data


async def download_douyin_aweme_id(aweme_id: str, headers: dict, hybrid: HybridCrawler, with_watermark: bool = False, output_directory: str = ".") -> str | None:
    data = await fetch_minimal_video_data(hybrid, aweme_id)
    if not data:
        return None

    video_data = data["video_data"]
    video_url = video_data["wm_video_url_HQ"] if with_watermark else video_data["nwm_video_url_HQ"]
    filename = f"douyin_{aweme_id}{'_wm' if with_watermark else ''}.mp4"
    os.makedirs(output_directory, exist_ok=True)
    filepath = os.path.join(output_directory, filename)

    if os.path.exists(filepath):
        return filepath

    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=60) as client:
        async with client.stream("GET", video_url) as response:
            response.raise_for_status()
            with open(filepath, "wb") as file_handle:
                async for chunk in response.aiter_bytes():
                    file_handle.write(chunk)
    return filepath


async def main():
    # Configuration
    download_limit = 3
    with_watermark = False
    output_directory = "downloads"

    hybrid = HybridCrawler()
    douyin_headers = (await hybrid.DouyinWebCrawler.get_douyin_headers())["headers"]

    # Generate a fresh msToken for listing posts
    ms_token = TokenManager.gen_real_msToken()

    aweme_ids = await fetch_latest_aweme_ids_for_user(user_url=userurl, target_video_count=download_limit, ms_token=ms_token)

    # Download only videos; try in order and stop after we have download_limit successful video files
    downloaded_files: List[str] = []
    semaphore = asyncio.Semaphore(3)

    async def guarded_download(one_aweme_id: str):
        async with semaphore:
            return await download_douyin_aweme_id(
                aweme_id=one_aweme_id,
                headers=douyin_headers,
                hybrid=hybrid,
                with_watermark=with_watermark,
                output_directory=output_directory,
            )

    for aweme_id in aweme_ids:
        if len(downloaded_files) >= download_limit:
            break
        result_path = await guarded_download(aweme_id)
        if isinstance(result_path, str):
            downloaded_files.append(result_path)

    # If initial batch didn’t yield enough due to non-video posts, attempt pagination or notify
    if len(downloaded_files) < download_limit:
        print(f"Downloaded {len(downloaded_files)} files; some recent posts may be photos or unavailable.")
    for path in downloaded_files:
        print(f"Saved: {os.path.abspath(path)}")


if __name__ == "__main__":
    asyncio.run(main())