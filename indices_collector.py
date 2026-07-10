"""
Investment Navigator · 주가지수 수집기 — v3
------------------------------------------------
MAIN      : KOSPI, KOSDAQ, S&P500, NASDAQ, 니케이225, 상해종합
KR_SECTOR : KOSPI 업종지수 10종   (KRX 계정 필요)
KQ_SECTOR : KOSDAQ 업종지수       (KRX 계정 필요)
US_SECTOR : 미국 SPDR 섹터 ETF 11종
대체       : KRX 계정 미설정 시 KOSPI/KOSDAQ 종합지수는 야후 파이낸스로 수집
결과       : data_indices.js

[KRX 계정] data.krx.co.kr 무료 가입 후 환경변수 KRX_ID / KRX_PW 설정(파일 하단 안내).
설치(1회) : pip install pykrx yfinance pandas
실행      : python indices_collector.py
"""
import os
import json
import datetime as dt
import pandas as pd

YEARS = 10
END = dt.date.today()
START = END - dt.timedelta(days=365 * YEARS + 10)
KRX_READY = bool(os.getenv("KRX_ID") and os.getenv("KRX_PW"))

series = {}


def downsample(pts):
    cutoff = (END - dt.timedelta(days=730)).strftime("%Y-%m-%d")
    return [p for p in pts if p[0] < cutoff][::5] + [p for p in pts if p[0] >= cutoff]


def add(key, label, group, s, unit=None):
    s = s.dropna()
    pts = [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in s.items()]
    if not pts:
        print(f"[SKIP] {key} {label}: 데이터 없음")
        return False
    series[key] = {"label": label, "group": group, "pts": downsample(pts)}
    if unit:
        series[key]["unit"] = unit
    print(f"[OK]   {key} {label}: {len(series[key]['pts'])}점")
    return True


# ──────────────── 해외 (yfinance) ────────────────
yff = None
try:
    import yfinance as yf

    def yff(tic):
        df = yf.download(tic, start=START.isoformat(), interval="1d",
                         progress=False, auto_adjust=False)
        c = df["Close"]
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        return c

    for k, (tic, lb) in {
        "SPX": ("^GSPC", "S&P500"), "IXIC": ("^IXIC", "NASDAQ"),
        "N225": ("^N225", "니케이225"), "SSE": ("000001.SS", "상해종합"),
    }.items():
        try:
            add(k, lb, "MAIN", yff(tic))
        except Exception as e:
            print(f"[FAIL] {k}: {e}")

    for k, (tic, lb) in {
        "US_TECH": ("XLK", "IT(기술)"), "US_FIN": ("XLF", "금융"),
        "US_HLTH": ("XLV", "헬스케어"), "US_ENER": ("XLE", "에너지"),
        "US_INDU": ("XLI", "산업재"), "US_DISC": ("XLY", "경기소비재"),
        "US_STAP": ("XLP", "필수소비재"), "US_UTIL": ("XLU", "유틸리티"),
        "US_MATR": ("XLB", "소재"), "US_REAL": ("XLRE", "리츠·부동산"),
        "US_COMM": ("XLC", "커뮤니케이션"),
    }.items():
        try:
            add(k, lb, "US_SECTOR", yff(tic))
        except Exception as e:
            print(f"[FAIL] {k}: {e}")
    # ── 원자재 (선물 근월물 / 우라늄은 실물 신탁 대용) ──
    cmd = {
        "CMD_WTI":    ("CL=F",  "원유 WTI",        "CMD_ENE", "달러/배럴"),
        "CMD_BRENT":  ("BZ=F",  "원유 브렌트",     "CMD_ENE", "달러/배럴"),
        "CMD_NG":     ("NG=F",  "천연가스",        "CMD_ENE", "달러/MMBtu"),
        "CMD_GOLD":   ("GC=F",  "금",              "CMD_PME", "달러/온스"),
        "CMD_SILVER": ("SI=F",  "은",              "CMD_PME", "달러/온스"),
        "CMD_PLAT":   ("PL=F",  "백금",            "CMD_PME", "달러/온스"),
        "CMD_PALL":   ("PA=F",  "팔라듐",          "CMD_PME", "달러/온스"),
        "CMD_COPPER": ("HG=F",  "구리",            "CMD_IND", "달러/파운드"),
        "CMD_ALUM":   ("ALI=F", "알루미늄(참고)",  "CMD_IND", "달러/톤"),
        "CMD_URAN":   ("SRUUF", "우라늄(신탁)",    "CMD_IND", "달러/주"),
        "CMD_CORN":   ("ZC=F",  "옥수수",          "CMD_AGR", "센트/부셸"),
        "CMD_WHEAT":  ("ZW=F",  "밀",              "CMD_AGR", "센트/부셸"),
        "CMD_SOY":    ("ZS=F",  "대두",            "CMD_AGR", "센트/부셸"),
        "CMD_SUGAR":  ("SB=F",  "설탕",            "CMD_AGR", "센트/파운드"),
        "CMD_COFFEE": ("KC=F",  "커피",            "CMD_AGR", "센트/파운드"),
    }
    for k, (tic, lb, grp, unit) in cmd.items():
        try:
            add(k, lb, grp, yff(tic), unit)
        except Exception as e:
            print(f"[FAIL] {k}: {e}")

    # ── 가상자산 (야후, 달러 표시, 24시간 거래) ──
    cry = {
        "CRY_BTC": ("BTC-USD", "비트코인", "CRYPTO", "달러"),
        "CRY_ETH": ("ETH-USD", "이더리움", "CRYPTO", "달러"),
        "CRY_SOL": ("SOL-USD", "솔라나",   "CRYPTO", "달러"),
        "CRY_XRP": ("XRP-USD", "리플",     "CRYPTO", "달러"),
    }
    for k, (tic, lb, grp, unit) in cry.items():
        try:
            add(k, lb, grp, yff(tic), unit)
        except Exception as e:
            print(f"[FAIL] {k}: {e}")
except Exception as e:
    print("[해외 수집 실패]", e)

# ──────────────── 채권·경제지표·부동산 (FRED CSV, 키 불필요) ────────────────
try:
    import io
    import requests

    def fred_series(sid, trim=True):
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + sid
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        df = pd.read_csv(io.StringIO(r.text))
        df.columns = ["date", "value"]
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna()
        s = pd.Series(df["value"].values, index=pd.to_datetime(df["date"]))
        if trim:
            s = s[s.index >= pd.Timestamp(START)]
        return s

    def yoy(s):
        out = (s.pct_change(12) * 100).dropna()
        return out[out.index >= pd.Timestamp(START)]

    fred_items = [
        ("BOND_US2Y",   "DGS2",            "미국 국채 2년",              "BOND",   "%",    None),
        ("BOND_US10Y",  "DGS10",           "미국 국채 10년",             "BOND",   "%",    None),
        ("BOND_US30Y",  "DGS30",           "미국 국채 30년",             "BOND",   "%",    None),
        ("BOND_SPREAD", "T10Y2Y",          "미 장단기금리차(10y-2y)",    "BOND",   "%p",   None),
        ("BOND_KR10Y",  "IRLTLT01KRM156N", "한국 국채 10년(월별)",       "BOND",   "%",    None),
        ("ECON_US_CPI", "CPIAUCSL",        "미국 CPI(전년비)",           "ECON",   "%",    "yoy"),
        ("ECON_US_CORE","CPILFESL",        "미국 근원 CPI(전년비)",      "ECON",   "%",    "yoy"),
        ("ECON_US_UNEMP","UNRATE",         "미국 실업률",                "ECON",   "%",    None),
        ("RE_CS",       "CSUSHPINSA",      "미국 주택가격(케이스-실러)", "REALTY", "지수", None),
        ("RE_MORT",     "MORTGAGE30US",    "미국 모기지 30년 금리",      "REALTY", "%",    None),
        ("RE_KR",       "QKRR628BIS",      "한국 실질 주택가격(분기)",   "REALTY", "지수", None),
    ]
    for k, sid, lb, grp, unit, tf in fred_items:
        try:
            s = fred_series(sid, trim=(tf is None))
            if tf == "yoy":
                s = yoy(s)
            add(k, lb, grp, s, unit)
        except Exception as e:
            print(f"[FAIL] {k}({sid}): {e}")
except Exception as e:
    print("[FRED 수집 실패]", e)

# ──────────────── 한국 CPI (한국은행 ECOS, 인증키 필요) ────────────────
ECOS_KEY = os.getenv("ECOS_KEY")
if ECOS_KEY:
    try:
        import requests
        f_m = (END - dt.timedelta(days=365 * (YEARS + 2))).strftime("%Y%m")
        t_m = END.strftime("%Y%m")
        url = ("https://ecos.bok.or.kr/api/StatisticSearch/" + ECOS_KEY
               + "/json/kr/1/1000/901Y009/M/" + f_m + "/" + t_m + "/0")
        js = requests.get(url, timeout=60).json()
        rows = js.get("StatisticSearch", {}).get("row", [])
        if not rows:
            raise RuntimeError(str(js.get("RESULT", js))[:200])
        s = pd.Series({pd.Timestamp(r["TIME"][:4] + "-" + r["TIME"][4:6] + "-01"):
                       float(r["DATA_VALUE"]) for r in rows}).sort_index()
        s = (s.pct_change(12) * 100).dropna()
        s = s[s.index >= pd.Timestamp(START)]
        add("ECON_KR_CPI", "한국 CPI(전년비)", "ECON", s, "%")
    except Exception as e:
        print(f"[FAIL] ECON_KR_CPI(ECOS): {e}")
else:
    print("[안내] ECOS_KEY 미설정 → 한국 CPI는 건너뜁니다.")
    print("       ecos.bok.or.kr 무료 인증키 발급 후 ECOS_KEY 설정 시 수집됩니다.")

# ──────────────── 국내 (pykrx, KRX 계정 필요) ────────────────
if KRX_READY:
    try:
        from pykrx import stock

        f, t = START.strftime("%Y%m%d"), END.strftime("%Y%m%d")

        def krx_close(ticker):
            return stock.get_index_ohlcv_by_date(f, t, ticker)["종가"]

        for key, lb, tk in [("KOSPI", "KOSPI", "1001"), ("KOSDAQ", "KOSDAQ", "2001")]:
            try:
                add(key, lb, "MAIN", krx_close(tk))
            except Exception as e:
                print(f"[FAIL] {key}: {e}")

        def collect_sectors(market, group, want, prefix):
            try:
                tickers = stock.get_index_ticker_list(market=market)
                names = {tk: stock.get_index_ticker_name(tk) for tk in tickers}
            except Exception as e:
                print(f"[{market} 업종 목록 조회 실패]", e)
                return
            miss = []
            for key, kw in want.items():
                kwn = kw.replace("·", "").replace(" ", "")
                hit = [tk for tk, nm in names.items()
                       if kwn in nm.replace("·", "").replace(" ", "")
                       and "200" not in nm and "150" not in nm]
                hit.sort(key=lambda tk: len(names[tk]))  # 가장 짧은 정식 업종명 우선
                if hit:
                    try:
                        add(key, prefix + names[hit[0]], group, krx_close(hit[0]))
                    except Exception as e:
                        print(f"[FAIL] {key}({kw}): {e}")
                else:
                    miss.append(kw)
                    print(f"[MISS] {market} {kw}: 일치 업종지수 없음")
            if miss:
                print(f"[참고] {market} 업종지수 전체 목록: "
                      + ", ".join(sorted(set(names.values()))))

        collect_sectors("KOSPI", "KR_SECTOR", {
            "KR_ELEC": "전기전자", "KR_CHEM": "화학", "KR_FIN": "금융",
            "KR_AUTO": "운송장비", "KR_STEEL": "금속", "KR_CONST": "건설",
            "KR_RETAIL": "유통", "KR_PHARM": "제약", "KR_TELCO": "통신",
            "KR_FOOD": "음식료",
        }, "")

        collect_sectors("KOSDAQ", "KQ_SECTOR", {
            "KQ_PHARM": "제약", "KQ_ELEC": "전기전자", "KQ_MED": "의료정밀",
            "KQ_FIN": "금융", "KQ_RETAIL": "유통", "KQ_CHEM": "화학",
            "KQ_MACH": "기계", "KQ_MFG": "제조", "KQ_TRAN": "운송장비",
            "KQ_ENT": "오락",
        }, "")
    except Exception as e:
        print("[국내 수집 실패]", e)
else:
    print("[안내] KRX 계정 미설정 → 국내 업종지수는 건너뜁니다.")
    print("       data.krx.co.kr 무료 가입 후 KRX_ID / KRX_PW 설정 뒤 재실행하십시오.")

# KOSPI/KOSDAQ 종합지수 대체(야후)
if yff is not None:
    for key, tic, lb in [("KOSPI", "^KS11", "KOSPI"), ("KOSDAQ", "^KQ11", "KOSDAQ")]:
        if key not in series:
            try:
                if add(key, lb, "MAIN", yff(tic)):
                    print(f"       ({key}: 야후 파이낸스 대체 수집)")
            except Exception as e:
                print(f"[FAIL] {key}(야후 대체): {e}")

out = "window.IDX_DATA=" + json.dumps(
    {"generated": END.isoformat(), "series": series}, ensure_ascii=False) + ";"
with open("data_indices.js", "w", encoding="utf-8") as fp:
    fp.write(out)
print(f"저장 완료: data_indices.js · {len(series)}개 시리즈")
