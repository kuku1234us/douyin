from __future__ import annotations

from typing import Dict, Iterable

import browser_cookie3

from crawlers.douyin.web.web_crawler import DouyinWebCrawler


class FirefoxDouyinWebCrawler(DouyinWebCrawler):
    async def get_douyin_headers(self):
        """
        Use base headers/proxies from YAML, but replace Cookie with a live Firefox cookie.
        Falls back to YAML Cookie if Firefox cookie retrieval fails.
        """
        base = await super().get_douyin_headers()
        headers = dict(base.get("headers", {}))
        try:
            cookie_header = self._build_cookie_header(
                self._load_firefox_cookies(['.douyin.com', 'douyin.com', 'www.douyin.com'])
            )
            if cookie_header:
                headers['Cookie'] = cookie_header
        except Exception:
            # Keep YAML cookie on any failure
            pass
        return {"headers": headers, "proxies": base.get("proxies")}

    @staticmethod
    def _load_firefox_cookies(domains: Iterable[str]) -> Dict[str, str]:
        cookies: Dict[str, str] = {}
        for domain in domains:
            try:
                jar = browser_cookie3.firefox(domain_name=domain)
            except Exception:
                continue
            for c in jar:
                cookies[c.name] = c.value
        return cookies

    @staticmethod
    def _build_cookie_header(cookies: Dict[str, str]) -> str:
        if not cookies:
            return ""
        return "; ".join([f"{k}={v}" for k, v in cookies.items()])


