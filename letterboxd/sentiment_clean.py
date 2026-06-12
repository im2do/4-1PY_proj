# -*- coding: utf-8 -*-
"""
Letterboxd 리뷰 — 감성 분류 + 정제 + 워드클라우드용 빈도 정렬
==============================================================
입력: reviews_raw.csv  (컬럼: id, author, rating, date, text, url)
문제 해결:
  - 본문 끝의 'Like review 56,279 likes' 같은 Letterboxd UI 텍스트 제거
    (이게 'review' 가 최상위 단어로 잡힌 원인)
  - rating 이 비어 있으므로 별점 대신 VADER 감성사전으로 긍/부정 분류
처리:
  1) 텍스트 클린(UI꼬리표/URL/좋아요수 제거)
  2) VADER compound 점수로 positive / negative / neutral 분류
  3) 분절 + 불용어/제목어/축약형 제거
  4) 클래스별 단어 빈도 산출 → 내림차순 정렬 CSV (워드클라우드 입력)

출력(data/):
  reviews_labeled.csv          # 리뷰별 감성 라벨 + compound + 정제본문
  freq_positive.csv            # 긍정 리뷰 단어 빈도 (word,count)
  freq_negative.csv            # 부정 리뷰 단어 빈도
  freq_all.csv                 # 전체
  tokens_positive.txt / tokens_negative.txt   # 워드클라우드용 토큰 문서

설치: pip install vaderSentiment
"""
from __future__ import annotations
import csv, os, re
from collections import Counter
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

IN_CSV  = "data/reviews_raw.csv"
OUT_DIR = "data"

# 긍/부정 임계값 (VADER 표준)
POS_TH, NEG_TH = 0.05, -0.05
MIN_TOKEN_LEN = 3

# ---- 불용어 ----
ENGLISH_STOP = set("""
a an the and or but if then else when while of in on at to from by for with about against
between into through during before after above below up down out off over under again further
is are was were be been being am do does did doing have has had having will would shall should
can could may might must i me my mine myself we us our ours ourselves you your yours yourself
yourselves he him his himself she her hers herself it its itself they them their theirs themselves
this that these those what which who whom whose where why how all any both each few more most other
some such no nor not only own same so than too very s t just don now d ll m o re ve y ain aren couldn
didn doesn hadn hasn haven isn ma mightn mustn needn shan shouldn wasn weren won wouldn
as because until among also however therefore thus hence yet still even though although
get got getting gotten go goes going gone went make makes made making like likes liked one two
really actually basically literally maybe perhaps probably definitely simply pretty quite rather
much many lot lots kind sort thing things stuff way ways im ive id youre theyre dont doesnt didnt
cant couldnt wouldnt shouldnt wont isnt arent wasnt werent thats whats lets gonna wanna gotta
ok okay yeah yep nope nah lol lmao haha hahaha omg tbh imo idk etc able well
watch watched watching see saw seen look looked looking feel felt feeling think thought
know knew known want wanted say said tell told give gave take took come came put
its im theyre were thats whats time review reviews
there here every never ever first last little bit lot way thing way ones
would could should also still much even way enough able around back
""".split())

# 제목·장르 등 큰 어휘 (케데헌/골든/케이팝데몬헌터스/영화/드라마/케이팝 → 영어 대응)
TITLE_STOP = set("""
kpop pop kpopdemonhunters kdh demon demons hunter hunters huntr huntrix
golden movie movies film films cinema cinematic drama dramas show shows
animation animated anime cartoon netflix sony soundtrack ost song songs music
korean korea
""".split())

STOP = ENGLISH_STOP | TITLE_STOP

# ---- 정규식 ----
LIKE_TAIL = re.compile(r"\s*Like\s+review\s*[\d,]*\s*likes?\s*$", re.I)  # 끝의 UI 텍스트
URL_RE    = re.compile(r"http\S+|www\.\S+")
TOKEN_RE  = re.compile(r"[a-z]{2,}")  # 어퍼스트로피 제거 후 알파벳 토큰


def clean_text(raw: str) -> str:
    t = LIKE_TAIL.sub("", raw or "").strip()
    t = URL_RE.sub(" ", t)
    return t


# 영어 판별 (langdetect 있으면 사용, 없으면 ASCII 비율 휴리스틱)
try:
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0
    def is_english(t: str) -> bool:
        if len(t) < 15:                    # 너무 짧으면 판별 불가 → ASCII 비율로
            return sum(c.isascii() for c in t) / max(1, len(t)) > 0.9
        try:
            return detect(t) == "en"
        except Exception:
            return True
except Exception:
    def is_english(t: str) -> bool:
        return bool(t) and sum(c.isascii() for c in t) / len(t) > 0.9


def tokenize(text: str) -> list[str]:
    text = text.lower().replace("’", "'").replace("'", "")  # it's -> its
    out = []
    for w in TOKEN_RE.findall(text):
        if len(w) < MIN_TOKEN_LEN or w in STOP:
            continue
        out.append(w)
    return out


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    sia = SentimentIntensityAnalyzer()
    rows = list(csv.DictReader(open(IN_CSV, encoding="utf-8-sig")))

    labeled = []
    freq = {"positive": Counter(), "negative": Counter(), "neutral": Counter()}
    counts = Counter()
    n_total = n_nonen = 0

    for r in rows:
        text = clean_text(r.get("text", ""))
        if not text:
            continue
        n_total += 1
        if not is_english(text):            # 영어 리뷰만 사용
            n_nonen += 1
            continue
        comp = sia.polarity_scores(text)["compound"]
        label = "positive" if comp >= POS_TH else "negative" if comp <= NEG_TH else "neutral"
        counts[label] += 1
        toks = tokenize(text)
        freq[label].update(toks)
        labeled.append({
            "id": r.get("id", ""), "author": r.get("author", ""), "date": r.get("date", ""),
            "sentiment": label, "compound": f"{comp:.4f}", "text": text, "url": r.get("url", ""),
        })

    # 라벨 CSV
    with open(os.path.join(OUT_DIR, "reviews_labeled.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id","author","date","sentiment","compound","text","url"])
        w.writeheader(); w.writerows(labeled)

    # 빈도 CSV (정렬)
    def dump_freq(counter, path):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["word", "count"])
            for word, c in counter.most_common():
                w.writerow([word, c])

    dump_freq(freq["positive"], os.path.join(OUT_DIR, "freq_positive.csv"))
    dump_freq(freq["negative"], os.path.join(OUT_DIR, "freq_negative.csv"))
    allc = freq["positive"] + freq["negative"] + freq["neutral"]
    dump_freq(allc, os.path.join(OUT_DIR, "freq_all.csv"))

    # 워드클라우드용 토큰 문서
    def dump_tokens(counter, path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(" ".join((w + " ") * c for w, c in counter.items()))
    dump_tokens(freq["positive"], os.path.join(OUT_DIR, "tokens_positive.txt"))
    dump_tokens(freq["negative"], os.path.join(OUT_DIR, "tokens_negative.txt"))

    # 요약
    print(f"전체 {n_total} · 비영어 제외 {n_nonen} · 분석 {sum(counts.values())}개")
    print(f"  → 긍정 {counts['positive']} · 부정 {counts['negative']} · 중립 {counts['neutral']}")
    print("\n[긍정 상위 20]")
    for w, c in freq["positive"].most_common(20): print(f"  {w:<14}{c}")
    print("\n[부정 상위 20]")
    for w, c in freq["negative"].most_common(20): print(f"  {w:<14}{c}")


if __name__ == "__main__":
    main()
