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

    # ── 관심 ETF (직접 추가 관리) ──
    # 추가 방법: 아래 딕셔너리에 한 줄 추가 후 저장 → 다음 수집부터 자동 반영
    #   "ETF_고유키": ("야후티커", "표시명", "ETF_US|ETF_KR|ETF_CN|ETF_JP", "달러|원|엔"),
    # 예시: "ETF_SCHD": ("SCHD", "SCHD(미국 배당)", "ETF_US", "달러"),
    etf = {
    }
    for k, (tic, lb, grp, unit) in etf.items():
        try:
            add(k, lb, grp, yff(tic), unit)
        except Exception as e:
            print(f"[FAIL] {k}: {e}")
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

    def yoy(s, n=12):
        out = (s.pct_change(n) * 100).dropna()
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
        ("LIQ_USM2",    "M2SL",            "미국 M2(전년비)",            "LIQ",    "%",    "yoy"),
        ("LIQ_FED",     "WALCL",           "연준 총자산(전년비)",        "LIQ",    "%",    "yoy52"),
    ]
    for k, sid, lb, grp, unit, tf in fred_items:
        try:
            s = fred_series(sid, trim=(tf is None))
            if tf:
                s = yoy(s, 52 if tf == "yoy52" else 12)
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
    m2_done, m2_err = False, ""
    for st_c in ("101Y004", "101Y003", "101Y002"):
        try:
            url2 = ("https://ecos.bok.or.kr/api/StatisticSearch/" + ECOS_KEY
                    + "/json/kr/1/1000/" + st_c + "/M/" + f_m + "/" + t_m + "/BBHA00")
            js2 = requests.get(url2, timeout=60).json()
            rows2 = js2.get("StatisticSearch", {}).get("row", [])
            if not rows2:
                m2_err = st_c + ": " + str(js2.get("RESULT", js2))[:120]
                continue
            s2 = pd.Series({pd.Timestamp(r["TIME"][:4] + "-" + r["TIME"][4:6] + "-01"):
                            float(r["DATA_VALUE"]) for r in rows2}).sort_index()
            s2 = (s2.pct_change(12) * 100).dropna()
            s2 = s2[s2.index >= pd.Timestamp(START)]
            if add("LIQ_KRM2", "한국 M2(전년비)", "LIQ", s2, "%"):
                m2_done = True
                print(f"       (한국 M2: ECOS 통계코드 {st_c} 사용)")
                break
        except Exception as e:
            m2_err = st_c + ": " + str(e)[:120]
    if not m2_done:
        print(f"[FAIL] LIQ_KRM2(ECOS): {m2_err}")
else:
    print("[안내] ECOS_KEY 미설정 → 한국 CPI는 건너뜁니다.")
    print("       ecos.bok.or.kr 무료 인증키 발급 후 ECOS_KEY 설정 시 수집됩니다.")

# ──────────────── 국내 부동산 (한국부동산원 R-ONE, 인증키 필요) ────────────────
REB_KEY = os.getenv("REB_KEY")
if REB_KEY:
    try:
        import requests

        stat_id, stat_nm = None, None
        for p in range(1, 11):
            cu = ("https://www.reb.or.kr/r-one/openapi/SttsApiTbl.do?Type=json"
                  "&pIndex=%d&pSize=1000" % p)
            cat = requests.get(cu, timeout=60).json()
            body = cat.get("SttsApiTbl")
            rows = body[1].get("row", []) if isinstance(body, list) and len(body) > 1 else []
            if not rows:
                break
            for r in rows:
                nm = str(r.get("STATBL_NM", ""))
                if "주간" in nm and "아파트" in nm and "매매가격지수" in nm:
                    if stat_id is None or len(nm) < len(stat_nm):
                        stat_id, stat_nm = r.get("STATBL_ID"), nm
            if stat_id:
                break
        if not stat_id:
            raise RuntimeError("주간 아파트 매매가격지수 통계표 탐색 실패")
        print(f"[REB]  통계표 확인: {stat_nm} ({stat_id})")

        vals = {}
        for p in range(1, 31):
            du = ("https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do?KEY=%s"
                  "&Type=json&pIndex=%d&pSize=1000&STATBL_ID=%s&DTACYCLE_CD=WK"
                  % (REB_KEY, p, stat_id))
            js = requests.get(du, timeout=60).json()
            body = js.get("SttsApiTblData")
            rows = body[1].get("row", []) if isinstance(body, list) and len(body) > 1 else []
            if not rows:
                if p == 1:
                    raise RuntimeError(str(js)[:300])
                break
            for r in rows:
                cls = str(r.get("CLS_NM", "")) + str(r.get("CLS_FULLNM", ""))
                t = str(r.get("WRTTIME_IDTFR_ID", ""))
                if "전국" in cls and len(t) == 8:
                    try:
                        vals[pd.Timestamp(t[:4] + "-" + t[4:6] + "-" + t[6:8])] = float(r["DTA_VAL"])
                    except Exception:
                        pass
        if not vals:
            raise RuntimeError("전국 주간 데이터 없음(분류 체계 확인 필요)")
        s = pd.Series(vals).sort_index()
        s = s[s.index >= pd.Timestamp(START)]
        add("RE_APT", "전국 아파트 매매가격지수(주간)", "REALTY", s, "지수")
    except Exception as e:
        print(f"[FAIL] RE_APT(부동산원): {e}")
else:
    print("[안내] REB_KEY 미설정 → 부동산원 아파트 지수는 건너뜁니다.")

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
