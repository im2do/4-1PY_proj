# Letterboxd 리뷰 수집 · 정제 (KPop Demon Hunters)

Mac + VSCode 에서 그대로 실행하는 2단계 파이프라인입니다.
수집(scrape) → 정제(clean) 순서로 돌리면 워드클라우드 입력 파일까지 나옵니다.

## 1. 설치

```bash
cd letterboxd
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`langdetect`, `nltk` 는 선택입니다(없어도 동작). 있으면 영어 판별·표제어 통합 정확도가 올라갑니다.

## 2. 수집 — `scrape_letterboxd.py`

```bash
# 먼저 소량으로 동작 확인 (셀렉터/네트워크 점검)
python scrape_letterboxd.py --target 50

# 정상 동작하면 본 수집
python scrape_letterboxd.py --target 10000
```

- 'OLDER' 버튼은 실제로 `<a class="next" href=".../page/N/">Older</a>` 링크입니다.
  이 코드는 그 href 를 그대로 따라가므로 **버튼 클릭과 동일하게** 다음 페이지로 넘어갑니다.
- 중간에 끊겨도 다시 실행하면 `data/_checkpoint.json` 으로 **이어받기(resume)** 합니다.
- 결과: `data/reviews_raw.jsonl`, `data/reviews_raw.csv`

> 1만 개는 페이지가 매우 많아 시간이 걸립니다(정중한 딜레이 1.5~3초 × 페이지수).
> 한 페이지에 약 12개 리뷰 → 1만 개면 800페이지 안팎. 중간에 멈춰도 이어집니다.
> Letterboxd 가 보유한 리뷰가 1만 개보다 적으면 'OLDER' 링크가 사라지며 자동 종료됩니다.

## 3. 정제 — `clean_reviews.py`

```bash
python clean_reviews.py
```

정제 규칙:
1. 영어 리뷰만 사용
2. 소문자화 → URL/숫자/이모지/문장부호 제거 → 분절(토큰화)
3. 영어 기능어 제거 (a, the, i, is, of …) — `ENGLISH_STOP`
4. **제목·장르 등 큰 어휘 제외** — `TITLE_STOP`
   (케데헌/골든/케이팝데몬헌터스/영화/드라마/케이팝 → kpop, golden, demon, hunters, movie, drama, music, korean …)
5. (선택) 표제어 추출로 movies→movie 등 통합
6. 결과: `data/cleaned_reviews.txt`(리뷰별 토큰), `data/tokens_all.txt`(전체), `data/word_freq.csv`(빈도)

### 제외 단어 조절
`clean_reviews.py` 상단의 `TITLE_STOP` / `ENGLISH_STOP` 를 직접 추가·삭제하세요.
예: 캐릭터명도 빼고 싶으면
```python
TITLE_STOP |= set("rumi mira zoey jinu sajaboys saja".split())
```

## 4. (나중에) 워드클라우드
`data/tokens_all.txt` 또는 `data/word_freq.csv` 를 입력으로 쓰면 됩니다.

---

### 마크업이 바뀌었을 때 점검 포인트
이 환경에서 라이브 DOM 확인이 불가해, Letterboxd 표준 셀렉터 + 폴백으로 작성했습니다.
혹시 0건이 잡히면 아래 두 셀렉터만 브라우저 개발자도구로 확인해 `parse_reviews` /
`find_older_link` 에 반영하면 됩니다.
- 리뷰 항목: `li.film-detail` → 본문 `.body-text p`
- 다음 페이지: `.paginate-nextprev a.next` (라벨 'Older')
