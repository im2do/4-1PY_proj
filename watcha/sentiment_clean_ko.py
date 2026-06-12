# -*- coding: utf-8 -*-
"""
왓챠피디아 한국어 리뷰 — 중복제거 + 감성분류 + 정제 + 워드클라우드용 빈도 정렬
================================================================================
입력: kpop_demon_hunters_watcha_infinite.csv  (컬럼: raw_text, cleaned_words)
  - cleaned_words 는 이미 Okt 형태소분석(원형: 맛있다/시원하다 등)이 된 컬럼이라
    이를 토큰/감성 매칭에 그대로 활용한다.
  - 별점 컬럼이 없으므로(레터박스와 동일) 한국어 '감성사전'으로 긍/부정 분류한다.

처리
  1) 중복 제거: raw_text 정규화(공백/문장부호 제거) 기준 + cleaned_words 기준
  2) 감성 점수 = (긍정어 hit) - (부정어 hit), 부정어미(안/못/없다/아니다)면 긍정 약화
     → score>0 긍정, <0 부정, =0 중립
  3) cleaned_words 에서 불용어/제목어 제거 후 클래스별 빈도 집계
  4) 내림차순 정렬 CSV(워드클라우드 입력) + 토큰 문서 출력

출력(data/)
  reviews_labeled.csv   freq_positive.csv  freq_negative.csv  freq_all.csv
  tokens_positive.txt   tokens_negative.txt

* 한계: 감성사전 방식은 반어/맥락을 완벽히 못 잡는다. 사전(POS/NEG)은 아래에서 자유롭게 보강 가능.
"""
from __future__ import annotations
import csv, os, re
from collections import Counter

IN_CSV  = "kpop_demon_hunters_watcha_infinite.csv"
OUT_DIR = "data"

# ---------------------------------------------------------------------------
# 한국어 감성사전 (영화 리뷰 도메인, Okt 원형 기준). 필요시 단어 추가/삭제.
# ---------------------------------------------------------------------------
POS = set("""
좋다 좋아하다 최고 짱 굿 대박 명작 수작 띵작 갓 인생 재밌다 재미있다 재미 꿀잼 핵잼
웃기다 웃음 유쾌 상쾌 통쾌 감동 감동적 뭉클 벅차다 울다 눈물 멋지다 멋있다 예쁘다 아름답다
귀엽다 사랑 사랑하다 행복 행복하다 즐겁다 즐기다 흥겹다 신나다 신명 완벽 훌륭하다 뛰어나다
인상적 신선하다 참신 독창 매력 매력적 중독 중독성 소름 황홀 환상 경이 추천 강추 입덕 빠지다
만족 흡족 따뜻하다 깔끔하다 탄탄하다 화려하다 세련 기대 설레다 흥미롭다 흥미 재치 명곡 띵곡
잘하다 잘만들다 정성 진심 고퀄 호평 인정 무난 볼만하다 킬링 힐링 행복감 기쁘다 좋았다 최애
""".split())

NEG = set("""
별로 별루 별로다 아쉽다 아쉬움 실망 실망스럽다 싫다 지루하다 노잼 재미없다 부족 부족하다 어색 어색하다
억지 작위 그저그렇다 그닥 망하다 최악 졸작 망작 노답 비추 비추천 식상 식상하다 진부 진부하다
유치 유치하다 오글 오글거리다 오그라들다 오그라 거부감 불편 불편하다 짜증 짜증나다 화나다 답답 답답하다
빈약 빈약하다 엉성 엉성하다 산만 산만하다 클리셰 뻔하다 뻔함 한계 부담 부담스럽다 실패 끔찍 끔찍하다
형편없다 글쎄 애매 애매하다 모호 모호하다 약하다 떨어지다 부실 부실하다 허접 조잡 조잡하다 단조 단조롭다
평범 평범하다 손발 거슬리다 과대평가 과대 그냥그렇다 아깝다 시간낭비 늘어지다 루즈 루즈하다 억지스럽다
""".split())

NEGATION = set("안 못 없다 아니다 아니 말다 없음 안되다".split())

# ---------------------------------------------------------------------------
# 불용어 (워드클라우드에서 의미 없는 음절) + 제목·장르 등 큰 어휘 제외
#   사용자 예시: '아' '진짜' '되다' '하다' '이다' 등
# ---------------------------------------------------------------------------
KO_STOP = set("""
하다 되다 이다 있다 없다 같다 보다 그렇다 그러다 이러다 저러다 들다 나다 지다 오다 가다 받다
너무 진짜 정말 그냥 완전 약간 매우 아주 좀 더 또 다시 이거 그거 저거 이건 그건 이게 그게 저게
거 게 것 수 때 데 줄 점 등 등등 정도 부분 생각 느낌 사람 우리 내가 너 저 그 이 자기 본인
누구 모두 다들 여기 거기 저기 이제 지금 처음 마지막 그리고 근데 그런데 하지만 그래서 그래도
뭔가 약간씩 아 어 음 와 헐 진짜로 라지 어쩜 얼마나 그니까 이런 그런 저런 거기 무슨 어떤 모든
거의 하나 둘 때문 동안 만큼 위해 통해 대해 가지 보기 정작 솔직히 그냥저냥 이번 다음 우리나라
""".split())

TITLE_STOP = set("""
케데헌 케이팝데몬헌터스 케이팝데몬헌터즈 데몬헌터스 케데몬 골든 케이팝 영화 드라마 애니 애니메이션
넷플릭스 노래 음악 사운드 ost 오에스티 작품
""".split())
# 한국/문화/고증/전통 등은 '리뷰 내용'이라 일부러 남겨둠. 빼고 싶으면 위에 추가.

STOP = KO_STOP | TITLE_STOP

NORM = re.compile(r"[\s\W_]+", re.U)  # 중복판정용 정규화


def score_sentiment(tokens: list[str]) -> int:
    pos = sum(1 for t in tokens if t in POS)
    neg = sum(1 for t in tokens if t in NEG)
    has_negation = any(t in NEGATION for t in tokens)
    if has_negation and pos > 0:   # '안 좋다' 류 → 긍정 약화
        pos -= 1
        neg += 1
    return pos - neg


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = list(csv.DictReader(open(IN_CSV, encoding="utf-8-sig")))
    n_raw = len(rows)

    # ---- 중복 제거 ----
    seen_raw, seen_clean = set(), set()
    uniq = []
    for r in rows:
        raw = (r.get("raw_text") or "").strip()
        clean = (r.get("cleaned_words") or "").strip()
        if not clean:
            continue
        key_raw = NORM.sub("", raw).lower()
        key_clean = clean
        if key_raw and key_raw in seen_raw:
            continue
        if key_clean in seen_clean:
            continue
        seen_raw.add(key_raw); seen_clean.add(key_clean)
        uniq.append(r)
    n_dup = n_raw - len(uniq)

    labeled = []
    freq = {"positive": Counter(), "negative": Counter(), "neutral": Counter()}
    counts = Counter()

    for r in uniq:
        tokens = (r.get("cleaned_words") or "").split()
        s = score_sentiment(tokens)
        label = "positive" if s > 0 else "negative" if s < 0 else "neutral"
        counts[label] += 1
        kept = [t for t in tokens if len(t) > 1 and t not in STOP]
        freq[label].update(kept)
        labeled.append({
            "sentiment": label, "score": s,
            "raw_text": r.get("raw_text", ""), "cleaned_words": r.get("cleaned_words", ""),
        })

    # ---- 저장 ----
    with open(os.path.join(OUT_DIR, "reviews_labeled.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["sentiment", "score", "raw_text", "cleaned_words"])
        w.writeheader(); w.writerows(labeled)

    def dump_freq(counter, path):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["word", "count"])
            for word, c in counter.most_common():
                w.writerow([word, c])

    dump_freq(freq["positive"], os.path.join(OUT_DIR, "freq_positive.csv"))
    dump_freq(freq["negative"], os.path.join(OUT_DIR, "freq_negative.csv"))
    dump_freq(freq["positive"] + freq["negative"] + freq["neutral"], os.path.join(OUT_DIR, "freq_all.csv"))

    def dump_tokens(counter, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(" ".join((w + " ") * c for w, c in counter.items()))
    dump_tokens(freq["positive"], os.path.join(OUT_DIR, "tokens_positive.txt"))
    dump_tokens(freq["negative"], os.path.join(OUT_DIR, "tokens_negative.txt"))

    print(f"원본 {n_raw} · 중복제거 {n_dup} · 분석 {len(uniq)}개")
    print(f"  → 긍정 {counts['positive']} · 부정 {counts['negative']} · 중립 {counts['neutral']}")
    print("\n[긍정 상위 20]")
    for w, c in freq["positive"].most_common(20): print(f"  {w:<10}{c}")
    print("\n[부정 상위 20]")
    for w, c in freq["negative"].most_common(20): print(f"  {w:<10}{c}")


if __name__ == "__main__":
    main()
