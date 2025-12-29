# Introduction

If cookie in crawlers/douyin/web/config.yaml is not updated, 抖音 may return empty response to try to block bots.

# Updating Cookie

1. Open Firefox browser and login to 抖音

   - In **Network**, Turn on “Disable Cache” (optional but helps), then refresh the page (Ctrl+R).
   - Click the **trash can / Clear** button (or right-click the list → **Clear**).

2. **Filter to only Douyin + only “document”**

   - In the filter box (“Filter URLs”), type:

     ```
     www.douyin.com
     ```

   - Then click the **Type** filter for **HTML / Doc / document** (Firefox shows it as **HTML**).
   - Goal: you only see 1–3 entries, not hundreds.

3. **Reload once**

   - Press **Ctrl+R** (keep DevTools open).

4. **Click the page’s main request**

   - In the filtered list, click the request whose **Type** is **document/HTML** and whose URL looks like:

     - `/user/self?...` (your profile page)
     - or just `www.douyin.com/`

5. **Copy the Cookie**

   - Right panel → **Headers** tab
   - Scroll to **Request Headers** → find **Cookie**
   - **Right-click the Cookie value → Copy Value**
   - **name=value** pair. Remove any prefix from cookie that is not in the format of a "name=value" pair.

That copied string (the whole `a=b; c=d; ...`) is what goes into:

```yaml
TokenManager:
  douyin:
    headers:
      Cookie: "PASTE_HERE"
```

---

### If you still see too many even after filtering

Use one of these “nuclear” options:

**Option A: Pause recording, then reload**

- Click the **recording dot** (so it stops recording), **Clear**, then **start recording again**, then reload.

**Option B (often easiest): Copy as cURL**

- Right-click the **document** request → **Copy → Copy as cURL**
- Paste it into a text editor and search for:

  ```
  -H 'cookie:
  ```

- Copy everything after `cookie:` as your Cookie header value.

---
