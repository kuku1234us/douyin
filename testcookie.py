import sys
from typing import Iterable, Dict
from pathlib import Path

import browser_cookie3
import yaml


def load_cookies_from_firefox(domains: Iterable[str]) -> Dict[str, str]:
    cookies: Dict[str, str] = {}
    for domain in domains:
        try:
            jar = browser_cookie3.firefox(domain_name=domain)
        except Exception:
            continue
        for c in jar:
            # Last one wins for duplicate names
            cookies[c.name] = c.value
    return cookies


def build_cookie_header(cookies: Dict[str, str]) -> str:
    if not cookies:
        return ""
    parts = [f"{name}={value}" for name, value in cookies.items()]
    return "; ".join(parts)


def main() -> int:
    # Try common Douyin domains
    domains = [".douyin.com", "douyin.com", "www.douyin.com"]
    cookies = load_cookies_from_firefox(domains)
    header = build_cookie_header(cookies)
    if not header:
        print("No Douyin cookies found in Firefox. Ensure you're logged in and Firefox is closed, then try again.")
        return 1
    print(header)

    # Update crawlers/douyin/web/config.yaml with the new Cookie
    try:
        project_root = Path(__file__).resolve().parent
        cfg_path = project_root / "crawlers" / "douyin" / "web" / "config.yaml"
        if not cfg_path.exists():
            print(f"Config not found at: {cfg_path}")
            return 0
        with open(cfg_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        # Navigate and set cookie
        tm = data.setdefault('TokenManager', {}).setdefault('douyin', {})
        headers = tm.setdefault('headers', {})
        headers['Cookie'] = header
        with open(cfg_path, 'w', encoding='utf-8') as f:
            # Force very wide width so the Cookie stays on a single line
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=1000000)
        print(f"Updated Cookie in {cfg_path}")
    except Exception as e:
        print(f"Failed to update config: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


