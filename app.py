import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
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
BRANCH_COL = 'Branch'
CODE_CUSTOMER_COL = 'Kode Customer'

LINK = 'https://docs.google.com/spreadsheets/d/1_B08zOyIueu1daLN11ihiguHrblVXAOgwZw5ILF-spU/edit?usp=sharing'

MONTH_NAMES = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
]

QUARTER_MONTHS = {
    1: [1, 2, 3],
    2: [4, 5, 6],
    3: [7, 8, 9],
    4: [10, 11, 12]
}


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


def month_range_label(data, month_col='Bulan'):
    if data.empty or month_col not in data.columns:
        return 'Tidak ada data'

    months = data[month_col].dropna().astype(str)

    if months.empty:
        return 'Tidak ada data'

    first_month = months.min()
    last_month = months.max()

    if first_month == last_month:
        return month_label(first_month)

    return (
        f'{month_label(first_month)} – '
        f'{month_label(last_month)}'
    )


def show_chart(fig):
    st.plotly_chart(
        fig,
        use_container_width=True
    )


def pct_change(current, previous):
    if pd.isna(previous) or previous == 0:
        return np.nan

    return ((current / previous) - 1) * 100


def get_selected_months(quarter):
    if quarter == 'All Quarter':
        return list(range(1, 13))

    quarter_num = int(quarter[1])
    return QUARTER_MONTHS[quarter_num]


def get_quarter_label(quarter_num):
    return {
        1: 'Jan-Mar',
        2: 'Apr-Jun',
        3: 'Jul-Sep',
        4: 'Oct-Dec'
    }[quarter_num]


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
    )

    # Lengkapi bulan kalender agar MoM dan YoY tepat
    first_month = pd.Period(d['Bulan'].min(), freq='M')
    last_month = pd.Period(d['Bulan'].max(), freq='M')

    calendar = pd.period_range(
        start=first_month,
        end=last_month,
        freq='M'
    ).astype(str)

    m = (
        m.set_index('Bulan')
        .reindex(calendar)
        .rename_axis('Bulan')
        .reset_index()
    )

    for col in ['Sales', 'Retur', 'Active_Outlet']:
        m[col] = m[col].fillna(0)

    m['Net_Sales'] = m['Sales'] - m['Retur']

    # Average per outlet untuk masing-masing jenis nilai
    m['Avg_Sales_Outlet'] = (
        m['Sales'] /
        m['Active_Outlet'].replace(0, np.nan)
    )

    m['Avg_Retur_Outlet'] = (
        m['Retur'] /
        m['Active_Outlet'].replace(0, np.nan)
    )

    m['Avg_Net_Sales_Outlet'] = (
        m['Net_Sales'] /
        m['Active_Outlet'].replace(0, np.nan)
    )

    # ------------------------------------------------------
    # MoM: bulan kalender sebelumnya
    # ------------------------------------------------------

    mom_columns = [
        ('Sales', 'Sales_MoM'),
        ('Retur', 'Retur_MoM'),
        ('Net_Sales', 'Net_Sales_MoM'),
        ('Active_Outlet', 'Outlet_MoM'),
        ('Avg_Sales_Outlet', 'Avg_MoM'),
        ('Avg_Retur_Outlet', 'Avg_Retur_MoM'),
        ('Avg_Net_Sales_Outlet', 'Avg_Net_MoM')
    ]

    for value_col, result_col in mom_columns:
        previous = m[value_col].shift(1).replace(0, np.nan)

        m[result_col] = (
            (m[value_col] / previous) - 1
        ) * 100

    # ------------------------------------------------------
    # YoY: bulan kalender yang sama tahun sebelumnya
    # ------------------------------------------------------

    month_lookup = m.set_index('Bulan')

    previous_year_months = (
        pd.PeriodIndex(m['Bulan'], freq='M') - 12
    ).astype(str)

    yoy_columns = [
        ('Sales', 'Sales_YoY'),
        ('Retur', 'Retur_YoY'),
        ('Net_Sales', 'Net_Sales_YoY'),
        ('Active_Outlet', 'Outlet_YoY'),
        ('Avg_Sales_Outlet', 'Avg_YoY'),
        ('Avg_Retur_Outlet', 'Avg_Retur_YoY'),
        ('Avg_Net_Sales_Outlet', 'Avg_Net_YoY')
    ]

    for value_col, result_col in yoy_columns:
        previous = (
            month_lookup[value_col]
            .reindex(previous_year_months)
            .to_numpy()
        )

        previous = (
            pd.Series(previous)
            .replace(0, np.nan)
            .to_numpy()
        )

        m[result_col] = (
            (m[value_col].to_numpy() / previous) - 1
        ) * 100

    return m


# ==========================================================
# 4. NEW OPEN OUTLET (NOO)
# ==========================================================

def new_open_outlets(data, target_month=None):
    code_col = CODE_CUSTOMER_COL

    if data.empty or code_col not in data.columns:
        return pd.DataFrame()

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

    sales = sales[
        sales[code_col].ne('')
    ]

    if sales.empty:
        return pd.DataFrame()

    sales['Bulan'] = (
        sales[DATE_COL]
        .dt.to_period('M')
        .astype(str)
    )

    if target_month is None:
        target_month = sales['Bulan'].max()

    # Transaksi pertama setiap customer dari seluruh histori
    first_transaction = (
        sales.groupby(code_col, as_index=False)
        .agg(
            First_Transaction=(DATE_COL, 'min')
        )
    )

    first_transaction['First_Period'] = (
        first_transaction['First_Transaction']
        .dt.to_period('M')
        .astype(str)
    )

    # NOO hanya jika transaksi pertamanya pada bulan target
    noo = first_transaction[
        first_transaction['First_Period'].eq(target_month)
    ].copy()

    if noo.empty:
        return pd.DataFrame()

    # Ambil nama customer dan total sales pada bulan NOO
    latest_sales = sales[
        sales['Bulan'].eq(target_month)
    ].copy()

    if CUSTOMER_COL in latest_sales.columns:
        customer_names = (
            latest_sales.groupby(code_col)[CUSTOMER_COL]
            .first()
        )

        noo['Nama Customer'] = (
            noo[code_col].map(customer_names)
        )

    sales_total = (
        latest_sales.groupby(code_col)[SALES_COL]
        .sum()
    )

    noo['Total Sales'] = (
        noo[code_col].map(sales_total)
    )

    noo['First_Transaction'] = (
        noo['First_Transaction'].dt.strftime('%d-%m-%Y')
    )

    noo = noo.rename(
        columns={
            code_col: 'Kode Customer',
            'First_Transaction': 'Tanggal Transaksi Pertama'
        }
    )

    columns = [
        'Kode Customer',
        'Nama Customer',
        'Tanggal Transaksi Pertama',
        'Total Sales'
    ]

    columns = [
        col for col in columns
        if col in noo.columns
    ]

    noo = noo[columns].copy()

    noo['Total Sales'] = noo['Total Sales'].map(fmt_rp)

    return noo.sort_values(
        'Kode Customer'
    ).reset_index(drop=True)


# ==========================================================
# 5. LOSS CUSTOMER
# Tahun terbaru dibanding seluruh tahun sebelumnya
# ==========================================================

def loss_customers(data):
    if data.empty:
        return pd.DataFrame(), None, []

    sales = data[
        data['Sales/Retur'].eq('Sales')
    ].copy()

    if sales.empty:
        return pd.DataFrame(), None, []

    key_col = (
        CODE_CUSTOMER_COL
        if CODE_CUSTOMER_COL in sales.columns
        else CUSTOMER_COL
    )

    sales = sales.dropna(
        subset=[DATE_COL, key_col]
    ).copy()

    sales[key_col] = (
        sales[key_col]
        .astype(str)
        .str.strip()
    )

    sales = sales[
        sales[key_col].ne('')
    ]

    if sales.empty:
        return pd.DataFrame(), None, []

    # Tahun terakhir yang tersedia
    latest_year = int(
        sales[DATE_COL].dt.year.max()
    )

    # Semua transaksi sebelum tahun terakhir
    previous_data = sales[
        sales[DATE_COL].dt.year < latest_year
    ].copy()

    # Transaksi pada tahun terakhir
    latest_data = sales[
        sales[DATE_COL].dt.year == latest_year
    ].copy()

    previous_years = sorted(
        previous_data[DATE_COL].dt.year.unique().tolist()
    )

    previous_customers = set(
        previous_data[key_col].unique()
    )

    latest_customers = set(
        latest_data[key_col].unique()
    )

    # Loss = pernah transaksi sebelumnya,
    # tetapi tidak transaksi pada tahun terakhir
    lost_customers = (
        previous_customers - latest_customers
    )

    if not lost_customers:
        return pd.DataFrame(), latest_year, previous_years

    lost_data = previous_data[
        previous_data[key_col].isin(lost_customers)
    ].copy()

    if key_col == CODE_CUSTOMER_COL:
        result = (
            lost_data.groupby(key_col, as_index=False)
            .agg(
                **{
                    'Nama Customer': (CUSTOMER_COL, 'first'),
                    'Last Transaction': (DATE_COL, 'max'),
                    'Total Sales Previous Years': (SALES_COL, 'sum')
                }
            )
        )

        result = result.rename(
            columns={key_col: 'Kode Customer'}
        )

    else:
        result = (
            lost_data.groupby(key_col, as_index=False)
            .agg(
                **{
                    'Last Transaction': (DATE_COL, 'max'),
                    'Total Sales Previous Years': (SALES_COL, 'sum')
                }
            )
            .rename(
                columns={key_col: 'Nama Customer'}
            )
        )

    result['Last Transaction'] = (
        result['Last Transaction'].dt.strftime('%d-%m-%Y')
    )

    result['Total Sales Previous Years'] = (
        result['Total Sales Previous Years'].map(fmt_rp)
    )

    result = result.sort_values(
        'Last Transaction',
        ascending=False
    ).reset_index(drop=True)

    return result, latest_year, previous_years


# ==========================================================
# 6. SIDEBAR - DATA INPUT
# ==========================================================

with st.sidebar:

    logo_path = Path(__file__).parent / 'logo.webp'

    if logo_path.exists():
        st.image(
            str(logo_path),
            width=100
        )

    st.header('Data Input')

    uploaded = st.file_uploader(
        'Upload Raw Data Excel',
        type=['xlsx', 'xls']
    )

    use_mapping = st.checkbox(
        'Principal & Customer Inactive Out',
        value=True
    )

    st.markdown(
        f'🔗 [List Principal & Customer Out]({LINK})'
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

raw_original = raw.copy()

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

total_raw = len(raw)

total_cancel = int(
    raw['Transaksi'].eq('Cancel').sum()
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

    c1, c2, c3, c4 = st.columns(4)

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
        'Data tanpa Mapping',
        f'{len(filtered_raw):,}'
    )

    st.caption(
        'Transaksi cancel dikeluarkan dari dashboard.'
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

if BRANCH_COL in base.columns:
    base[BRANCH_COL] = (
        base[BRANCH_COL]
        .fillna('Unknown')
        .astype(str)
    )

if CODE_CUSTOMER_COL in base.columns:
    base[CODE_CUSTOMER_COL] = (
        base[CODE_CUSTOMER_COL]
        .astype('string')
        .str.strip()
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

if BRANCH_COL in base.columns:

    branch = st.sidebar.selectbox(
        'Branch',
        ['All Branch'] +
        sorted(base[BRANCH_COL].unique().tolist())
    )

else:
    branch = 'All Branch'

    st.sidebar.warning(
        "Kolom 'Branch' tidak ditemukan."
    )


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

# Filter utama, termasuk quarter
scope = base.copy()

if branch != 'All Branch' and BRANCH_COL in scope.columns:
    scope = scope[
        scope[BRANCH_COL].eq(branch)
    ]

if channel != 'All Channel':
    scope = scope[
        scope[CHANNEL_COL].eq(channel)
    ]

if quarter != 'All Quarter':
    scope = scope[
        scope['Quarter_Num'].eq(int(quarter[1]))
    ]

if tipe != 'All Tipe':
    scope = scope[
        scope[TYPE_COL].eq(tipe)
    ]


# Scope KPI dan grafik
d = scope.copy()

if trx_type in ['Sales', 'Retur']:
    d = d[
        d['Sales/Retur'].eq(trx_type)
    ]


# Scope pembanding:
# Mengikuti Branch, Channel, Nama Tipe,
# tetapi tidak dibatasi Quarter.
kpi_scope = base.copy()

if branch != 'All Branch' and BRANCH_COL in kpi_scope.columns:
    kpi_scope = kpi_scope[
        kpi_scope[BRANCH_COL].eq(branch)
    ]

if channel != 'All Channel':
    kpi_scope = kpi_scope[
        kpi_scope[CHANNEL_COL].eq(channel)
    ]

if tipe != 'All Tipe':
    kpi_scope = kpi_scope[
        kpi_scope[TYPE_COL].eq(tipe)
    ]

kpi_d = kpi_scope.copy()

if trx_type in ['Sales', 'Retur']:
    kpi_d = kpi_d[
        kpi_d['Sales/Retur'].eq(trx_type)
    ]


# ==========================================================
# 14. DASHBOARD HEADER
# ==========================================================

st.subheader(
    f'{branch} | {channel} | {trx_type} | {quarter} | {tipe}'
)

st.caption(
    f'Jumlah baris setelah filter: {len(d):,}'
)

all_dates = base[DATE_COL].dropna()

if not all_dates.empty:
    st.caption(
        'Periode seluruh data: '
        f'{all_dates.min():%d-%b-%Y} sampai '
        f'{all_dates.max():%d-%b-%Y}'
    )


if d.empty:
    st.warning(
        'Tidak ada data yang sesuai dengan filter.'
    )
    st.stop()





# ==========================================================
# 15. MONTHLY KPI
# KPI mengikuti pilihan Sales/Retur/Nett Sales
# Tampilan: Total | Active Outlet | Average per Outlet
# ==========================================================

m = monthly_summary(d)

if m.empty:
    st.warning('Tidak ada data untuk perhitungan KPI.')
    st.stop()

target_month = d['Bulan'].max()

# Tentukan kolom KPI berdasarkan pilihan transaksi
if trx_type == 'Sales':
    value_col = 'Sales'
    mom_col = 'Sales_MoM'
    yoy_col = 'Sales_YoY'
    kpi_label = 'Total Sales'

elif trx_type == 'Retur':
    value_col = 'Retur'
    mom_col = 'Retur_MoM'
    yoy_col = 'Retur_YoY'
    kpi_label = 'Total Retur'

else:
    value_col = 'Net_Sales'
    mom_col = 'Net_Sales_MoM'
    yoy_col = 'Net_Sales_YoY'
    kpi_label = 'Net Sales'


# Data KPI mengikuti jenis transaksi yang dipilih
kpi_transaction_data = kpi_scope.copy()

if trx_type in ['Sales', 'Retur']:
    kpi_transaction_data = kpi_transaction_data[
        kpi_transaction_data['Sales/Retur'].eq(trx_type)
    ]


# ----------------------------------------------------------
# QUARTER KPI
# ----------------------------------------------------------

if quarter != 'All Quarter':

    quarter_num = int(quarter[1])

    quarter_dates = scope.loc[
        scope['Quarter_Num'].eq(quarter_num), DATE_COL
    ].dropna()

    if quarter_dates.empty:
        st.warning('Tidak ada data untuk quarter yang dipilih.')
        st.stop()

    kpi_year = int(quarter_dates.dt.year.max())

    kpi_period_data = kpi_transaction_data[
        (kpi_transaction_data[DATE_COL].dt.year.eq(kpi_year)) &
        (kpi_transaction_data['Quarter_Num'].eq(quarter_num))
    ].copy()

    quarter_start_month = (quarter_num - 1) * 3 + 1

    period = (
        f'{MONTH_NAMES[quarter_start_month - 1]}-'
        f'{MONTH_NAMES[quarter_start_month + 1]} {kpi_year}'
    )

    # Total berdasarkan pilihan Sales/Retur/Net Sales
    if trx_type == 'Nett Sales':
        sales_total = kpi_period_data.loc[
            kpi_period_data['Sales/Retur'].eq('Sales'),
            SALES_COL
        ].sum()

        retur_total = kpi_period_data.loc[
            kpi_period_data['Sales/Retur'].eq('Retur'),
            SALES_COL
        ].sum()

        total_value = sales_total - retur_total

    else:
        total_value = kpi_period_data[SALES_COL].sum()

    # Active Outlet selama quarter
    active_outlet = int(
        kpi_period_data[CUSTOMER_COL].nunique()
    )

    avg = (
        total_value / active_outlet
        if active_outlet > 0 else np.nan
    )

    # YoY: quarter yang sama tahun sebelumnya
    previous_year_data = kpi_transaction_data[
        (kpi_transaction_data[DATE_COL].dt.year.eq(kpi_year - 1)) &
        (kpi_transaction_data['Quarter_Num'].eq(quarter_num))
    ]

    if trx_type == 'Nett Sales':
        previous_year_sales = previous_year_data.loc[
            previous_year_data['Sales/Retur'].eq('Sales'),
            SALES_COL
        ].sum()

        previous_year_retur = previous_year_data.loc[
            previous_year_data['Sales/Retur'].eq('Retur'),
            SALES_COL
        ].sum()

        previous_year_value = (
            previous_year_sales - previous_year_retur
        )
    else:
        previous_year_value = previous_year_data[SALES_COL].sum()

    yoy = pct_change(total_value, previous_year_value)

    # QoQ: quarter sebelumnya
    previous_quarter = 4 if quarter_num == 1 else quarter_num - 1
    previous_quarter_year = (
        kpi_year - 1 if quarter_num == 1 else kpi_year
    )

    previous_quarter_data = kpi_transaction_data[
        (kpi_transaction_data[DATE_COL].dt.year.eq(previous_quarter_year)) &
        (kpi_transaction_data['Quarter_Num'].eq(previous_quarter))
    ]

    if trx_type == 'Nett Sales':
        previous_sales = previous_quarter_data.loc[
            previous_quarter_data['Sales/Retur'].eq('Sales'),
            SALES_COL
        ].sum()

        previous_retur = previous_quarter_data.loc[
            previous_quarter_data['Sales/Retur'].eq('Retur'),
            SALES_COL
        ].sum()

        previous_quarter_value = previous_sales - previous_retur
    else:
        previous_quarter_value = previous_quarter_data[SALES_COL].sum()

    mom = pct_change(total_value, previous_quarter_value)
    growth_label = 'QoQ'


# ----------------------------------------------------------
# MONTHLY KPI
# ----------------------------------------------------------

else:

    kpi_m = monthly_summary(kpi_d)

    if kpi_m.empty or target_month not in kpi_m['Bulan'].values:
        st.warning('Data KPI tidak tersedia untuk periode filter ini.')
        st.stop()

    latest = (
        kpi_m[kpi_m['Bulan'].eq(target_month)]
        .iloc[0]
    )

    period = month_label(target_month)

    total_value = latest[value_col]
    mom = latest[mom_col]
    yoy = latest[yoy_col]

    active_outlet = int(latest['Active_Outlet'])
    avg = (
        total_value / active_outlet
        if active_outlet > 0 else np.nan
    )

    growth_label = 'MoM'


# ----------------------------------------------------------
# KPI DISPLAY
# ----------------------------------------------------------

st.subheader(
    f'Key Performance Indicators ({period})'
)

k1, k2, k3 = st.columns([1, 1, 1])

with k1:
    st.metric(
        label=kpi_label,
        value=fmt_rp(total_value),
        delta=(
            f'{growth_label} {fmt_pct(mom)}'
            if pd.notna(mom) else None
        ),
        delta_color='normal'
    )

with k2:
    st.metric(
        label='Active Outlet',
        value=f'{active_outlet:,}',
        delta=None
    )

with k3:
    st.metric(
        label='Average per Outlet',
        value=fmt_rp(avg),
        delta=(
            f'YoY {fmt_pct(yoy)}'
            if pd.notna(yoy) else None
        ),
        delta_color='normal'
    )



# ==========================================================
# 16. MONTHLY SALES TREND
# DYNAMIC ALL YEARS
# ==========================================================

if trx_type == 'Sales':
    ycol = 'Sales'
    chart_title = 'Monthly Sales Trend'

elif trx_type == 'Retur':
    ycol = 'Retur'
    chart_title = 'Monthly Retur Trend'

else:
    ycol = 'Net_Sales'
    chart_title = 'Monthly Net Sales Trend'


selected_months = get_selected_months(quarter)

selected_month_names = [
    MONTH_NAMES[i - 1] for i in selected_months
]

trend_data = m.copy()

trend_data['_Date'] = pd.to_datetime(
    trend_data['Bulan'].astype(str) + '-01',
    errors='coerce'
)

trend_data['Year'] = trend_data['_Date'].dt.year
trend_data['Month_Num'] = trend_data['_Date'].dt.month

trend_data = trend_data[
    trend_data['Month_Num'].isin(selected_months)
].copy()

available_years = sorted(
    trend_data['Year'].dropna().unique().tolist()
)

trend_pivot = trend_data.pivot_table(
    index='Month_Num',
    columns='Year',
    values=ycol,
    aggfunc='sum'
).reindex(selected_months)

fig = go.Figure()

for year in available_years:
    fig.add_trace(
        go.Scatter(
            x=selected_month_names,
            y=(
                trend_pivot[year].tolist()
                if year in trend_pivot.columns
                else [None] * len(selected_months)
            ),
            name=str(int(year)),
            mode='lines+markers',
            connectgaps=False
        )
    )

fig.update_layout(
    title=(
        f'{chart_title} '
        f'({month_range_label(m)})'
    ),
    xaxis_title='Month',
    yaxis_title=ycol.replace('_', ' '),
    hovermode='x unified',
    legend=dict(
        orientation='h',
        yanchor='bottom',
        y=1.02,
        xanchor='right',
        x=1
    )
)

show_chart(fig)


# ==========================================================
# 17. ACTIVE OUTLET & AVERAGE SALES TREND
# DYNAMIC ALL YEARS
# ==========================================================

c1, c2 = st.columns(2)


# ----------------------------------------------------------
# ACTIVE OUTLET COMPARISON
# ----------------------------------------------------------

with c1:

    active_data = m.copy()

    active_data['_Date'] = pd.to_datetime(
        active_data['Bulan'] + '-01',
        errors='coerce'
    )

    active_data['Year'] = active_data['_Date'].dt.year
    active_data['Month_Num'] = active_data['_Date'].dt.month

    active_data = active_data[
        active_data['Month_Num'].isin(selected_months)
    ].copy()

    active_years = sorted(
        active_data['Year'].dropna().unique().tolist()
    )

    active_pivot = active_data.pivot_table(
        index='Month_Num',
        columns='Year',
        values='Active_Outlet',
        aggfunc='first'
    ).reindex(selected_months)

    fig_active = go.Figure()

    for year in active_years:
        fig_active.add_trace(
            go.Scatter(
                x=selected_month_names,
                y=(
                    active_pivot[year].tolist()
                    if year in active_pivot.columns
                    else [None] * len(selected_months)
                ),
                name=str(int(year)),
                mode='lines+markers',
                connectgaps=False
            )
        )

    fig_active.update_layout(
        title=(
            'Active Outlet Comparison '
            f'({month_range_label(active_data)})'
        ),
        xaxis_title='Month',
        yaxis_title='Active Outlet',
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )

    show_chart(fig_active)


# ----------------------------------------------------------
# AVERAGE SALES PER OUTLET
# ----------------------------------------------------------

with c2:

    avg_chart_data = m.copy()

    avg_chart_data['_Date'] = pd.to_datetime(
        avg_chart_data['Bulan'] + '-01',
        errors='coerce'
    )

    avg_chart_data['Year'] = avg_chart_data['_Date'].dt.year
    avg_chart_data['Month_Num'] = avg_chart_data['_Date'].dt.month

    avg_chart_data = avg_chart_data[
        avg_chart_data['Month_Num'].isin(selected_months)
    ].copy()

    avg_years = sorted(
        avg_chart_data['Year'].dropna().unique().tolist()
    )

    avg_pivot = avg_chart_data.pivot_table(
        index='Month_Num',
        columns='Year',
        values='Avg_Sales_Outlet',
        aggfunc='first'
    ).reindex(selected_months)

    fig_avg = go.Figure()

    for year in avg_years:
        fig_avg.add_trace(
            go.Scatter(
                x=selected_month_names,
                y=(
                    avg_pivot[year].tolist()
                    if year in avg_pivot.columns
                    else [None] * len(selected_months)
                ),
                name=str(int(year)),
                mode='lines+markers',
                connectgaps=False
            )
        )

    fig_avg.update_layout(
        title=(
            'Average Sales per Active Outlet '
            f'({month_range_label(m)})'
        ),
        xaxis_title='Month',
        yaxis_title='Average Sales per Active Outlet',
        hovermode='x unified',
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='right',
            x=1
        )
    )

    show_chart(fig_avg)


# ==========================================================
# 18. DISTRIBUTION ANALYSIS
# ==========================================================

st.subheader(
    f'Distribution Analysis ({month_range_label(m)})'
)

distribution_data = d.copy()

if trx_type == 'Sales':

    distribution_data = distribution_data[
        distribution_data['Sales/Retur'].eq('Sales')
    ]

    channel_summary = (
        distribution_data
        .groupby(CHANNEL_COL, as_index=False)[SALES_COL]
        .sum()
    )

    channel_summary['Display_Value'] = (
        channel_summary[SALES_COL].abs()
    )

elif trx_type == 'Retur':

    distribution_data = distribution_data[
        distribution_data['Sales/Retur'].eq('Retur')
    ]

    channel_summary = (
        distribution_data
        .groupby(CHANNEL_COL, as_index=False)[SALES_COL]
        .sum()
    )

    channel_summary['Display_Value'] = (
        channel_summary[SALES_COL].abs()
    )

else:

    distribution_data['Sales_Value'] = np.where(
        distribution_data['Sales/Retur'].eq('Sales'),
        distribution_data[SALES_COL],
        0
    )

    distribution_data['Retur_Value'] = np.where(
        distribution_data['Sales/Retur'].eq('Retur'),
        distribution_data[SALES_COL],
        0
    )

    channel_summary = (
        distribution_data
        .groupby(CHANNEL_COL, as_index=False)
        .agg(
            Sales=('Sales_Value', 'sum'),
            Retur=('Retur_Value', 'sum')
        )
    )

    channel_summary['Net Sales'] = (
        channel_summary['Sales'] -
        channel_summary['Retur']
    )

    channel_summary['Display_Value'] = (
        channel_summary['Net Sales'].abs()
    )


if (
    not channel_summary.empty and
    channel_summary['Display_Value'].sum() > 0
):

    fig_distribution = px.pie(
        channel_summary,
        names=CHANNEL_COL,
        values='Display_Value',
        hole=0.45
    )

    show_chart(fig_distribution)

else:
    st.info(
        'Tidak ada nilai untuk distribusi Channel.'
    )



# ==========================================================
# 19. MONTHLY PERFORMANCE
# Dynamic berdasarkan Quarter dan seluruh tahun
# ==========================================================

st.subheader(
    f'Monthly Performance ({month_range_label(m)})'
)

# Filter bulan berdasarkan quarter yang dipilih.
# selected_months sudah tersedia dari Section 16.
table_data = m.copy()

table_data['_Month_Num'] = (
    pd.PeriodIndex(table_data['Bulan'], freq='M').month
)

table_data = table_data[
    table_data['_Month_Num'].isin(selected_months)
].copy()

table = table_data[
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
# Berdasarkan bulan terakhir yang tersedia
# ==========================================================

top10_data = d[
    d['Bulan'].eq(target_month)
].copy()

top10_period = month_label(target_month)

st.subheader(
    f'Top 10 Analysis ({top10_period})'
)

type_col = (
    TIPE_CUSTOMER_COL
    if TIPE_CUSTOMER_COL in top10_data.columns
    else TYPE_COL
)

c1, c2 = st.columns(2)

with c1:

    top_type = (
        top10_data.groupby(type_col, as_index=False)[SALES_COL]
        .sum()
        .nlargest(10, SALES_COL)
    )

    show_chart(
        px.bar(
            top_type.sort_values(SALES_COL),
            x=SALES_COL,
            y=type_col,
            orientation='h',
            title=(
                f'Top 10 Tipe Customer '
                f'({trx_type}) — {top10_period}'
            )
        )
    )

with c2:

    top_customer = (
        top10_data.groupby(CUSTOMER_COL, as_index=False)[SALES_COL]
        .sum()
        .nlargest(10, SALES_COL)
    )

    show_chart(
        px.bar(
            top_customer.sort_values(SALES_COL),
            x=SALES_COL,
            y=CUSTOMER_COL,
            orientation='h',
            title=(
                f'Top 10 Customer '
                f'({trx_type}) — {top10_period}'
            )
        )
    )


# ==========================================================
# 21. NEW OPEN OUTLET (NOO)
# Menggunakan seluruh histori transaksi
# ==========================================================

noo_sales_scope = kpi_scope[
    kpi_scope['Sales/Retur'].eq('Sales')
].copy()

if quarter != 'All Quarter':
    # Target bulan tetap mengikuti quarter terpilih
    selected_noo_sales = scope[
        scope['Sales/Retur'].eq('Sales')
    ].copy()
else:
    selected_noo_sales = noo_sales_scope.copy()

if not selected_noo_sales.empty:

    noo_target_month = selected_noo_sales['Bulan'].max()
    noo_period = month_label(noo_target_month)

    st.subheader(
        f'New Open Outlet (NOO) ({noo_period})'
    )

    # Gunakan kpi_scope sebagai histori lengkap,
    # bukan scope yang sudah dibatasi quarter.
    noo = new_open_outlets(
        noo_sales_scope,
        target_month=noo_target_month
    )

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
        st.info(
            'Tidak ada NOO pada bulan tersebut. '
            'Customer yang sudah pernah bertransaksi '
            'tidak dihitung sebagai NOO.'
        )

else:

    st.subheader('New Open Outlet (NOO)')

    if CODE_CUSTOMER_COL not in kpi_scope.columns:
        st.warning(
            "Kolom 'Kode Customer' tidak ditemukan. "
            "Tambahkan kolom tersebut pada file raw Excel "
            "untuk menghitung NOO."
        )
    else:
        st.info(
            'Tidak ada transaksi Sales pada periode terpilih.'
        )


# ==========================================================
# 22. LOSS CUSTOMER REPORT
# Tahun terbaru dibanding seluruh tahun sebelumnya
# ==========================================================

loss_quarter_label = (
    'All Quarter'
    if quarter == 'All Quarter'
    else quarter
)

loss, loss_latest_year, loss_previous_years = (
    loss_customers(scope)
)

if loss_latest_year is not None:

    if loss_previous_years:
        previous_year_label = ', '.join(
            str(year) for year in loss_previous_years
        )
    else:
        previous_year_label = 'Belum ada tahun sebelumnya'

    st.subheader(
        f'Loss Customer Report '
        f'({loss_latest_year} vs tahun sebelumnya)'
    )

    st.caption(
        f'Customer yang pernah melakukan transaksi Sales '
        f'pada tahun {loss_latest_year}, tetapi tidak '
        f'melakukan transaksi Sales pada tahun sebelumnya.'
    )

    st.caption(
        f'Perbandingan periode: {loss_quarter_label}'
    )

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
            f'Tidak ada Loss Customer terdeteksi pada '
            f'tahun {loss_latest_year}.'
        )

else:

    st.subheader('Loss Customer Report')

    st.info(
        'Tidak ada data Sales untuk menghitung Loss Customer.'
    )


# ==========================================================
# 23. FOOTER
# ==========================================================

st.divider()

st.caption(
    'Sales Dashboard'
)

