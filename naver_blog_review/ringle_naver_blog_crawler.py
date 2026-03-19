import re
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

import requests
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm


# ============================
# NAVER API CREDENTIALS (LOCAL ONLY)
# ============================
NAVER_CLIENT_ID = ""
NAVER_CLIENT_SECRET = ""


# ----------------------------
# Config
# ----------------------------
@dataclass
class CrawlerConfig:
    queries: List[str]

    # Blog Search API: query 당 최대 수집 개수(최대 1000까지 가능하지만 과도하면 차단/부하↑)
    max_results_per_query: int = 100

    # API display(한 번에 가져오는 개수): 10~100
    api_display: int = 30

    # 요청 간 sleep
    sleep_range: Tuple[float, float] = (0.8, 1.6)

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    out_csv: str = "naver_blog_ringle.csv"
    dedup_urls: bool = True
    min_text_len: int = 80
    ad_keywords: List[str] = None

    # API sort: "sim"(정확도), "date"(최신)
    api_sort: str = "sim"


DEFAULT_AD_KEYWORDS = ["협찬", "제공받아", "원고료", "파트너스", "광고", "소정의", "지원받아"]


# ----------------------------
# Helpers
# ----------------------------
def make_session(user_agent: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": user_agent,
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "*/*",
        "Connection": "keep-alive",
    })
    return s


def sleep_jitter(cfg: CrawlerConfig):
    time.sleep(random.uniform(*cfg.sleep_range))


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_probable_ad(text: str, ad_keywords: List[str]) -> bool:
    t = text.replace(" ", "")
    return any(k.replace(" ", "") in t for k in ad_keywords)


def strip_html(s: str) -> str:
    # API title/desc는 <b> 태그 들어있음
    return re.sub(r"<[^>]+>", "", s or "").strip()


def safe_get_json(resp: requests.Response) -> Optional[Dict]:
    try:
        return resp.json()
    except Exception:
        return None


# ----------------------------
# 1) Naver Blog Search API
# ----------------------------
def naver_blog_search_api(
    session: requests.Session,
    query: str,
    client_id: str,
    client_secret: str,
    display: int,
    start: int,
    sort: str
) -> Optional[Dict]:
    """
    네이버 Search API - blog.json
    """
    url = "https://openapi.naver.com/v1/search/blog.json"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {
        "query": query,
        "display": display,
        "start": start,     # 1~1000 (API 제한)
        "sort": sort,       # sim(정확도), date(최신)
    }

    resp = session.get(url, headers=headers, params=params, timeout=20)

    if resp.status_code != 200:
        data = safe_get_json(resp)
        print(f"[WARN] API status={resp.status_code} query='{query}' start={start} display={display}")
        if data:
            # 네이버 API 에러메시지 출력
            err_msg = data.get("errorMessage") or data.get("message") or str(data)
            print(f"[WARN] API error: {err_msg}")
        else:
            print("[WARN] API error: (no json body)")
        return None

    return safe_get_json(resp)


def collect_urls_via_api(session: requests.Session, query: str, cfg: CrawlerConfig) -> List[Dict]:
    """
    API로 안정적으로 링크 목록 수집
    """
    client_id = (NAVER_CLIENT_ID or "").strip()
    client_secret = (NAVER_CLIENT_SECRET or "").strip()

    if not client_id or not client_secret or "여기에" in client_id or "여기에" in client_secret:
        raise RuntimeError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 값이 비어있거나 기본값입니다.\n"
            "코드 상단의 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET을 본인 값으로 바꿔주세요."
        )

    results = []
    fetched = 0
    start = 1

    while fetched < cfg.max_results_per_query and start <= 1000:
        display = min(cfg.api_display, cfg.max_results_per_query - fetched)

        data = naver_blog_search_api(
            session=session,
            query=query,
            client_id=client_id,
            client_secret=client_secret,
            display=display,
            start=start,
            sort=cfg.api_sort
        )
        if not data or "items" not in data:
            break

        items = data.get("items", [])
        if not items:
            break

        for it in items:
            link = it.get("link", "")
            if "blog.naver.com" not in link and "m.blog.naver.com" not in link:
                continue

            results.append({
                "query": query,
                "url": link,
                "api_title": strip_html(it.get("title", "")),
                "api_desc": strip_html(it.get("description", "")),
                "api_blogger": it.get("bloggername", ""),
                "api_postdate": it.get("postdate", ""),  # yyyymmdd
            })

        fetched += len(items)
        start += len(items)
        sleep_jitter(cfg)

    return results


# ----------------------------
# 2) Blog content crawling (blog.naver.com)
# ----------------------------
def _get_soup(session: requests.Session, url: str) -> Optional[BeautifulSoup]:
    try:
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            return None
        return BeautifulSoup(resp.text, "lxml")
    except Exception:
        return None


def _resolve_mainframe_url(session: requests.Session, blog_url: str) -> Optional[str]:
    soup = _get_soup(session, blog_url)
    if soup is None:
        return None

    iframe = soup.find("iframe", id="mainFrame")
    if iframe and iframe.get("src"):
        src = iframe["src"]
        if src.startswith("http"):
            return src
        return "https://blog.naver.com" + src

    return blog_url


def _extract_title(soup: BeautifulSoup) -> str:
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return ""


def _extract_date(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", property="article:published_time")
    if meta and meta.get("content"):
        return meta["content"][:10]
    cand = soup.select_one("span.se_publishDate") or soup.select_one("span.date") or soup.select_one("time")
    return cand.get_text(" ", strip=True) if cand else ""


def _extract_author(soup: BeautifulSoup) -> str:
    meta = soup.find("meta", property="naverblog:nickname")
    if meta and meta.get("content"):
        return meta["content"].strip()
    cand = soup.select_one("span.nick")
    return cand.get_text(" ", strip=True) if cand else ""


def _extract_content_text(soup: BeautifulSoup) -> str:
    # 신형 스마트에디터
    container = soup.select_one("div.se-main-container")
    if container:
        return container.get_text(" ", strip=True)

    # 구형
    container = soup.select_one("div#postViewArea") or soup.select_one("div.post-view")
    if container:
        return container.get_text(" ", strip=True)

    # 기타 케이스
    container = soup.select_one("div._postViewArea")
    if container:
        return container.get_text(" ", strip=True)

    return ""


def crawl_blog_post(session: requests.Session, blog_url: str, cfg: CrawlerConfig) -> Dict:
    resolved_url = _resolve_mainframe_url(session, blog_url)
    if not resolved_url:
        return {"url": blog_url, "ok": False, "error": "resolve_failed"}

    soup = _get_soup(session, resolved_url)
    if soup is None:
        return {"url": blog_url, "resolved_url": resolved_url, "ok": False, "error": "request_failed"}

    title = _extract_title(soup)
    date = _extract_date(soup)
    author = _extract_author(soup)

    text = clean_text(_extract_content_text(soup))
    if len(text) < cfg.min_text_len:
        return {
            "url": blog_url,
            "resolved_url": resolved_url,
            "title": title,
            "date": date,
            "author": author,
            "text": text,
            "is_ad": is_probable_ad(text, cfg.ad_keywords),
            "ok": False,
            "error": "too_short_or_empty"
        }

    return {
        "url": blog_url,
        "resolved_url": resolved_url,
        "title": title,
        "date": date,
        "author": author,
        "text": text,
        "is_ad": is_probable_ad(text, cfg.ad_keywords),
        "ok": True,
        "error": ""
    }


# ----------------------------
# Main
# ----------------------------
def run(cfg: CrawlerConfig):
    if cfg.ad_keywords is None:
        cfg.ad_keywords = DEFAULT_AD_KEYWORDS

    session = make_session(cfg.user_agent)

    # 1) collect URLs via API
    url_rows = []
    for q in cfg.queries:
        url_rows.extend(collect_urls_via_api(session, q, cfg))

    if not url_rows:
        print("[WARN] API에서 URL을 못 받았습니다. (쿼리/인증키/호출 제한 확인)")
        return

    url_df = pd.DataFrame(url_rows)

    # dedup
    if cfg.dedup_urls:
        url_df = url_df.drop_duplicates(subset=["url"]).reset_index(drop=True)

    urls = url_df["url"].tolist()
    print(f"[INFO] Collected URLs via API: {len(urls)}")
    print("[DEBUG] first 5 URLs:", urls[:5])

    # 2) crawl each post
    rows = []
    for u in tqdm(urls, desc="Crawling posts"):
        row = crawl_blog_post(session, u, cfg)
        rows.append(row)
        sleep_jitter(cfg)

    df = pd.DataFrame(rows)

    # merge API meta
    out = url_df.merge(df, left_on="url", right_on="url", how="left")

    if out.empty:
        print("[WARN] No data collected. CSV is empty.")
        return

    out.to_csv(cfg.out_csv, index=False, encoding="utf-8-sig")
    print(f"[DONE] Saved: {cfg.out_csv}")

    if "ok" in out.columns:
        print(out["ok"].value_counts(dropna=False))
        if "error" in out.columns:
            print(out[out["ok"] == False]["error"].value_counts(dropna=False))


if __name__ == "__main__":
    config = CrawlerConfig(
        queries=[
            "링글 솔직 후기",
            "링글 영어회화 후기",
            "링글 가격 후기",
            "링글 추천 후기",
        ],
        max_results_per_query=80,
        api_display=30,
        out_csv="naver_blog_ringle.csv",
        min_text_len=80,
        sleep_range=(1.0, 2.0),
        api_sort="sim"  # 최신순이면 "date"
    )
    run(config)
