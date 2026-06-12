# -*- coding: utf-8 -*-
"""
왓챠피디아 리뷰 무한 스크롤 수집기 (Selenium)
================================================
왓챠피디아 리뷰 페이지는 '무한 스크롤(infinite scroll)' 방식이라,
스크롤을 내릴 때마다 리뷰가 동적으로 추가 로딩된다.

[핵심] 봇/매크로 탐지 우회
  - 일정한 간격·일정한 스크롤 양으로 반복하면 자동화로 탐지돼 차단·캡차가 뜬다.
  - 따라서 (1) 스크롤 이동량과 (2) 대기 시간을 '난수(random)'로 설정해
    사람의 불규칙한 행동을 모사한다.  random.randint / random.uniform 사용.

출력: kpop_demon_hunters_watcha_infinite.csv  (raw_text, cleaned_words)
설치: pip install selenium konlpy ;  ChromeDriver 필요
"""
import csv, random, time, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from konlpy.tag import Okt

URL = "https://pedia.watcha.com/ko-KR/contents/<CONTENT_ID>/comments"  # 대상 리뷰 페이지
REVIEW_SEL = "div.css-review-text, .StyledText"   # 리뷰 텍스트 셀렉터(사이트 구조에 맞춤)
MAX_STALE = 6          # 새 리뷰가 더 안 나오는 스크롤이 연속 6회면 종료
OUT = "kpop_demon_hunters_watcha_infinite.csv"

okt = Okt()
KO_DROP = set("을 를 이 가 은 는 의 에 도 만 와 과".split())  # 간단 예시(전처리는 별도)


def make_driver():
    opt = Options()
    opt.add_argument("--window-size=1280,2000")
    # 자동화 표식 숨기기(navigator.webdriver=false) — 탐지 회피의 일부
    opt.add_experimental_option("excludeSwitches", ["enable-automation"])
    opt.add_experimental_option("useAutomationExtension", False)
    d = webdriver.Chrome(options=opt)
    d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument",
                      {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"})
    return d


def to_cleaned(text: str) -> str:
    """Okt 형태소 분석으로 명사·형용사·동사 원형만 남긴다(워드클라우드 전처리)."""
    words = []
    for w, pos in okt.pos(text, stem=True, norm=True):
        if pos in ("Noun", "Adjective", "Verb") and len(w) > 1 and w not in KO_DROP:
            words.append(w)
    return " ".join(words)


def main():
    d = make_driver()
    d.get(URL)
    time.sleep(random.uniform(2.0, 4.0))     # 첫 로딩도 난수 대기

    seen, stale = {}, 0
    while stale < MAX_STALE:
        # ── 봇 탐지 우회: 스크롤 이동량을 '난수'로 ──
        step = random.randint(1200, 2600)
        d.execute_script(f"window.scrollBy(0, {step});")

        # ── 봇 탐지 우회: 대기 시간을 '난수'로(사람처럼 불규칙) ──
        time.sleep(random.uniform(1.2, 3.2))
        # 가끔 살짝 위로 되올리는 등 인간적 노이즈(선택)
        if random.random() < 0.15:
            d.execute_script(f"window.scrollBy(0, {-random.randint(150, 400)});")
            time.sleep(random.uniform(0.4, 1.0))

        before = len(seen)
        for el in d.find_elements(By.CSS_SELECTOR, REVIEW_SEL):
            t = el.text.strip()
            if t and t not in seen:
                seen[t] = to_cleaned(t)
        # 새 리뷰가 안 늘면 정체 카운트 +1, 늘면 0으로 리셋
        stale = stale + 1 if len(seen) == before else 0
        print(f"  수집 {len(seen)}건 (정체 {stale}/{MAX_STALE})")

    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["raw_text", "cleaned_words"])
        for raw, clean in seen.items():
            w.writerow([raw, clean])
    print(f"[done] {len(seen)}건 → {OUT}")
    d.quit()


if __name__ == "__main__":
    main()
