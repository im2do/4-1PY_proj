# -*- coding: utf-8 -*-
"""
Letterboxd 리뷰 정제기 (분절 → 불용어 제거 → 빈도)
=====================================================
scrape_letterboxd.py 가 만든 data/reviews_raw.jsonl 을 읽어서,
워드클라우드에 '리뷰의 내용'이 드러나도록 정제한다.

정제 규칙
1) 영어 리뷰만 사용(langdetect 있으면 사용, 없으면 ASCII 비율 휴리스틱).
2) 소문자화 → URL/숫자/이모지/문장부호 제거 → 토큰화.
3) 영어 기능어(a, the, i, is, of ...) 제거 — 광범위한 내장 stopword 세트.
4) 제목·장르 같은 '큰 어휘'를 제외 단어로 지정:
   케데헌/골든/케이팝데몬헌터스/영화/드라마/케이팝 → movie, drama, kpop, golden, demon, hunters ...
   (TITLE_STOP 에서 자유롭게 추가/삭제 가능)
5) (선택) 표제어 추출(lemmatization): nltk 가 있으면 사용해 movies→movie 등 통합.
6) 2글자 이하·불용어·제외어 제거.

출력
    data/cleaned_reviews.txt  # 리뷰 1건 = 1줄(정제된 토큰 공백연결) — 추후 워드클라우드 입력용
    data/tokens_all.txt       # 모든 토큰을 공백으로 이어붙인 1개 문서
    data/word_freq.csv        # word,count (빈도 내림차순)

사용법
    pip install langdetect        # (선택) 영어 판별 정확도↑
    pip install nltk              # (선택) 표제어 추출
    python clean_reviews.py
"""

from __future__ import annotations
import csv
import json
import os
import re
from collections import Counter

IN_PATH = os.path.join("data", "reviews_raw.jsonl")
CLEAN_PATH = os.path.join("data", "cleaned_reviews.txt")
TOKENS_PATH = os.path.join("data", "tokens_all.txt")
FREQ_PATH = os.path.join("data", "word_freq.csv")

MIN_TOKEN_LEN = 3   # 이 길이 이하 토큰 제거(2 로 낮춰도 됨)

# ----------------------------------------------------------------------------
# (A) 영어 기능어 — 워드클라우드에서 의미 없는 단어(내장 세트, nltk 불필요)
# ----------------------------------------------------------------------------
ENGLISH_STOP = set("""
a an the and or but if then else when while of in on at to from by for with about against
between into through during before after above below up down out off over under again further
is are was were be been being am do does did doing have has had having will would shall should
can could may might must i me my mine myself we us our ours ourselves you your yours yourself
yourselves he him his himself she her hers herself it its itself they them their theirs themselves
this that these those what which who whom whose where why how all any both each few more most other
some such no nor not only own same so than too very s t just don now d ll m o re ve y ain aren couldn
didn doesn hadn hasn haven isn ma mightn mustn needn shan shouldn wasn weren won wouldn
as because until against among also however therefore thus hence yet still even though although
get got getting gotten go goes going gone went make makes made making like likes liked one two
really actually basically literally maybe perhaps probably definitely simply pretty quite rather
much many lot lots kind sort thing things stuff way ways im ive id youre theyre dont doesnt didnt
cant couldnt wouldnt shouldnt wont isnt arent wasnt werent thats whats lets gonna wanna gotta
ok okay yeah yep nope nah lol lmao haha hahaha omg tbh imo idk etc also able well good bad
watch watched watching see saw seen look looked looking feel felt feeling think thought
know knew known want wanted say said tell told give gave take took come came put
""".split())

# ----------------------------------------------------------------------------
# (B) 제목·장르 등 '큰 어휘' 제외 단어 — 리뷰 내용이 드러나도록 제거
#     (한국어 예시 케데헌/골든/케이팝데몬헌터스/영화/드라마/케이팝 의 영어 대응)
# ----------------------------------------------------------------------------
TITLE_STOP = set("""
kpop k-pop kpopdemonhunters kdh demon demons hunter hunters huntr huntrix
golden movie movies film films cinema cinematic drama dramas show shows
animation animated anime cartoon netflix sony soundtrack ost song songs music
korean korea
""".split())
# 필요하면 캐릭터/그룹명도 추가 제외 가능(원하면 주석 해제):
# TITLE_STOP |= set("rumi mira zoey jinu sajaboys saja".split())

STOP = ENGLISH_STOP | TITLE_STOP

# ----------------------------------------------------------------------------
# 토큰화
# ----------------------------------------------------------------------------
URL_RE = re.compile(r"http\S+|www\.\S+")
TOKEN_RE = re.compile(r"[a-z][a-z'\-]+")  # 영문 단어(중간 어퍼스트로피/하이픈 허용)


def tokenize(text: str) -> list[str]:
    text = text.lower()
    text = URL_RE.sub(" ", text)
    toks = TOKEN_RE.findall(text)
    out = []
    for w in toks:
        w = w.strip("'-")
        if len(w) < MIN_TOKEN_LEN:
            continue
        if w in STOP:
            continue
        out.append(w)
    return out


# ----------------------------------------------------------------------------
# (선택) 표제어 추출 — nltk 있으면 사용, 없으면 그대로
# ----------------------------------------------------------------------------
def get_lemmatizer():
    try:
        from nltk.stem import WordNetLemmatizer
        import nltk
        try:
            nltk.data.find("corpora/wordnet")
        except LookupError:
            nltk.download("wordnet", quiet=True)
        lem = WordNetLemmatizer()
        return lambda w: lem.lemmatize(w)
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 영어 판별
# ----------------------------------------------------------------------------
def english_filter():
    try:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0

        def is_en(t: str) -> bool:
            if len(t) < 20:
                return True  # 너무 짧으면 판별 불가 → 통과
            try:
                return detect(t) == "en"
            except Exception:
                return True
        return is_en
    except Exception:
        # langdetect 없을 때: 비ASCII 비율로 대략 판별
        def is_en(t: str) -> bool:
            if not t:
                return False
            ascii_ratio = sum(c.isascii() for c in t) / len(t)
            return ascii_ratio > 0.9
        return is_en


# ----------------------------------------------------------------------------
# 메인
# ----------------------------------------------------------------------------
def main() -> None:
    if not os.path.exists(IN_PATH):
        raise SystemExit(f"입력이 없습니다: {IN_PATH} — 먼저 scrape_letterboxd.py 를 실행하세요.")

    is_en = english_filter()
    lemmatize = get_lemmatizer()
    if lemmatize is None:
        print("[info] nltk 미설치 — 표제어 추출 생략(설치 시 movies→movie 등 통합).")

    freq: Counter = Counter()
    n_in = n_en = 0

    with open(IN_PATH, encoding="utf-8") as f, \
         open(CLEAN_PATH, "w", encoding="utf-8") as out_clean, \
         open(TOKENS_PATH, "w", encoding="utf-8") as out_tokens:

        for line in f:
            try:
                rec = json.loads(line)
            except Exception:
                continue
            n_in += 1
            text = rec.get("text", "")
            if not is_en(text):
                continue
            n_en += 1

            toks = tokenize(text)
            if lemmatize:
                toks = [lemmatize(w) for w in toks]
                # 표제어가 제외어가 되는 경우(예: movies→movie) 한 번 더 거름
                toks = [w for w in toks if w not in STOP and len(w) >= MIN_TOKEN_LEN]

            if not toks:
                continue
            freq.update(toks)
            out_clean.write(" ".join(toks) + "\n")
            out_tokens.write(" ".join(toks) + " ")

    # 빈도 CSV
    with open(FREQ_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["word", "count"])
        for word, cnt in freq.most_common():
            w.writerow([word, cnt])

    print(f"[done] 입력 {n_in}건 · 영어 {n_en}건 · 고유단어 {len(freq)}개")
    print(f"       {CLEAN_PATH} / {TOKENS_PATH} / {FREQ_PATH} 생성")
    print("[상위 30개]")
    for word, cnt in freq.most_common(30):
        print(f"  {word:<16} {cnt}")


if __name__ == "__main__":
    main()
