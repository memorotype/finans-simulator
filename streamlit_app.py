import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from utils import amortize, optimize_loan_ratio, net_benefit, simulate_interest_sweep, simulate_price_scenarios, to_excel_bytes
import importlib

st.set_page_config(page_title="Finans Simülatörü", page_icon="🏠", layout="wide")

# ---- Language selector ----
lang_choice = st.sidebar.selectbox("Dil / Sprache / Language", ["TR","EN","DE"], index=0)
lang_module = {"TR":"languages.lang_tr", "EN":"languages.lang_en", "DE":"languages.lang_de"}[lang_choice]
T = importlib.import_module(lang_module).TEXTS

# ---- Logo ----
try:
    st.sidebar.image("assets/logo.png", width=160)
except Exception:
    st.sidebar.info(T["ui"]["logo_missing"])

st.title(T["app_title"])
st.write(T["intro"])
st.caption(T["ui"]["theme_info"])

# ---- Inputs (with tooltips) ----
st.sidebar.header(T["sidebar_header"])

ev_fiyati = st.sidebar.number_input(
    T["inputs"]["price_label"], value=800000,
    help=T["inputs"]["price_help"]
)
nakit = st.sidebar.number_input(
    T["inputs"]["cash_label"], value=1000000,
    help=T["inputs"]["cash_help"]
)
kredi_faiz = st.sidebar.number_input(
    T["inputs"]["rate_label"], value=3.5,
    help=T["inputs"]["rate_help"]
)/100
tilgung = st.sidebar.number_input(
    T["inputs"]["tilgung_label"], value=3.0,
    help=T["inputs"]["tilgung_help"]
)/100
kredi_yil = st.sidebar.number_input(
    T["inputs"]["term_label"], value=10,
    help=T["inputs"]["term_help"]
)
yatirim_getiri = st.sidebar.number_input(
    T["inputs"]["inv_label"], value=2.0,
    help=T["inputs"]["inv_help"]
)/100
ges = st.sidebar.number_input(
    T["inputs"]["ges_label"], value=6.0,
    help=T["inputs"]["ges_help"]
)/100
noter = st.sidebar.number_input(
    T["inputs"]["notary_label"], value=2.0,
    help=T["inputs"]["notary_help"]
)/100
makler = st.sidebar.number_input(
    T["inputs"]["agent_label"], value=3.57,
    help=T["inputs"]["agent_help"]
)/100
manual_kredi = st.sidebar.number_input(
    T["inputs"]["manual_loan_label"], value=400000,
    help=T["inputs"]["manual_loan_help"]
)

# Common values
masraf_toplam = ev_fiyati*ges + ev_fiyati*noter + ev_fiyati*makler

# ---- Core calculations (10Y) ----
amort = amortize(manual_kredi, kredi_faiz, tilgung, months_total=120)
pesinat = ev_fiyati - manual_kredi
rezerv = nakit - pesinat - masraf_toplam
fv10 = rezerv * ((1 + yatirim_getiri)**10)
net10 = fv10 - amort.interest_paid_10y - amort.remaining_balance_10y

# ---- Output KPIs ----
st.header(T["outputs_header"])
c1,c2,c3 = st.columns(3)
c1.metric(T["metrics"]["monthly"], f"{amort.monthly_payment:,.2f} €")
c2.metric(T["metrics"]["int10"], f"{amort.interest_paid_10y:,.2f} €")
c3.metric(T["metrics"]["rem10"], f"{amort.remaining_balance_10y:,.2f} €")
st.metric(T["metrics"]["fv10"], f"{fv10:,.2f} €")
st.metric(T["metrics"]["net"], f"{net10:,.2f} €")

# ---- Amortization Chart ----
st.header(T["charts"]["amort"])
fig, ax = plt.subplots()
ax.plot(amort.schedule_yearly["Yıl"], amort.schedule_yearly["Kalan Borç"])
ax.set_xlabel("Yıl")
ax.set_ylabel("Kalan Borç (€)")
ax.grid(True)
st.pyplot(fig, use_container_width=True)

# ---- Optimization ----
st.header(T["charts"]["opt_header"])
best_ratio = optimize_loan_ratio(ev_fiyati, nakit, kredi_faiz, tilgung, masraf_toplam, yatirim_getiri, years=10, step=0.01)
st.success(f'{T["charts"]["opt_ratio"]}: %{best_ratio*100:.1f}')

# Net fayda - oran eğrisi
import numpy as np
ratios = np.linspace(0,1,101)
scores = [ net_benefit(ev_fiyati, nakit, ev_fiyati*r, kredi_faiz, tilgung, masraf_toplam, yatirim_getiri, years=10)
           for r in ratios ]
fig2, ax2 = plt.subplots()
ax2.plot(ratios*100, scores)
ax2.set_xlabel("% Kredi Oranı")
ax2.set_ylabel("Net Fayda (€)")
ax2.grid(True)
st.subheader(T["charts"]["opt_chart"])
st.pyplot(fig2, use_container_width=True)

# ---- Multi-scenario comparison ----
# ---- Multi-scenario comparison ----
st.header(T["charts"]["multi_scen"])

# 1) Seçenekleri ve varsayılanı tanımla
options = [0, 20, 40, 60, 80, 100]
user_default = [0, 40, 50, 60, 100]  # 50 burada sorunlu

# 2) Tipleri normalize et (int’e döndür)
options = [int(x) for x in options]
user_default = [int(x) for x in user_default]

# 3) default’u options ile kesiştir (olmayanları otomatik at)
safe_default = [x for x in user_default if x in options]

# 4) multiselect
preset = st.multiselect("Kredi oranları (%)", options, default=safe_default)

# 5) Seçim boşsa kullanıcıyı yönlendir
if len(preset) == 0:
    st.warning("Lütfen en az 1 kredi oranı seçin.")
else:
    rows = []
    for pct in preset:
        r = pct / 100
        kredi_x = ev_fiyati * r
        score_x = net_benefit(
            ev_fiyati, nakit, kredi_x, kredi_faiz, tilgung,
            masraf_toplam, yatirim_getiri, years=10
        )

        # Geçersiz skorlar için güvenlik
        if score_x < -1e17:
            score_x = None

        rows.append([pct, kredi_x, score_x])

    df_multi = pd.DataFrame(rows, columns=["Kredi(%)", "Kredi(€)", "NetFayda(€)"])

    st.subheader("Tablo")
    st.dataframe(df_multi, use_container_width=True)

    if df_multi["NetFayda(€)"].isna().all():
        st.warning("Bu senaryolarda hesaplanabilir Net Fayda yok (nakit yetersiz olabilir).")
    else:
        fig3, ax3 = plt.subplots()
        plot_vals = df_multi["NetFayda(€)"].fillna(0)
        ax3.bar(df_multi["Kredi(%)"].astype(str), plot_vals)
        ax3.set_xlabel("Kredi Oranı (%)")
        ax3.set_ylabel("Net Fayda (€)")
        st.pyplot(fig3, use_container_width=True)

# ---- Interest Sweep ----
st.header(T["charts"]["interest_sweep"])
colA, colB, colC = st.columns(3)
rate_min = colA.number_input("Min Faiz (%)", value=3.0)/100
rate_max = colB.number_input("Maks Faiz (%)", value=5.0)/100
rate_step = colC.number_input("Adım (%)", value=0.25)/100
opt_each = st.checkbox("Her faiz noktasında krediyi optimize et", value=False)

df_sweep = simulate_interest_sweep(ev_fiyati, nakit, manual_kredi,
                                   rate_min, rate_max, rate_step,
                                   tilgung, masraf_toplam,
                                   yatirim_getiri, years=10,
                                   optimize_each_rate=opt_each)
st.dataframe(df_sweep, use_container_width=True)
fig4, ax4 = plt.subplots()
ax4.plot(df_sweep["Faiz"]*100, df_sweep["NetFayda"], marker="o")
ax4.set_xlabel("Faiz (%)")
ax4.set_ylabel("Net Fayda (€)")
ax4.grid(True)
st.pyplot(fig4, use_container_width=True)

# ---- Price Scenarios ----
st.header(T["charts"]["price_scen"])
growth_input = st.text_input("Yıllık büyüme senaryoları (%), virgülle ayır (örn: 0,2,4,6)", value="0,2,4,6")
growth_list = []
try:
    growth_list = [float(x.strip()) for x in growth_input.split(",") if x.strip()!=""]
except:
    st.warning("Büyüme listesi parse edilemedi. Örn: 0,2,4,6")
if growth_list:
    df_price = simulate_price_scenarios(ev_fiyati, growth_list, manual_kredi,
                                        kredi_faiz, tilgung, masraf_toplam,
                                        nakit, yatirim_getiri, years=10)
    st.dataframe(df_price, use_container_width=True)
    fig5, ax5 = plt.subplots()
    ax5.plot(df_price["Büyüme(%)"], df_price["Net Servet 10Y"], marker="o")
    ax5.set_xlabel("Yıllık Büyüme (%)")
    ax5.set_ylabel("Net Servet (10Y) (€)")
    ax5.grid(True)
    st.pyplot(fig5, use_container_width=True)

# ---- Excel Export ----
st.header(T["excel_header"])
dfs_to_export = {
    "Amort_Monthly": amort.schedule_monthly,
    "Amort_Yearly": amort.schedule_yearly
}
if growth_list:
    dfs_to_export["Price_Scenarios"] = df_price
dfs_to_export["Interest_Sweep"] = df_sweep
dfs_to_export["Multi_Ratios"] = df_multi

xlsx_bytes = to_excel_bytes(dfs_to_export)
st.download_button(
    label=T["excel_btn"],
    data=xlsx_bytes,
    file_name="finans_simulator_10Y.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
