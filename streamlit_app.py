import streamlit as st
import pandas as pd
import numpy as np
import math
import matplotlib.pyplot as plt

st.set_page_config(page_title="Finans Simülatörü", page_icon="🏠", layout="wide")

st.title("🏠 Finansal Konut + Kredi Optimizasyon Simülatörü")
st.markdown("Kredi – nakit oranlarını optimize eden, grafikli, gelecekteki maliyetleri hesaplayan interaktif uygulama.")

# ---------------------
# INPUTS
# ---------------------
st.sidebar.header("📌 Girdi Bilgileri")

ev_fiyati = st.sidebar.number_input("Ev fiyatı (€)", value=800000)
nakit = st.sidebar.number_input("Toplam nakit (€)", value=1000000)

kredi_faiz = st.sidebar.number_input("Kredi faiz oranı (%)", value=3.5) / 100
tilgung = st.sidebar.number_input("Başlangıç Tilgung (%)", value=3.0) / 100
kredi_yil = st.sidebar.number_input("Kredi süresi (yıl)", value=10)

yatirim_getiri = st.sidebar.number_input("Yıllık net yatırım getirisi (%)", value=2.0) / 100

ges = st.sidebar.number_input("Grunderwerbsteuer (%)", value=6.0) / 100
noter = st.sidebar.number_input("Noter + Grundbuch (%)", value=2.0) / 100
makler = st.sidebar.number_input("Makler (%)", value=3.57) / 100

manual_kredi = st.sidebar.number_input("Manuel kredi miktarı (€)", value=400000)

# ---------------------
# COMPUTATION FUNCTIONS
# ---------------------
def amortize(loan, faiz, tilgung, months):
    aylik_faiz = faiz / 12
    aylik_tilg = tilgung / 12
    aylik_taksit = loan * (aylik_faiz + aylik_tilg)

    kalan = loan
    faiz_odeme = 0
    yillar = []
    bakiyeler = []

    for i in range(months):
        f = kalan * aylik_faiz
        p = aylik_taksit - f
        kalan -= p
        faiz_odeme += f

        if i % 12 == 0:
            yillar.append(i/12)
            bakiyeler.append(kalan)

    return aylik_taksit, faiz_odeme, max(kalan,0), yillar, bakiyeler

# ---------------------
# CALCULATE
# ---------------------
ay = kredi_yil * 12
aylik, faiz10, kalan10, yy, borc_grafik = amortize(manual_kredi, kredi_faiz, tilgung, 120)

masraf = ev_fiyati * ges + ev_fiyati * noter + ev_fiyati * makler
pesinat = ev_fiyati - manual_kredi
kalan_nakit = nakit - pesinat - masraf

fv_nakit = kalan_nakit * ((1 + yatirim_getiri)**10)
net_fayda = fv_nakit - faiz10 - kalan10

# ---------------------
# OUTPUT
# ---------------------
st.header("📊 Sonuçlar")

col1, col2, col3 = st.columns(3)

col1.metric("Aylık taksit", f"{aylik:,.2f} €")
col2.metric("10 yılda ödenen faiz", f"{faiz10:,.2f} €")
col3.metric("10 yıl sonunda kalan kredi", f"{kalan10:,.2f} €")

st.metric("10 yıl sonraki yatırım değeri (FV)", f"{fv_nakit:,.2f} €")
st.metric("Net Finansal Fayda", f"{net_fayda:,.2f} €")

# ---------------------
# GRAPH – AMORTIZATION
# ---------------------
st.header("📉 Borç Azalım Grafiği")

fig, ax = plt.subplots()
ax.plot(yy, borc_grafik)
ax.set_xlabel("Yıl")
ax.set_ylabel("Kalan Borç (€)")
ax.grid(True)
st.pyplot(fig)

# ---------------------
# OPTIMIZATION
# ---------------------
st.header("🧮 Otomatik En İyi Kredi Oranı Hesabı")

def score_for_ratio(r):
    kredi = ev_fiyati * r
    pesin = ev_fiyati - kredi
    nakit_kalan = nakit - pesin - masraf
    if nakit_kalan < 0:
        return -1e18

    aylik_o, faiz_10, kalan_10, _, _ = amortize(kredi, kredi_faiz, tilgung, 120)
    fv = nakit_kalan * ((1 + yatirim_getiri)**10)
    return fv - faiz_10 - kalan_10

ratios = np.linspace(0, 1, 101)
scores = [score_for_ratio(r) for r in ratios]

best_idx = int(np.argmax(scores))
best_ratio = ratios[best_idx]

st.success(f"Optimal kredi oranı: %{best_ratio * 100:.1f}")

fig2, ax2 = plt.subplots()
ax2.plot(ratios * 100, scores)
ax2.set_xlabel("Kredi Oranı (%)")
ax2.set_ylabel("Net Fayda (€)")
ax2.grid(True)
st.subheader("📈 Optimizasyon Grafiği")
st.pyplot(fig2)

# ---------------------
# EXCEL EXPORT
# ---------------------
st.header("📥 Excel Çıktısı")

if st.button("Excel İndir"):
    df = pd.DataFrame({
        "Yıl": yy,
        "Kalan Borç (€)": borc_grafik
    })
    df.to_excel("borc_grafik.xlsx", index=False)
    st.success("Excel başarıyla oluşturuldu! Dosya: borc_grafik.xlsx")
