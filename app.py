
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from urllib.parse import urlparse
from pathlib import Path

# ==========================================================
# 1. CONFIGURATION
# ==========================================================

st.set_page_config(
    page_title='Sales Dashboard',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='expanded'
)

st.title('Sales Dashboard')
st.caption('Overview of Key Business Metrics and Performance')

DATE_COL = 'Tanggal'
SALES_COL = 'Total Value exc. PPN'
CUSTOMER_COL = 'Nama Customer'
CHANNEL_COL = 'Channel'
TYPE_COL = 'Nama Tipe'
TIPE_CUSTOMER_COL = 'Tipe'

LINK = 'https://docs.google.com/spreadsheets/d/1_B08zOyIueu1daLN11ihiguHrblVXAOgwZw5ILF-spU/edit?usp=sharing'


# ==========================================================
# 2. HELPER FUNCTIONS
# ==========================================================

def read_sheet(link, sheet_name):
    sheet_id = urlparse(link).path.split('/')[3]

    url = (
        f'https://docs.google.com/spreadsheets/d/{sheet_id}'
        f'/gviz/tq?sheet={sheet_name}&tqx=out:csv'
    )

    return pd.read_csv(url)


def fmt_rp(x):
    return '-' if pd.isna(x) else f'Rp {x:,.0f}'


def fmt_pct(x):
    return '-' if pd.isna(x) else f'{x:+.2f}%'


def month_label(x):
    return pd.Period(x, freq='M').strftime('%b-%Y')


def show_chart(fig):
    st.plotly_chart(fig, use_container_width=True)


# ==========================================================
# 3. MONTHLY SUMMARY
# ==========================================================

def monthly_summary(data):

    if data.empty:
        return pd.DataFrame()

    d = data.copy()

    d['Sales_Val'] = np.where(
        d['Sales/Retur'].eq('Sales'),
        d[SALES_COL],
        0
    )

    d['Retur_Val'] = np.where(
        d['Sales/Retur'].eq('Retur'),
        d[SALES_COL],
        0
    )

    m = (
        d.groupby('Bulan', as_index=False)
        .agg(
            Sales=('Sales_Val', 'sum'),
            Retur=('Retur_Val', 'sum'),
            Active_Outlet=(CUSTOMER_COL, 'nunique')
        )
        .sort_values('Bulan')
        .reset_index(drop=True)
    )

    # Net Sales = Sales - Retur
    m['Net_Sales'] = m['Sales'] - m['Retur']

    m['Avg_Sales_Outlet'] = (
        m['Net_Sales'] /
        m['Active_Outlet'].replace(0, np.nan)
    )

    m['Sales_MoM'] = m['Net_Sales'].pct_change() * 100
    m['Outlet_MoM'] = m['Active_Outlet'].pct_change() * 100

    m['Sales_YoY'] = (
        m['Net_Sales']
        .div(m['Net_Sales'].shift(12).replace(0, np.nan))
        .sub(1) * 100
    )

    m['Outlet_YoY'] = (
        m['Active_Outlet']
        .div(m['Active_Outlet'].shift(12).replace(0, np.nan))
        .sub(1) * 100
    )

    return m


# ==========================================================
# 4. NEW OPEN OUTLET (NOO)
# ==========================================================

def new_open_outlets(data):

    code_col = 'Kode Customer'

    if data.empty or code_col not in data.columns:
        return pd.DataFrame()

    latest_month = data['Bulan'].max()

    sales = data[
        data['Sales/Retur'].eq('Sales')
    ].copy()

    sales = sales.dropna(
        subset=[DATE_COL, code_col]
    )

    if sales.empty:
        return pd.DataFrame()

    sales[code_col] = (
        sales[code_col]
        .astype(str)
        .str.strip()
    )

    latest_sales = sales[
        sales['Bulan'].eq(latest_month)
    ].copy()

    previous_sales = sales[
        sales['Bulan'].lt(latest_month)
    ]

    previous_codes = set(
        previous_sales[code_col].unique()
    )

    latest_sales = latest_sales[
        ~latest_sales[code_col].isin(previous_codes)
    ]

    if latest_sales.empty:
        return pd.DataFrame()

    if CUSTOMER_COL in latest_sales.columns:

        result = (
            latest_sales.groupby(code_col, as_index=False)
            .agg(
                **{
                    'Nama Customer': (CUSTOMER_COL, 'first'),
                    'Total Sales': (SALES_COL, 'sum')
                }
            )
        )

    else:

        result = (
            latest_sales.groupby(code_col, as_index=False)[SALES_COL]
            .sum()
            .rename(columns={SALES_COL: 'Total Sales'})
        )

    result = result.rename(
        columns={code_col: 'Kode Customer'}
    )

    result['Total Sales'] = result['Total Sales'].map(fmt_rp)

    return result.sort_values(
        'Kode Customer'
    ).reset_index(drop=True)


# ==========================================================
# 5. LOSS CUSTOMER
# Definisi:
# Sales pada 2025 tetapi tidak ada Sales pada 2026
# ==========================================================

def loss_customers(data):

    if data.empty:
        return pd.DataFrame()

    # Hanya transaksi Sales
    sales = data[
        data['Sales/Retur'].eq('Sales')
    ].copy()

    if sales.empty:
        return pd.DataFrame()

    # Identifikasi customer
    if 'Kode Customer' in sales.columns:
        key_col = 'Kode Customer'
    else:
        key_col = CUSTOMER_COL

    sales = sales.dropna(
        subset=[DATE_COL, key_col]
    ).copy()

    sales['Tahun'] = sales[DATE_COL].dt.year

    sales[key_col] = (
        sales[key_col]
        .astype(str)
        .str.strip()
    )

    sales = sales[
        sales[key_col].ne('')
    ]

    # Customer yang pernah melakukan Sales pada 2025
    customer_2025 = set(
        sales.loc[
            sales['Tahun'].eq(2025),
            key_col
        ].unique()
    )

    # Customer yang pernah melakukan Sales pada 2026
    customer_2026 = set(
        sales.loc[
            sales['Tahun'].eq(2026),
            key_col
        ].unique()
    )

    # Loss Customer
    lost_customers = customer_2025 - customer_2026

    if not lost_customers:
        return pd.DataFrame()

    # Ambil transaksi Sales tahun 2025
    lost_data = sales[
        sales['Tahun'].eq(2025) &
        sales[key_col].isin(lost_customers)
    ].copy()

    # Rekap berdasarkan customer
    if key_col == 'Kode Customer':

        result = (
            lost_data.groupby(key_col, as_index=False)
            .agg(
                **{
                    'Nama Customer': (CUSTOMER_COL, 'first'),
                    'Total Sales 2025': (SALES_COL, 'sum')
                }
            )
        )

    else:

        result = (
            lost_data.groupby(key_col, as_index=False)[SALES_COL]
            .sum()
            .rename(
                columns={
                    key_col: 'Nama Customer',
                    SALES_COL: 'Total Sales 2025'
                }
            )
        )

    if key_col == 'Kode Customer':
        result = result.rename(
            columns={key_col: 'Kode Customer'}
        )

    result['Total Sales 2025'] = (
        result['Total Sales 2025'].map(fmt_rp)
    )

    return result.reset_index(drop=True)


# ==========================================================
# 6. SIDEBAR - DATA INPUT
# ==========================================================

with st.sidebar:
    logo_path = Path(__file__).parent / 'logo.webp'

    if logo_path.exists():
        st.image(
            str(logo_path),
            width=150
        )

    st.header('Data Input')

    uploaded = st.file_uploader(
        'Upload Raw Data Excel',
        type=['xlsx', 'xls']
    )

    use_mapping = st.checkbox(
        'Ambil mapping dari Google Sheets',
        value=True
    )


if uploaded is None:

    st.info(
        'Upload file Excel melalui panel sebelah kiri '
        'untuk memulai dashboard.'
    )

    st.stop()


# ==========================================================
# 7. READ RAW DATA
# ==========================================================

try:

    raw = pd.read_excel(uploaded)

except Exception as e:

    st.error(f'File gagal dibaca: {e}')
    st.stop()


required = [
    'Faktur',
    'Qty',
    DATE_COL,
    SALES_COL,
    CUSTOMER_COL,
    CHANNEL_COL,
    TYPE_COL
]

missing = [
    c for c in required
    if c not in raw.columns
]

if missing:

    st.error(
        f'Kolom wajib tidak ditemukan: {missing}'
    )

    st.stop()


# ==========================================================
# 8. DATA CLEANING
# ==========================================================

# Simpan data asli untuk audit
raw_original = raw.copy()

# Konversi data
raw['Faktur'] = raw['Faktur'].astype('string')

raw['Qty'] = pd.to_numeric(
    raw['Qty'],
    errors='coerce'
)

raw[DATE_COL] = pd.to_datetime(
    raw[DATE_COL],
    errors='coerce'
)

raw[SALES_COL] = pd.to_numeric(
    raw[SALES_COL],
    errors='coerce'
).fillna(0)


# Identifikasi Sales dan Retur
raw['Sales/Retur'] = np.select(
    [
        raw['Faktur'].str.contains('JL', na=False),
        raw['Faktur'].str.contains('RJ', na=False)
    ],
    [
        'Sales',
        'Retur'
    ],
    default='Unknown'
)


# Identifikasi Cancel
raw['Transaksi'] = np.where(
    raw['Qty'].eq(0),
    'Cancel',
    'Transaksi'
)


# Ringkasan cleaning
total_raw = len(raw)

total_cancel = int(
    raw['Transaksi'].eq('Cancel').sum()
)

total_missing_qty = int(
    raw['Qty'].isna().sum()
)


# Keluarkan transaksi Cancel
raw = raw[
    raw['Transaksi'].ne('Cancel')
].copy()

total_clean = len(raw)


# ==========================================================
# 9. GOOGLE SHEETS MAPPING
# ==========================================================

raw['Notes For Principal'] = np.nan
raw['Notes For Customers'] = np.nan

mapping_message = 'Mapping tidak digunakan.'

if use_mapping:

    try:

        principal = read_sheet(LINK, 'principal')
        customers = read_sheet(LINK, 'customers')

        pmap = (
            principal.dropna(subset=['Nama Tipe'])
            .drop_duplicates('Nama Tipe')
            .set_index('Nama Tipe')['Keterangan']
            .to_dict()
        )

        cmap = (
            customers.dropna(subset=['Nama Customer'])
            .drop_duplicates('Nama Customer')
            .set_index('Nama Customer')['Keterangan']
            .to_dict()
        )

        raw['Notes For Principal'] = (
            raw['Nama Tipe'].map(pmap)
        )

        raw['Notes For Customers'] = (
            raw['Nama Customer'].map(cmap)
        )

        mapping_message = (
            'Mapping Principal dan Customer berhasil dimuat.'
        )

    except Exception as e:

        mapping_message = f'Mapping gagal dimuat: {e}'

        st.warning(
            mapping_message +
            ' Pastikan Google Sheets dapat diakses '
            'dan nama tab/kolom sesuai.'
        )


filtered_raw = raw[
    raw['Notes For Principal'].isna() &
    raw['Notes For Customers'].isna()
].copy()


# ==========================================================
# 10. DATA QUALITY SUMMARY
# ==========================================================

with st.expander('Ringkasan data dan mapping'):

    st.write(mapping_message)

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        'Total Raw Data',
        f'{total_raw:,}'
    )

    c2.metric(
        'Transaksi Cancel',
        f'{total_cancel:,}'
    )

    c3.metric(
        'Data Setelah Cleaning',
        f'{total_clean:,}'
    )

    c4.metric(
        'Qty Kosong',
        f'{total_missing_qty:,}'
    )

    c5.metric(
        'Data tanpa Mapping',
        f'{len(filtered_raw):,}'
    )

    st.caption(
        'Transaksi dengan Qty = 0 dikeluarkan dari dashboard. '
        'Qty kosong tidak otomatis dianggap Cancel.'
    )

    st.write('Preview Raw Data:')

    st.dataframe(
        raw_original.head(10),
        use_container_width=True
    )


# ==========================================================
# 11. DATA PREPARATION
# ==========================================================

base = raw.dropna(
    subset=[DATE_COL]
).copy()

base['Bulan'] = (
    base[DATE_COL]
    .dt.to_period('M')
    .astype(str)
)

base['Quarter_Num'] = base[DATE_COL].dt.quarter

for col in [
    CHANNEL_COL,
    CUSTOMER_COL,
    TYPE_COL
]:

    base[col] = (
        base[col]
        .fillna('Unknown')
        .astype(str)
    )

if TIPE_CUSTOMER_COL in base.columns:

    base[TIPE_CUSTOMER_COL] = (
        base[TIPE_CUSTOMER_COL]
        .fillna('Unknown')
        .astype(str)
    )


if base.empty:

    st.warning(
        'Tidak ada data valid setelah proses cleaning.'
    )

    st.stop()


# ==========================================================
# 12. DASHBOARD FILTERS
# ==========================================================

st.sidebar.header('Dashboard Filters')

channel = st.sidebar.selectbox(
    'Channel',
    ['All Channel'] +
    sorted(base[CHANNEL_COL].unique().tolist())
)

trx_type = st.sidebar.selectbox(
    'Sales/Retur',
    ['Nett Sales', 'Sales', 'Retur'],
    index=1
)

quarter = st.sidebar.selectbox(
    'Quarter',
    ['All Quarter', 'Q1', 'Q2', 'Q3', 'Q4']
)

tipe = st.sidebar.selectbox(
    'Nama Tipe',
    ['All Tipe'] +
    sorted(base[TYPE_COL].unique().tolist())
)


# ==========================================================
# 13. FILTER DATA
# ==========================================================

scope = base.copy()

if channel != 'All Channel':

    scope = scope[
        scope[CHANNEL_COL].eq(channel)
    ]

if quarter != 'All Quarter':

    scope = scope[
        scope['Quarter_Num'].eq(
            int(quarter[1])
        )
    ]

if tipe != 'All Tipe':

    scope = scope[
        scope[TYPE_COL].eq(tipe)
    ]


# Scope untuk NOO dan Loss Customer
d = scope.copy()

if trx_type in ['Sales', 'Retur']:

    d = d[
        d['Sales/Retur'].eq(trx_type)
    ]


# ==========================================================
# 14. DASHBOARD HEADER
# ==========================================================

st.subheader(
    f'{channel} | {trx_type} | {quarter} | {tipe}'
)

st.caption(
    f'Jumlah baris setelah filter: {len(d):,}'
)

if d.empty:

    st.warning(
        'Tidak ada data yang sesuai dengan filter.'
    )

    st.stop()


# ==========================================================
# 15. MONTHLY KPI
# ==========================================================

m = monthly_summary(d)

if m.empty:

    st.warning('Tidak ada data untuk perhitungan KPI.')
    st.stop()

latest = m.iloc[-1]

period = month_label(latest['Bulan'])


if trx_type == 'Sales':

    main_value = latest['Sales']
    main_label = 'Total Sales'

    mom = (
        m['Sales'].pct_change().iloc[-1] * 100
        if len(m) > 1 else np.nan
    )

    yoy = (
        m['Sales']
        .div(m['Sales'].shift(12).replace(0, np.nan))
        .sub(1).iloc[-1] * 100
        if len(m) > 12 else np.nan
    )


elif trx_type == 'Retur':

    main_value = latest['Retur']
    main_label = 'Total Retur'

    mom = (
        m['Retur'].pct_change().iloc[-1] * 100
        if len(m) > 1 else np.nan
    )

    yoy = (
        m['Retur']
        .div(m['Retur'].shift(12).replace(0, np.nan))
        .sub(1).iloc[-1] * 100
        if len(m) > 12 else np.nan
    )


else:

    main_value = latest['Net_Sales']
    main_label = 'Net Sales (Sales - Retur)'

    mom = latest['Sales_MoM']
    yoy = latest['Sales_YoY']


avg = (
    main_value / latest['Active_Outlet']
    if latest['Active_Outlet'] else np.nan
)


st.subheader(
    f'Key Performance Indicators ({period})'
)

k1, k2, k3 = st.columns(3)

k1.metric(
    main_label,
    fmt_rp(main_value),
    f'MoM {fmt_pct(mom)}'
)

k2.metric(
    'Active Outlet',
    f"{latest['Active_Outlet']:,.0f}"
)

k3.metric(
    'Average per Outlet',
    fmt_rp(avg),
    f'YoY {fmt_pct(yoy)}'
)


# ==========================================================
# 16. MONTHLY SALES TREND
# ==========================================================

if trx_type == 'Sales':

    ycol = 'Sales'
    title = 'Monthly Sales Trend'

elif trx_type == 'Retur':

    ycol = 'Retur'
    title = 'Monthly Retur Trend'

else:

    ycol = 'Net_Sales'
    title = 'Monthly Net Sales Trend'


fig = px.line(
    m,
    x='Bulan',
    y=ycol,
    markers=True,
    title=title
)

show_chart(fig)


# ==========================================================
# 17. ACTIVE OUTLET & AVERAGE SALES TREND
# ==========================================================

c1, c2 = st.columns(2)

with c1:

    show_chart(
        px.line(
            m,
            x='Bulan',
            y='Active_Outlet',
            markers=True,
            title='Active Outlet Trend'
        )
    )


with c2:

    show_chart(
        px.line(
            m,
            x='Bulan',
            y='Avg_Sales_Outlet',
            markers=True,
            title='Average Sales per Active Outlet'
        )
    )


# ==========================================================
# 18. CHANNEL DISTRIBUTION
# ==========================================================

latest_data = d[
    d['Bulan'].eq(latest['Bulan'])
].copy()

if trx_type == 'Sales':

    latest_data = latest_data[
        latest_data['Sales/Retur'].eq('Sales')
    ]

elif trx_type == 'Retur':

    latest_data = latest_data[
        latest_data['Sales/Retur'].eq('Retur')
    ]


channel_summary = (
    latest_data.groupby(CHANNEL_COL, as_index=False)[SALES_COL]
    .sum()
)

channel_summary['Display_Value'] = (
    channel_summary[SALES_COL].abs()
)

if channel_summary['Display_Value'].sum() > 0:

    show_chart(
        px.pie(
            channel_summary,
            names=CHANNEL_COL,
            values='Display_Value',
            hole=0.45,
            title=f'Distribution by Channel — {period}'
        )
    )

else:

    st.info(
        'Tidak ada nilai untuk distribusi Channel.'
    )


# ==========================================================
# 19. MONTHLY PERFORMANCE
# ==========================================================

st.subheader('Monthly Performance')

table = m[
    [
        'Bulan',
        'Sales',
        'Retur',
        'Net_Sales',
        'Sales_MoM',
        'Sales_YoY',
        'Active_Outlet',
        'Outlet_MoM',
        'Avg_Sales_Outlet'
    ]
].copy()


table['Bulan'] = table['Bulan'].map(month_label)

for col in [
    'Sales',
    'Retur',
    'Net_Sales',
    'Avg_Sales_Outlet'
]:

    table[col] = table[col].map(fmt_rp)


for col in [
    'Sales_MoM',
    'Sales_YoY',
    'Outlet_MoM'
]:

    table[col] = table[col].map(fmt_pct)


table['Active_Outlet'] = table[
    'Active_Outlet'
].map(lambda x: f'{x:,.0f}')


table = table.rename(
    columns={
        'Bulan': 'Month',
        'Net_Sales': 'Net Sales',
        'Sales_MoM': 'Sales MoM',
        'Sales_YoY': 'Sales YoY',
        'Active_Outlet': 'Active Outlet',
        'Outlet_MoM': 'Outlet MoM',
        'Avg_Sales_Outlet': 'Avg Sales / Outlet'
    }
)


st.dataframe(
    table,
    use_container_width=True,
    hide_index=True
)


# ==========================================================
# 20. TOP 10 ANALYSIS
# ==========================================================

st.subheader('Top 10 Analysis')

type_col = (
    TIPE_CUSTOMER_COL
    if TIPE_CUSTOMER_COL in d.columns
    else TYPE_COL
)

c1, c2 = st.columns(2)


with c1:

    top_type = (
        d.groupby(type_col, as_index=False)[SALES_COL]
        .sum()
        .nlargest(10, SALES_COL)
    )

    show_chart(
        px.bar(
            top_type.sort_values(SALES_COL),
            x=SALES_COL,
            y=type_col,
            orientation='h',
            title=f'Top 10 Tipe Customer ({trx_type})'
        )
    )


with c2:

    top_customer = (
        d.groupby(CUSTOMER_COL, as_index=False)[SALES_COL]
        .sum()
        .nlargest(10, SALES_COL)
    )

    show_chart(
        px.bar(
            top_customer.sort_values(SALES_COL),
            x=SALES_COL,
            y=CUSTOMER_COL,
            orientation='h',
            title=f'Top 10 Customer ({trx_type})'
        )
    )


# ==========================================================
# 21. NEW OPEN OUTLET (NOO)
# ==========================================================

st.subheader(f'New Open Outlet (NOO) ({period})')

st.caption(
    'NOO adalah Kode Customer yang pertama kali '
    'memiliki transaksi Sales pada bulan terbaru '
    'dalam filter yang dipilih.'
)

noo = new_open_outlets(scope)

if not noo.empty:

    st.metric(
        'Total NOO',
        f'{len(noo):,}'
    )

    st.dataframe(
        noo,
        use_container_width=True,
        hide_index=True
    )

else:

    if 'Kode Customer' not in scope.columns:

        st.warning(
            "Kolom 'Kode Customer' tidak ditemukan. "
            "Tambahkan kolom tersebut pada file raw Excel "
            "untuk menghitung NOO."
        )

    else:

        st.info(
            'Tidak ada NOO pada bulan terakhir '
            'berdasarkan filter yang dipilih.'
        )


# ==========================================================
# 22. LOSS CUSTOMER REPORT
# ==========================================================

st.subheader('Loss Customer Report')

st.caption(
    'Customer yang melakukan transaksi Sales pada 2025 '
    'tetapi tidak melakukan transaksi Sales sama sekali '
    'selama 2026.'
)

loss = loss_customers(scope)

if not loss.empty:

    st.metric(
        'Total Loss Customer',
        f'{len(loss):,}'
    )

    st.dataframe(
        loss,
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        'Tidak ada Loss Customer terdeteksi.'
    )


# ==========================================================
# 23. FOOTER
# ==========================================================

st.divider()

st.caption(
    'Data dashboard telah melalui proses cleaning. '
    'Transaksi dengan Qty = 0 (Cancel) tidak digunakan '
    'dalam seluruh perhitungan.'
)
