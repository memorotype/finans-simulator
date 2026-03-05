from dataclasses import dataclass
from io import BytesIO
import pandas as pd
import numpy as np
import math

@dataclass
class AmortResult:
    monthly_payment: float
    interest_paid_10y: float
    remaining_balance_10y: float
    schedule_monthly: pd.DataFrame
    schedule_yearly: pd.DataFrame

def amortize(loan: float, annual_rate: float, initial_tilgung: float, months_total: int = 120) -> AmortResult:
    """Aylık annüite: ödeme = loan * (faiz/12 + tilgung/12). 10 yıl (120 ay) simülasyon."""
    if loan <= 0:
        # Boş tablo dönelim
        cols = ["Ay", "Yıl", "Aylık Ödeme", "Faiz", "Ana Para", "Kalan Borç"]
        empty = pd.DataFrame(columns=cols)
        return AmortResult(0.0, 0.0, 0.0, empty, empty)

    r_m = annual_rate / 12.0
    t_m = initial_tilgung / 12.0
    monthly_payment = loan * (r_m + t_m)

    balance = loan
    rows = []
    interest_paid = 0.0

    for m in range(1, months_total + 1):
        interest = balance * r_m
        principal = monthly_payment - interest
        balance = max(balance - principal, 0.0)
        interest_paid += interest
        rows.append([m, (m - 1)//12 + 1, monthly_payment, interest, principal, balance])

    df = pd.DataFrame(rows, columns=["Ay", "Yıl", "Aylık Ödeme", "Faiz", "Ana Para", "Kalan Borç"])
    yearly = df.groupby("Yıl").agg({"Aylık Ödeme":"sum","Faiz":"sum","Ana Para":"sum","Kalan Borç":"last"}).reset_index()
    return AmortResult(
        monthly_payment=monthly_payment,
        interest_paid_10y=interest_paid,
        remaining_balance_10y=balance,
        schedule_monthly=df,
        schedule_yearly=yearly
    )

def future_value(principal: float, net_rate_annual: float, years: int = 10) -> float:
    return principal * ((1 + net_rate_annual) ** years)

def net_benefit(ev_fiyat: float, nakit: float, kredi: float,
                annual_rate: float, tilgung: float, masraf_toplam: float,
                invest_return: float, years: int = 10) -> float:
    """Net fayda = FV(rezerv) - faiz(10y) - kalan borç(10y)"""
    pesinat = ev_fiyat - kredi
    rezerv = nakit - pesinat - masraf_toplam
    if rezerv < 0:
        return -1e18
    amort = amortize(kredi, annual_rate, tilgung, months_total=years*12)
    fv = future_value(rezerv, invest_return, years)
    return fv - amort.interest_paid_10y - amort.remaining_balance_10y

def optimize_loan_ratio(ev_fiyat: float, nakit: float,
                        annual_rate: float, tilgung: float, masraf_toplam: float,
                        invest_return: float, years: int = 10, step: float = 0.01) -> float:
    """0–100% arası kredi oranında en yüksek net fayda veren oranı bul."""
    best_ratio = 0.0
    best_score = -1e18
    ratios = np.arange(0, 1.0 + step, step)
    for r in ratios:
        kredi = ev_fiyat * r
        score = net_benefit(ev_fiyat, nakit, kredi, annual_rate, tilgung, masraf_toplam, invest_return, years)
        if score > best_score:
            best_score = score
            best_ratio = float(r)
    return best_ratio

def simulate_interest_sweep(ev_fiyat: float, nakit: float, kredi: float,
                            rate_min: float, rate_max: float, rate_step: float,
                            tilgung: float, masraf_toplam: float,
                            invest_return: float, years: int = 10,
                            optimize_each_rate: bool = False):
    """Faiz aralığına göre net fayda eğrisi (manuel kredi veya her noktada optimize)."""
    rates = np.arange(rate_min, rate_max + 1e-9, rate_step)
    results = []
    for r in rates:
        if optimize_each_rate:
            best_r = optimize_loan_ratio(ev_fiyat, nakit, r, tilgung, masraf_toplam, invest_return, years)
            kredi_used = ev_fiyat * best_r
        else:
            kredi_used = kredi
        score = net_benefit(ev_fiyat, nakit, kredi_used, r, tilgung, masraf_toplam, invest_return, years)
        results.append((float(r), float(kredi_used), float(score)))
    df = pd.DataFrame(results, columns=["Faiz", "Kredi", "NetFayda"])
    return df

def simulate_price_scenarios(ev_fiyat: float, growth_list_pct, kredi: float,
                             annual_rate: float, tilgung: float, masraf_toplam: float,
                             nakit: float, invest_return: float, years: int = 10):
    """Fiyat artışı senaryolarında 10Y net servet: EvDeğeri - KalanBorc + FV(Rezerv)"""
    pesinat = ev_fiyat - kredi
    rezerv = nakit - pesinat - masraf_toplam
    amort = amortize(kredi, annual_rate, tilgung, months_total=years*12)
    fv = future_value(rezerv, invest_return, years)
    rows = []
    for g in growth_list_pct:
        ev_future = ev_fiyat * ((1 + g/100.0) ** years)
        net_servet = ev_future - amort.remaining_balance_10y + fv
        rows.append([g, ev_future, amort.remaining_balance_10y, fv, net_servet])
    df = pd.DataFrame(rows, columns=["Büyüme(%)","Ev Değeri 10Y","Kalan Borç 10Y","FV Rezerv 10Y","Net Servet 10Y"])
    return df

def to_excel_bytes(dfs: dict) -> BytesIO:
    """Birden fazla DataFrame’i Excel’e yazar ve bytes döner."""
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as writer:
        for name, df in dfs.items():
            df.to_excel(writer, sheet_name=name[:31], index=False)
    bio.seek(0)
    return bio
