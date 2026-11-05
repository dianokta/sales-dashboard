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
