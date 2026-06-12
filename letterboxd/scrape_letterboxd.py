# -*- coding: utf-8 -*-
"""
Letterboxd 리뷰 수집기 — KPop Demon Hunters
================================================
목표: https://letterboxd.com/film/kpop-demon-hunters/reviews/ 의 영어 리뷰를
      'OLDER'(다음 페이지) 링크를 따라가며 최대 N개까지 수집한다.

설계 포인트(왜 이렇게 짰는가)
- Letterboxd의 'OLDER' 버튼은 결국 `<a class="next" href=".../page/2/">Older</a>`
  라는 '링크'다. 브라우저(Selenium) 없이 requests로 그 href를 그대로 따라가면
  버튼을 누르는 것과 동일하게 동작하며 훨씬 빠르고 안정적이다.
- 한 번에 1만 개는 시간이 오래 걸리고 중간에 끊길 수 있으므로
  (1) 진행상황 체크포인트 저장 → 재실행 시 이어받기(resume)
  (2) jsonl 스트리밍 저장(메모리 안전)
  (3) 429/5xx 재시도 + 지수 백오프 + 정중한 랜덤 딜레이
  를 모두 넣었다.
- 중복 리뷰는 review의 고유 id로 제거한다.

사용법
    pip install requests beautifulsoup4 lxml
    python scrape_letterboxd.py                 # 기본값으로 실행
    python scrape_letterboxd.py --target 10000  # 목표 개수 지정
    python scrape_letterboxd.py --sort by/activity   # 정렬 방식 변경

출력
    data/reviews_raw.jsonl   # 리뷰 1건 = 1줄(JSON): id, author, rating, date, text, url
    data/reviews_raw.csv     # 같은 내용 CSV
    data/_checkpoint.json    # 다음에 이어받을 페이지 URL/누적 개수

주의
    - 공개 페이지만 수집한다. robots/이용약관을 준수하고, 과도한 요청을 피하기 위해
      DELAY 값을 너무 낮추지 말 것(기본 1.5~3.0초 랜덤).
    - Letterboxd가 깊은 페이지네이션을 제한하면 'OLDER' 링크가 사라지며 그 시점에서
      정상 종료된다(사이트가 보유한 만큼만 수집됨).
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Iterator, Optional

import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# 설정 (필요하면 여기만 수정)
# ----------------------------------------------------------------------------
FILM_SLUG = "kpop-demon-hunters"
BASE = "https://letterboxd.com"
# 정렬: by/activity(기본), by/added, by/length, by/your-rating-highest 등
DEFAULT_SORT = "by/activity"
DEFAULT_TARGET = 10_000

OUT_DIR = "data"
JSONL_PATH = os.path.join(OUT_DIR, "reviews_raw.jsonl")
CSV_PATH = os.path.join(OUT_DIR, "reviews_raw.csv")
CHECKPOINT_PATH = os.path.join(OUT_DIR, "_checkpoint.json")

# 정중한 요청 간격(초). 서버 부하/차단을 피하려면 낮추지 말 것.
DELAY_MIN, DELAY_MAX = 1.5, 3.0
MAX_RETRIES = 5
TIMEOUT = 25

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}


# ----------------------------------------------------------------------------
# 데이터 모델
# ----------------------------------------------------------------------------
@dataclass
class Review:
    id: str
    author: str
    rating: Optional[float]
    date: str
    text: str
    url: str


# ----------------------------------------------------------------------------
# 네트워크 (재시도 + 백오프)
# ----------------------------------------------------------------------------
def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def polite_sleep() -> None:
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def fetch(session: requests.Session, url: str) -> Optional[str]:
    """url을 GET. 429/5xx는 지수 백오프로 재시도. 영구 실패면 None."""
    backoff = 3.0
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.text
            if r.status_code in (429, 500, 502, 503, 504):
                wait = backoff * attempt + random.uniform(0, 2)
                print(f"  [{r.status_code}] 재시도 {attempt}/{MAX_RETRIES} — {wait:.1f}s 대기")
                time.sleep(wait)
                continue
            if r.status_code in (403, 404):
                print(f"  [{r.status_code}] 접근 불가: {url}")
                return None
            print(f"  [{r.status_code}] 예상 외 응답: {url}")
            time.sleep(backoff)
        except requests.RequestException as e:
            wait = backoff * attempt
            print(f"  네트워크 오류({e}) — 재시도 {attempt}/{MAX_RETRIES}, {wait:.1f}s 대기")
            time.sleep(wait)
    return None


# ----------------------------------------------------------------------------
# 파싱
# ----------------------------------------------------------------------------
RATING_MAP = {  # Letterboxd 별점 클래스(rated-1..10) → 0.5~5.0
    f"rated-{i}": i / 2.0 for i in range(1, 11)
}


def parse_rating(node) -> Optional[float]:
    span = node.select_one("span.rating")
    if not span:
        return None
    for cls in span.get("class", []):
        if cls in RATING_MAP:
            return RATING_MAP[cls]
    return None


def parse_reviews(html: str) -> list[Review]:
    """리뷰 목록 페이지 1장에서 모든 리뷰를 추출."""
    soup = BeautifulSoup(html, "lxml")
    out: list[Review] = []
    # 각 리뷰 항목
    for li in soup.select("li.film-detail"):
        content = li.select_one(".film-detail-content")
        if not content:
            continue

        # 본문: collapsible 본문 안의 모든 <p>
        body = content.select_one(".body-text") or content.select_one(".js-review-body")
        if not body:
            continue
        paras = [p.get_text(" ", strip=True) for p in body.select("p")]
        text = " ".join(t for t in paras if t).strip()
        if not text:
            continue

        # 작성자
        a_name = content.select_one(".attribution .name, strong.name a, .name")
        author = a_name.get_text(strip=True) if a_name else ""

        # 날짜
        t = content.select_one("time")
        date = t.get("datetime", "") if t else ""

        # 리뷰 고유 URL & id
        link = content.select_one("a.context, a[href*='/film/']")
        href = link.get("href") if link else ""
        url = BASE + href if href.startswith("/") else href
        rid = (
            li.get("data-object-id")
            or content.get("data-object-id")
            or href
            or f"{author}|{date}|{hash(text) & 0xffffffff}"
        )

        out.append(
            Review(
                id=str(rid),
                author=author,
                rating=parse_rating(content),
                date=date,
                text=text,
                url=url,
            )
        )
    return out


def find_older_link(html: str) -> Optional[str]:
    """'OLDER' 버튼(= a.next)의 절대 URL을 반환. 없으면 None(마지막 페이지)."""
    soup = BeautifulSoup(html, "lxml")
    a = soup.select_one(".paginate-nextprev a.next")
    if not a:
        return None
    href = a.get("href", "")
    if not href:
        return None
    return BASE + href if href.startswith("/") else href


# ----------------------------------------------------------------------------
# 체크포인트(이어받기)
# ----------------------------------------------------------------------------
def load_checkpoint(start_url: str) -> tuple[str, set[str], int]:
    """저장된 진행상황이 있으면 (다음URL, 이미수집한id집합, 누적개수) 반환."""
    seen: set[str] = set()
    count = 0
    next_url = start_url

    if os.path.exists(JSONL_PATH):
        with open(JSONL_PATH, encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    seen.add(rec["id"])
                    count += 1
                except Exception:
                    pass

    if os.path.exists(CHECKPOINT_PATH):
        try:
            cp = json.load(open(CHECKPOINT_PATH, encoding="utf-8"))
            next_url = cp.get("next_url") or start_url
            print(f"[resume] 체크포인트 발견 — {count}개 보유, 다음 페이지부터 이어받기")
        except Exception:
            pass

    return next_url, seen, count


def save_checkpoint(next_url: Optional[str], count: int) -> None:
    json.dump(
        {"next_url": next_url, "count": count, "ts": time.time()},
        open(CHECKPOINT_PATH, "w", encoding="utf-8"),
        ensure_ascii=False,
    )


# ----------------------------------------------------------------------------
# 메인 루프
# ----------------------------------------------------------------------------
def run(target: int, sort: str) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    start_url = f"{BASE}/film/{FILM_SLUG}/reviews/{sort}/"
    next_url, seen, count = load_checkpoint(start_url)

    session = make_session()
    jsonl = open(JSONL_PATH, "a", encoding="utf-8")

    page_no = 0
    print(f"[start] 목표 {target}개 · 시작 URL: {next_url}")

    while next_url and count < target:
        page_no += 1
        print(f"[page {page_no}] GET {next_url}  (누적 {count})")
        html = fetch(session, next_url)
        if html is None:
            print("  페이지를 가져오지 못해 종료(이어받기 가능).")
            break

        reviews = parse_reviews(html)
        new_in_page = 0
        for rv in reviews:
            if rv.id in seen:
                continue
            seen.add(rv.id)
            jsonl.write(json.dumps(asdict(rv), ensure_ascii=False) + "\n")
            count += 1
            new_in_page += 1
            if count >= target:
                break
        jsonl.flush()
        print(f"  +{new_in_page} (페이지 내 {len(reviews)}건)")

        # 다음(OLDER) 링크 추출 → 없으면 마지막 페이지
        nxt = find_older_link(html)
        next_url = nxt
        save_checkpoint(next_url, count)

        if new_in_page == 0 and nxt is None:
            print("  더 이상 페이지 없음 — 정상 종료.")
            break

        polite_sleep()

    jsonl.close()
    export_csv()
    print(f"[done] 총 {count}개 수집 → {JSONL_PATH}")
    if count < target and next_url is None:
        print("      (사이트가 보유한 리뷰를 모두 수집했습니다.)")


def export_csv() -> None:
    """jsonl → csv 변환(엑셀 확인용)."""
    if not os.path.exists(JSONL_PATH):
        return
    with open(JSONL_PATH, encoding="utf-8") as f, open(
        CSV_PATH, "w", newline="", encoding="utf-8-sig"
    ) as out:
        w = csv.writer(out)
        w.writerow(["id", "author", "rating", "date", "text", "url"])
        for line in f:
            try:
                r = json.loads(line)
                w.writerow([r["id"], r["author"], r["rating"], r["date"], r["text"], r["url"]])
            except Exception:
                pass


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Letterboxd KPop Demon Hunters 리뷰 수집")
    ap.add_argument("--target", type=int, default=DEFAULT_TARGET, help="목표 리뷰 개수")
    ap.add_argument("--sort", type=str, default=DEFAULT_SORT,
                    help="정렬(by/activity, by/added, by/length 등)")
    args = ap.parse_args()
    try:
        run(args.target, args.sort)
    except KeyboardInterrupt:
        print("\n[중단] 사용자 중단 — 체크포인트 저장됨. 다시 실행하면 이어받습니다.")
        export_csv()
        sys.exit(0)
