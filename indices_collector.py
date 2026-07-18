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

YEARS = 20
END = dt.date.today()
START = END - dt.timedelta(days=365 * YEARS + 10)
KRX_READY = bool(os.getenv("KRX_ID") and os.getenv("KRX_PW"))

series = {}


def downsample(pts):
    """2년 이전 구간만 주기별로 솎아냄: 일별 1/5, 주간 1/2, 월간 이상 원본 유지"""
    cutoff = (END - dt.timedelta(days=730)).strftime("%Y-%m-%d")
    old_p = [p for p in pts if p[0] < cutoff]
    new_p = [p for p in pts if p[0] >= cutoff]
    if len(pts) >= 2:
        span = (dt.date.fromisoformat(pts[-1][0]) - dt.date.fromisoformat(pts[0][0])).days
        gap = span / max(len(pts) - 1, 1)
    else:
        gap = 1
    step = 1 if gap >= 20 else (2 if gap >= 5 else 5)
    return old_p[::step] + new_p


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
        ("RE_US_CS",    "CSUSHPINSA",      "미국 주택가격(케이스-실러)", "REALTY", "지수", None),
        ("RE_US_MORT",  "MORTGAGE30US",    "미국 모기지 30년 금리",      "REALTY", "%",    None),
        ("LIQ_US_M2",   "M2SL",            "미국 M2(전년비)",            "LIQ",    "%",    "yoy"),
        ("LIQ_US_CB",   "WALCL",           "연준 총자산(전년비)",        "LIQ",    "%",    "yoy52"),
        ("LIQ_EA_CB",   "ECBASSETSW",      "ECB 총자산(전년비)",         "LIQ",    "%",    "yoy52"),
        ("LIQ_JP_CB",   "JPNASSETS",       "일본은행 총자산(전년비)",    "LIQ",    "%",    "yoy"),
        ("RE_EA_BIS",   "QXMR628BIS",      "유로존 주택가격(BIS 분기)",  "REALTY", "지수", None),
        ("RE_UK_BIS",   "QGBR628BIS",      "영국 주택가격(BIS 분기)",    "REALTY", "지수", None),
        ("RE_CN_BIS",   "QCNR628BIS",      "중국 주택가격(BIS 분기)",    "REALTY", "지수", None),
        ("RE_JP_BIS",   "QJPR628BIS",      "일본 주택가격(BIS 분기)",    "REALTY", "지수", None),
        ("GDP_US_NOM",  "GDP",             "미국 명목 GDP(전년비)",      "GDP",    "%",    "yoy4"),
        ("GDP_US_REAL", "GDPC1",           "미국 실질 GDP(전년비)",      "GDP",    "%",    "yoy4"),
    ]
    for k, sid, lb, grp, unit, tf in fred_items:
        try:
            s = fred_series(sid, trim=(tf is None))
            if tf:
                s = yoy(s, {"yoy52": 52, "yoy4": 4}.get(tf, 12))
            add(k, lb, grp, s, unit)
        except Exception as e:
            print(f"[FAIL] {k}({sid}): {e}")

    ea_err = ""
    for sid in ("CP0000EZ19M086NEST", "CP0000EZ19M086NEA"):
        try:
            s = yoy(fred_series(sid, trim=False))
            if add("ECON_EA_CPI", "유로존 HICP(전년비)", "ECON", s, "%"):
                print(f"       (유로존 HICP: {sid})")
                break
        except Exception as e:
            ea_err = str(e)[:120]
    else:
        print(f"[FAIL] ECON_EA_CPI: {ea_err}")
except Exception as e:
    print("[FRED 수집 실패]", e)

# ──────────────── 한국·국제 지표 (한국은행 ECOS, 인증키 필요) ────────────────
ECOS_KEY = os.getenv("ECOS_KEY")
if ECOS_KEY:
    import requests

    def ecos_rows(path):
        js = requests.get("https://ecos.bok.or.kr/api/" + path, timeout=60).json()
        for v in js.values():
            if isinstance(v, dict) and "row" in v:
                return v["row"]
        return []

    f_m = (END - dt.timedelta(days=365 * (YEARS + 2))).strftime("%Y%m")
    t_m = END.strftime("%Y%m")

    def ecos_series(stat, item_path):
        rows = ecos_rows(f"StatisticSearch/{ECOS_KEY}/json/kr/1/2000/{stat}/M/{f_m}/{t_m}/{item_path}")
        if not rows:
            return None
        return pd.Series({pd.Timestamp(r["TIME"][:4] + "-" + r["TIME"][4:6] + "-01"):
                          float(r["DATA_VALUE"]) for r in rows}).sort_index()

    def ecos_series_q(stat, item_path):
        y0, y1 = START.year, END.year
        for f_q, t_q in ((f"{y0}Q1", f"{y1}Q4"), (f"{y0}1", f"{y1}4")):
            rows = ecos_rows(f"StatisticSearch/{ECOS_KEY}/json/kr/1/2000/{stat}/Q/{f_q}/{t_q}/{item_path}")
            if not rows:
                continue
            out = {}
            for r in rows:
                t = str(r["TIME"]).upper()
                try:
                    if "Q" in t:
                        y, q = int(t[:4]), int(t.split("Q")[1])
                    elif len(t) == 5:
                        y, q = int(t[:4]), int(t[4])
                    else:
                        continue
                    out[pd.Timestamp(y, q * 3, 1)] = float(r["DATA_VALUE"])
                except Exception:
                    pass
            if out:
                return pd.Series(out).sort_index()
        return None

    def ecos_series_a(stat, item_path):
        y0, y1 = START.year, END.year
        rows = ecos_rows(f"StatisticSearch/{ECOS_KEY}/json/kr/1/2000/{stat}/A/{y0}/{y1}/{item_path}")
        out = {}
        for r in rows or []:
            t = str(r["TIME"])[:4]
            try:
                out[pd.Timestamp(int(t), 12, 1)] = float(r["DATA_VALUE"])
            except Exception:
                pass
        return pd.Series(out).sort_index() if out else None

    def ecos_items(stat):
        out = []
        for p in range(3):
            rows = ecos_rows(f"StatisticItemList/{ECOS_KEY}/json/kr/{p*1000+1}/{(p+1)*1000}/{stat}")
            if not rows:
                break
            out += rows
        return out

    _c = {"tables": None}

    def ecos_tables():
        if _c["tables"] is None:
            out = []
            for p in range(8):
                rows = ecos_rows(f"StatisticTableList/{ECOS_KEY}/json/kr/{p*1000+1}/{(p+1)*1000}")
                if not rows:
                    break
                out += rows
            _c["tables"] = out
        return _c["tables"]

    def ecos_find_stat(kws):
        hits = []
        for r in ecos_tables():
            nm = str(r.get("STAT_NAME", ""))
            if all(k in nm for k in kws) and str(r.get("SRCH_YN", "Y")) != "N":
                hits.append((nm, r.get("STAT_CODE")))
        hits.sort(key=lambda x: len(x[0]))
        return hits[0] if hits else (None, None)

    def ecos_item_path(stat, pick):
        rows = ecos_items(stat)
        grps, order = {}, []
        for r in rows:
            g = str(r.get("GRP_CODE") or "G1")
            if g not in grps:
                grps[g] = []
                order.append(g)
            grps[g].append(r)
        path, hit = [], None
        for g in order:
            code = None
            for r in grps[g]:
                nm = str(r.get("ITEM_NAME", "")).replace(" ", "")
                if pick(nm):
                    code, hit = r.get("ITEM_CODE"), nm
                    break
            if code is None:
                code = grps[g][0].get("ITEM_CODE")
            path.append(str(code))
        return "/".join(path), hit, rows

    def trim_yoy(s, n=12):
        if s is None:
            return None
        if n:
            s = (s.pct_change(n) * 100).dropna()
        return s[s.index >= pd.Timestamp(START)]

    def item_names(rows, m=12):
        seen, out = set(), []
        for r in rows:
            nm = str(r.get("ITEM_NAME", ""))
            if nm not in seen:
                seen.add(nm)
                out.append(nm)
            if len(out) >= m:
                break
        return ", ".join(out)

    # 1) 한국 CPI 총지수 (901Y009 / 0)
    try:
        s = trim_yoy(ecos_series("901Y009", "0"))
        if s is None:
            raise RuntimeError("응답 없음")
        add("ECON_KR_CPI", "한국 CPI(전년비)", "ECON", s, "%")
    except Exception as e:
        print(f"[FAIL] ECON_KR_CPI(ECOS): {str(e)[:150]}")

    # 2) 한국 근원 CPI: '소비자물가' 계열 통계표 순회, 제외지수 항목 탐색
    try:
        stats = ["901Y009"]
        for r in ecos_tables():
            nm = str(r.get("STAT_NAME", ""))
            if "소비자물가" in nm and str(r.get("SRCH_YN", "Y")) != "N":
                stats.append(str(r.get("STAT_CODE")))
        seen, done, tried = set(), False, []
        for stat in stats[:10]:
            if stat in seen:
                continue
            seen.add(stat)
            code, hit = None, None
            for r in ecos_items(stat):
                nm = str(r.get("ITEM_NAME", "")).replace(" ", "")
                if ("농산물" in nm and "석유류" in nm) or ("식료품" in nm and "에너지" in nm):
                    code, hit = r.get("ITEM_CODE"), nm
                    break
            if not code:
                tried.append(stat)
                continue
            raw = ecos_series(stat, str(code))
            if raw is None:
                tried.append(f"{stat}/{code}:데이터없음")
                continue
            s = trim_yoy(raw) if raw.median() > 30 else trim_yoy(raw, n=None)
            add("ECON_KR_CORE", "한국 근원 CPI(전년비)", "ECON", s, "%")
            print(f"       (근원 CPI: {stat} / {code} / {hit})")
            done = True
            break
        if not done:
            raise RuntimeError("제외지수 항목 미발견 · 시도 통계표: " + ", ".join(tried[:8]))
    except Exception as e:
        print(f"[FAIL] ECON_KR_CORE(ECOS): {str(e)[:250]}")

    # 3) 국제 주요국 실업률: 한국·일본·영국
    try:
        nm_u, stat_u = ecos_find_stat(["주요국", "실업률"])
        if not stat_u:
            raise RuntimeError("실업률 통계표 미발견")
        rows_u = ecos_items(stat_u)
        nmap_u = {}
        for r in rows_u:
            nmap_u[str(r.get("ITEM_NAME", "")).replace(" ", "")] = str(r.get("ITEM_CODE"))
            nmap_u[str(r.get("ITEM_CODE"))] = str(r.get("ITEM_CODE"))
        for key, cc, label in [("ECON_KR_UNEMP", "한국", "한국 실업률"),
                               ("ECON_JP_UNEMP", "일본", "일본 실업률"),
                               ("ECON_UK_UNEMP", "영국", "영국 실업률")]:
            try:
                if cc not in nmap_u:
                    print(f"[MISS] {key}: '{cc}' 항목 없음")
                    continue
                s = trim_yoy(ecos_series(stat_u, nmap_u[cc]), n=None)
                if s is None:
                    raise RuntimeError("데이터 없음")
                add(key, label, "ECON", s, "%")
            except Exception as e:
                print(f"[FAIL] {key}(ECOS): {str(e)[:150]}")
        print(f"       (실업률 통계표: {nm_u} / {stat_u} · 항목: {item_names(rows_u)})")
    except Exception as e:
        print(f"[FAIL] 실업률(ECOS): {str(e)[:200]}")

    # 4) 국제 주요국 소비자물가: 일본·영국·중국
    try:
        nm_c, stat_c = ecos_find_stat(["주요국", "소비자물가"])
        if not stat_c:
            raise RuntimeError("국제 소비자물가 통계표 미발견")
        rows_c = ecos_items(stat_c)
        nmap_c = {}
        for r in rows_c:
            nmap_c[str(r.get("ITEM_NAME", "")).replace(" ", "")] = str(r.get("ITEM_CODE"))
            nmap_c[str(r.get("ITEM_CODE"))] = str(r.get("ITEM_CODE"))
        for key, cc, label in [("ECON_JP_CPI", "일본", "일본 CPI(전년비)"),
                               ("ECON_UK_CPI", "영국", "영국 CPI(전년비)"),
                               ("ECON_CN_CPI", "중국", "중국 CPI(전년비)")]:
            try:
                if cc not in nmap_c:
                    print(f"[MISS] {key}: '{cc}' 항목 없음")
                    continue
                raw = ecos_series(stat_c, nmap_c[cc])
                if raw is None:
                    raise RuntimeError("데이터 없음")
                s = trim_yoy(raw) if raw.median() > 30 else trim_yoy(raw, n=None)
                add(key, label, "ECON", s, "%")
            except Exception as e:
                print(f"[FAIL] {key}(ECOS): {str(e)[:150]}")
        print(f"       (국제 CPI 통계표: {nm_c} / {stat_c} · 항목: {item_names(rows_c)})")
    except Exception as e:
        print(f"[FAIL] 국제 CPI(ECOS): {str(e)[:200]}")

    # 5) 한국 M2: 통계표 탐색 + 고정 코드 병행, 항목 경로 자동 구성
    try:
        cand = []
        for r in ecos_tables():
            nm = str(r.get("STAT_NAME", ""))
            if "M2" in nm and str(r.get("SRCH_YN", "Y")) != "N":
                cand.append((len(nm), str(r.get("STAT_CODE")), nm))
        cand.sort()
        stats = [c[1] for c in cand[:4]] + ["161Y013", "101Y004", "101Y003"]
        seen, got, tried = set(), False, []
        for stat in stats:
            if stat in seen:
                continue
            seen.add(stat)
            path, hit, rows = ecos_item_path(stat, lambda n: n == "M2" or n.startswith("M2("))
            if not hit:
                tried.append(stat + ":항목없음")
                continue
            s = trim_yoy(ecos_series(stat, path))
            if s is None or len(s) == 0 or (pd.Timestamp(END) - s.index[-1]).days > 400:
                tried.append(f"{stat}/{path}:데이터없음·갱신중단")
                continue
            if add("LIQ_KR_M2", "한국 M2(전년비)", "LIQ", s, "%"):
                print(f"       (한국 M2: {stat} / {path} / {hit})")
                got = True
                break
        if not got:
            raise RuntimeError("시도: " + " | ".join(tried[:6]))
    except Exception as e:
        print(f"[FAIL] LIQ_KR_M2(ECOS): {str(e)[:250]}")

    # 6) GDP: 국제 주요국 실질 성장률(분기)
    try:
        nm_g, stat_g = None, None
        for kws in (["주요국", "경제성장률"], ["주요국", "성장률"], ["주요국", "GDP"]):
            best = None
            for r in ecos_tables():
                nm = str(r.get("STAT_NAME", ""))
                if all(k in nm for k in kws) and "1인당" not in nm \
                        and str(r.get("SRCH_YN", "Y")) != "N":
                    if best is None or len(nm) < len(best[0]):
                        best = (nm, str(r.get("STAT_CODE")))
            if best:
                nm_g, stat_g = best
                break
        if not stat_g:
            raise RuntimeError("국제 GDP 통계표 미발견")
        rows_g = ecos_items(stat_g)
        nmap_g = {str(r.get("ITEM_NAME", "")).replace(" ", ""): str(r.get("ITEM_CODE")) for r in rows_g}
        for key, cc, label in [("GDP_KR_REAL", "한국", "한국 실질 GDP(전년비)"),
                               ("GDP_EA_REAL", "유로존", "유로존 실질 GDP(전년비)"),
                               ("GDP_UK_REAL", "영국", "영국 실질 GDP(전년비)"),
                               ("GDP_CN_REAL", "중국", "중국 실질 GDP(전년비)"),
                               ("GDP_JP_REAL", "일본", "일본 실질 GDP(전년비)")]:
            try:
                code = nmap_g.get(cc)
                if not code and cc == "유로존":
                    for nm2, cd2 in nmap_g.items():
                        if "유로" in nm2:
                            code = cd2
                            break
                if not code:
                    print(f"[MISS] {key}: '{cc}' 항목 없음")
                    continue
                raw = ecos_series_q(stat_g, code)
                if raw is None:
                    raw = ecos_series_a(stat_g, code)
                if raw is None:
                    raise RuntimeError("데이터 없음(분기·연간)")
                s = raw if raw.abs().median() < 30 else (raw.pct_change(4) * 100).dropna()
                s = s[s.index >= pd.Timestamp(START)]
                add(key, label, "GDP", s, "%")
            except Exception as e:
                print(f"[FAIL] {key}(ECOS): {str(e)[:120]}")
        print(f"       (국제 GDP 통계표: {nm_g} / {stat_g} · 항목: {item_names(rows_g)})")
    except Exception as e:
        print(f"[FAIL] 국제 GDP(ECOS): {str(e)[:200]}")

    # 7) 한국 명목 GDP: 국민계정 통계표 탐색(분기)
    try:
        cands = []
        for r in ecos_tables():
            nm = str(r.get("STAT_NAME", ""))
            if "국내총생산" in nm and "명목" in nm and str(r.get("SRCH_YN", "Y")) != "N":
                cands.append((len(nm), nm, str(r.get("STAT_CODE"))))
        cands.sort()
        done, tried = False, []
        for _, nm, stat in cands[:5]:
            path, hit, rows = ecos_item_path(stat, lambda n: "국내총생산" in n)
            raw = ecos_series_q(stat, path)
            if raw is None:
                tried.append(nm)
                continue
            s = (raw.pct_change(4) * 100).dropna() if raw.abs().median() > 50 else raw
            s = s[s.index >= pd.Timestamp(START)]
            if add("GDP_KR_NOM", "한국 명목 GDP(전년비)", "GDP", s, "%"):
                print(f"       (한국 명목 GDP: {nm} / {stat} / {path})")
                done = True
                break
        if not done:
            raise RuntimeError(("시도: " + " | ".join(tried[:5])) if tried else "명목 GDP 통계표 미발견")
    except Exception as e:
        print(f"[FAIL] GDP_KR_NOM(ECOS): {str(e)[:200]}")

    # 8) 한국 정기예금 금리(예금은행 신규취급액 기준, 월별)
    try:
        cands = []
        for r in ecos_tables():
            nm = str(r.get("STAT_NAME", ""))
            if "수신금리" in nm and str(r.get("SRCH_YN", "Y")) != "N":
                pri = 0 if "신규" in nm else 1
                cands.append((pri, len(nm), nm, str(r.get("STAT_CODE"))))
        cands.sort()
        pool, seenp = [], set()
        for _, _, nm, stat in cands[:5]:
            if stat not in seenp:
                pool.append((nm, stat))
                seenp.add(stat)
        if "121Y002" not in seenp:
            pool.append(("예금은행 가중평균 수신금리(고정코드)", "121Y002"))
        done, tried = False, []
        for nm, stat in pool:
            path, hit, rows = ecos_item_path(
                stat, lambda n: n == "정기예금" or n.startswith("정기예금("))
            if not hit:
                tried.append(nm + ":항목없음(" + item_names(rows, 6) + ")")
                continue
            s = trim_yoy(ecos_series(stat, path), n=None)
            if s is None or len(s) == 0 or (pd.Timestamp(END) - s.index[-1]).days > 400:
                tried.append(f"{nm}/{path}:데이터없음·중단")
                continue
            if add("RATE_KR_DEPO", "한국 정기예금 금리(신규, 월별)", "DEPO", s, "%"):
                print(f"       (정기예금 금리: {nm} / {stat} / {path})")
                done = True
                break
        if not done:
            raise RuntimeError(("시도: " + " | ".join(tried[:5])) if tried else "수신금리 통계표 미발견")
    except Exception as e:
        print(f"[FAIL] RATE_KR_DEPO(ECOS): {str(e)[:200]}")
else:
    print("[안내] ECOS_KEY 미설정 → 한국·국제(ECOS) 지표는 건너뜁니다.")
    print("       ecos.bok.or.kr 무료 인증키 발급 후 ECOS_KEY 설정 시 수집됩니다.")

# ──────────────── 국내 부동산 (한국은행 ECOS 등재 주택가격지수) ────────────────
# 로컬·클라우드 어디서나 동일한 데이터를 쓰도록 ECOS로 일원화
# (부동산원 R-ONE API는 해외 서버 접속을 차단해 클라우드 수집이 불가)
if os.getenv("ECOS_KEY"):
    try:
        def ecos_house_cands(kw):
            out = []
            for r in ecos_tables():
                nm = str(r.get("STAT_NAME", ""))
                if kw in nm and "지수" in nm and str(r.get("SRCH_YN", "Y")) != "N":
                    pri = 0 if "부동산원" in nm else (2 if "KB" in nm.upper() else 1)
                    out.append((pri, len(nm), nm, str(r.get("STAT_CODE"))))
            out.sort()
            return [(nm, st) for _, _, nm, st in out[:5]]

        for key, kw, base in [
            ("RE_KR_APT", "매매가격", "전국 아파트 매매가격지수"),
            ("RE_KR_JS",  "전세가격", "전국 아파트 전세가격지수"),
            ("RE_KR_WS",  "월세",     "전국 아파트 월세가격지수"),
        ]:
            best, errs = None, []
            for nm, stat in ecos_house_cands(kw):
                try:
                    path, hit, rows = ecos_item_path(stat, lambda n: n == "전국" or "아파트" in n)
                    raw = ecos_series(stat, path)
                    if raw is None:
                        errs.append(f"{nm}:데이터없음")
                        continue
                    s = raw[raw.index >= pd.Timestamp(START)]
                    if len(s) < 12 or (pd.Timestamp(END) - s.index[-1]).days > 400:
                        errs.append(f"{nm}:{len(s)}점·구간부족(최근 {s.index[-1].date() if len(s) else '없음'})")
                        continue
                    if best is None or len(s) > best[0]:
                        best = (len(s), nm, stat, path, s)
                except Exception as e:
                    errs.append(f"{nm}: {str(e)[:60]}")
            if best:
                _, nm, stat, path, s = best
                src_tag = "부동산원" if "부동산원" in nm else ("KB" if "KB" in nm.upper() else "ECOS")
                add(key, base + f"(월간·{src_tag})", "REALTY", s, "지수")
                print(f"       ({key} 채택: {nm} / {stat} / {path} · 최장 {len(s)}개월)")
            else:
                print(f"[FAIL] {key}(ECOS): " + " | ".join(errs[:4]))
    except Exception as e:
        print(f"[FAIL] 주택가격지수(ECOS): {str(e)[:200]}")
else:
    print("[안내] ECOS_KEY 미설정 → 한국 주택가격지수는 건너뜁니다.")

# ──────────────── 주요 기사 수집 (해외 경제 RSS 3종, 누적) ────────────────
try:
    import requests
    import xml.etree.ElementTree as ET
    import json as _json
    import re as _re
    import hashlib

    feeds = [
        ("https://www.cnbc.com/id/100003114/device/rss/rss.html", "CNBC"),
        ("https://feeds.content.dowjones.io/public/rss/mw_topstories", "MarketWatch"),
        ("https://finance.yahoo.com/news/rssindex", "Yahoo Finance"),
    ]
    today = END.isoformat()
    buckets = []
    for furl, fsrc in feeds:
        try:
            xmls = requests.get(furl, timeout=30,
                                headers={"User-Agent": "Mozilla/5.0"}).content
            root = ET.fromstring(xmls)
            lst = []
            for it in root.iter("item"):
                t = (it.findtext("title") or "").strip()
                u = (it.findtext("link") or "").strip()
                if not t or not u.startswith("http"):
                    continue
                iid = hashlib.md5(t.encode("utf-8")).hexdigest()[:12]
                lst.append({"d": today, "t": t, "s": fsrc, "u": u, "id": iid})
                if len(lst) >= 6:
                    break
            buckets.append(lst)
        except Exception as e:
            print(f"[MISS] 기사 피드({fsrc}): {str(e)[:80]}")
    fresh, idx, fseen = [], 0, set()
    while len(fresh) < 10:
        added = False
        for b in buckets:
            if idx < len(b) and len(fresh) < 10 and b[idx]["id"] not in fseen:
                fresh.append(b[idx])
                fseen.add(b[idx]["id"])
                added = True
        if not added:
            break
        idx += 1
    olds = []
    try:
        with open("data_news.js", encoding="utf-8") as fp:
            m = _re.search(r"=\s*(\{.*\});?\s*$", fp.read(), _re.S)
            if m:
                olds = _json.loads(m.group(1)).get("items", [])
    except Exception:
        pass
    seen = {o.get("id") for o in olds}
    today_cnt = sum(1 for o in olds if o.get("d") == today)
    adds = []
    for n in fresh:
        if n["id"] in seen or today_cnt + len(adds) >= 10:
            continue
        adds.append(n)
    items = (adds + olds)[:1200]
    with open("data_news.js", "w", encoding="utf-8") as fp:
        fp.write("window.NEWS_DATA=" + _json.dumps(
            {"generated": today, "items": items}, ensure_ascii=False) + ";")
    print(f"[NEWS] 신규 {len(adds)}건 · 누적 {len(items)}건 저장(data_news.js)")
except Exception as e:
    print(f"[FAIL] 주요 기사 수집: {str(e)[:200]}")
    if not os.path.exists("data_news.js"):
        with open("data_news.js", "w", encoding="utf-8") as fp:
            fp.write('window.NEWS_DATA={"generated":"","items":[]};')

# ──────────────── 국내 분양 청약 일정 (청약홈 오픈API, 인증키 필요) ────────────────
SUB_KEY = os.getenv("SUB_KEY")
if SUB_KEY:
    try:
        import requests
        import json as _json
        today_s = END.strftime("%Y-%m-%d")
        subs = []

        def pickk(d, pats):
            for k2, v2 in d.items():
                ku = str(k2).upper()
                if all(p in ku for p in pats):
                    return v2 if v2 is not None else ""
            return ""

        for ep, typ in [
            ("getAPTLttotPblancDetail", "일반분양"),
            ("getRemndrLttotPblancDetail", "무순위·잔여"),
        ]:
            try:
                js = requests.get(
                    f"https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/{ep}",
                    params={"page": 1, "perPage": 100, "serviceKey": SUB_KEY,
                            "cond[RCEPT_ENDDE::GTE]": today_s},
                    timeout=60, headers={"User-Agent": "Mozilla/5.0"}).json()
                rows = js.get("data")
                if rows is None:
                    raise RuntimeError(str(js)[:180])
                got0 = len(subs)
                for r in rows:
                    nm = pickk(r, ["HOUSE_NM"])
                    rs = str(pickk(r, ["RCEPT_BGNDE"]))[:10]
                    re_ = str(pickk(r, ["RCEPT_ENDDE"]))[:10]
                    an = str(pickk(r, ["PRZWNER"]))[:10]
                    rg = pickk(r, ["SUBSCRPT_AREA"]) or str(pickk(r, ["ADRES"]))[:24]
                    if not nm or not rs:
                        continue
                    subs.append({"name": str(nm), "region": str(rg), "type": typ,
                                 "r_start": rs, "r_end": re_, "announce": an})
                print(f"[SUB]  {typ}: 수신 {len(rows)}건 · 채택 {len(subs)-got0}건")
                if rows and len(subs) == got0:
                    print("       (필드 확인 필요, 키 예시: " + ", ".join(list(rows[0].keys())[:10]) + ")")
            except Exception as e:
                print(f"[FAIL] 청약({typ}): {str(e)[:150]}")
        subs.sort(key=lambda x: x.get("r_start") or "9999")
        with open("data_sub.js", "w", encoding="utf-8") as fp:
            fp.write("window.SUB_DATA=" + _json.dumps(
                {"generated": today_s, "items": subs[:200]}, ensure_ascii=False) + ";")
        print(f"[SUB]  청약 일정 {len(subs)}건 저장(data_sub.js)")
    except Exception as e:
        print(f"[FAIL] 청약 일정 수집: {str(e)[:200]}")
else:
    print("[안내] SUB_KEY 미설정 → 청약홈 분양 일정은 건너뜁니다.")
    print("       공공데이터포털(data.go.kr) '청약홈 분양정보' 활용신청 후 SUB_KEY 설정 시 수집됩니다.")
if not os.path.exists("data_sub.js"):
    with open("data_sub.js", "w", encoding="utf-8") as fp:
        fp.write('window.SUB_DATA={"generated":"","items":[]};')

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

        # ── 관심 주가 (직접 추가 관리) ──
        # 추가 방법: "키": ("종목코드", "표시명") 한 줄 추가 → 다음 수집부터 자동 반영
        watch = {
            "W_NAVER": ("035420", "네이버"),
            "W_SKSIG": ("260870", "SK시그넷"),
        }
        for k, (code, lb) in watch.items():
            try:
                s = stock.get_market_ohlcv_by_date(f, t, code)["종가"]
                add(k, lb, "WATCH", s, "원")
            except Exception as e:
                print(f"[FAIL] {k}({code}): {e}")
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
