"""
dashboard.py — SIPSAA Dashboard
================================
Ejecutar con .venv activado:
    cd L:\DATA\SIPSAA
    streamlit run CSV/dashboard.py
"""

import os
import duckdb
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import pydeck as pdk

# ── Rutas ─────────────────────────────────────────────────────────────────────
DIR         = os.path.dirname(os.path.abspath(__file__))
PARQUET     = os.path.join(DIR, "SIPSAA_TOTAL_V9.parquet")
TERRITORIOS       = os.path.join(DIR, "tmaestra_territorios.csv")
PRODUCTOS         = os.path.join(DIR, "tmaestra_productos.csv")
CENTRALES         = os.path.join(DIR, "tabla_centrales.csv")
COORD_MUNI        = os.path.join(DIR, "tmaestra_coordenadas_muni.csv")
COORD_CENTRALES   = os.path.join(DIR, "tmaestra_coord_centrales.csv")

# ── Configuración de la página ────────────────────────────────────────────────
st.set_page_config(
    page_title="SIPSAA — Abastecimiento de Alimentos",
    page_icon="🌽",
    layout="wide",
)

st.title("🌽 SIPSAA — Sistema de Abastecimiento de Alimentos")
st.caption("Fuente: DANE Colombia · Período 2018–2026 · Centrales mayoristas")

st.divider()

# ── Cargar tablas maestras (una sola vez) ─────────────────────────────────────
@st.cache_data
def cargar_territorios():
    return pd.read_csv(TERRITORIOS, sep=";", encoding="utf-8-sig", dtype=str)

@st.cache_data
def cargar_productos():
    return pd.read_csv(PRODUCTOS, sep=";", encoding="utf-8-sig", dtype=str)

@st.cache_data
def cargar_centrales():
    return pd.read_csv(CENTRALES, sep=";", encoding="utf-8-sig", dtype=str)

geo      = cargar_territorios()
prod     = cargar_productos()
centrales = cargar_centrales()

TERRITORIOS_FUNCIONALES = sorted(
    geo.loc[geo["terri_funcional"] != "Ninguno", "terri_funcional"].unique()
)

# ── Barra lateral ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 Filtros")

    # ── DESTINO ───────────────────────────────────────────────────────────────
    st.subheader("🏪 Destino")

    ciudades_disp = sorted(centrales["ciudad_destino"].unique())
    ciudad_sel = st.multiselect(
        "Ciudad destino",
        options=ciudades_disp,
        placeholder="Todas las ciudades",
    )

    if ciudad_sel:
        centrales_disp = sorted(
            centrales.loc[centrales["ciudad_destino"].isin(ciudad_sel), "central_may"].unique()
        )
    else:
        centrales_disp = sorted(centrales["central_may"].unique())

    central_sel = st.multiselect(
        "Central mayorista",
        options=centrales_disp,
        placeholder="Todas las centrales",
    )

    st.divider()

    # ── ORIGEN ────────────────────────────────────────────────────────────────
    st.subheader("📍 Origen")

    escala = st.selectbox(
        "Escala geográfica",
        options=[
            "SIPSAA Total",
            "Región Central total",
            "RC externa",
            "RMBC",
            "Territorio funcional",
            "Municipios Conmutados",
            "Solo internacionales (sin Colombia)",
        ],
    )

    territorio_sel = None
    if escala == "Territorio funcional":
        territorio_sel = st.selectbox(
            "Selecciona el territorio",
            options=["Todos"] + TERRITORIOS_FUNCIONALES,
        )

    # Municipios válidos para la escala
    if escala == "SIPSAA Total":
        munis_escala = set(geo["cod_muni"].tolist())
    elif escala == "Región Central total":
        munis_escala = set(geo.loc[geo["rc_total"] == "1", "cod_muni"].tolist())
    elif escala == "RC externa":
        munis_escala = set(geo.loc[geo["rc_externa"] == "1", "cod_muni"].tolist())
    elif escala == "RMBC":
        munis_escala = set(geo.loc[geo["rmbc"] == "1", "cod_muni"].tolist())
    elif escala == "Territorio funcional":
        if territorio_sel == "Todos":
            munis_escala = set(geo.loc[geo["terri_funcional"] != "Ninguno", "cod_muni"].tolist())
        else:
            munis_escala = set(geo.loc[geo["terri_funcional"] == territorio_sel, "cod_muni"].tolist())
    elif escala == "Municipios Conmutados":
        munis_escala = set(geo.loc[geo["muni_conmutados"] == "1", "cod_muni"].tolist())
    elif escala == "Solo internacionales (sin Colombia)":
        munis_escala = set()  # no aplica selector de depto/muni
    else:
        munis_escala = set(geo["cod_muni"].tolist())

    # Departamento (anidado en escala)
    deps_disponibles = sorted(
        geo.loc[geo["cod_muni"].isin(munis_escala), "departamento"].unique()
    )
    dep_sel = st.multiselect(
        "Departamento",
        options=deps_disponibles,
        placeholder="Todos los departamentos",
    )

    # Municipio (anidado en departamento)
    if dep_sel:
        munis_en_dep = geo.loc[
            geo["cod_muni"].isin(munis_escala) & geo["departamento"].isin(dep_sel),
            "cod_muni"
        ].tolist()
    else:
        munis_en_dep = list(munis_escala)

    munis_disponibles = sorted(
        geo.loc[geo["cod_muni"].isin(munis_en_dep), "municipio"].unique()
    )
    muni_sel = st.multiselect(
        "Municipio",
        options=munis_disponibles,
        placeholder="Todos los municipios",
    )

    st.divider()

    # ── FECHAS ────────────────────────────────────────────────────────────────
    st.subheader("📆 Período")

    import datetime
    fecha_min = datetime.date(2018, 1, 2)
    fecha_max = datetime.date(2026, 5, 31)

    anios_sel = st.multiselect(
        "Año(s)",
        options=list(range(2018, 2027)),
        placeholder="Todos los años (o elige uno/varios)",
    )

    fecha_ini = st.date_input(
        "Fecha inicio",
        value=fecha_min,
        min_value=fecha_min,
        max_value=fecha_max,
        format="YYYY-MM-DD",
    )
    fecha_fin = st.date_input(
        "Fecha fin",
        value=fecha_max,
        min_value=fecha_min,
        max_value=fecha_max,
        format="YYYY-MM-DD",
    )
    if fecha_ini > fecha_fin:
        st.error("La fecha inicio no puede ser mayor que la fecha fin.")

    st.divider()

    # ── PRODUCTOS ─────────────────────────────────────────────────────────────
    st.subheader("🥦 Productos")

    # Priorizado FAO 178
    priori_sel = st.radio(
        "Alimento priorizado FAO 178",
        options=["Todos", "Solo priorizados", "Solo no priorizados"],
        horizontal=True,
    )
    if priori_sel == "Solo priorizados":
        prod_filtrado = prod[prod["alim_priori178"] == "1"]
    elif priori_sel == "Solo no priorizados":
        prod_filtrado = prod[prod["alim_priori178"] == "0"]
    else:
        prod_filtrado = prod

    # Grupo
    grupos_disponibles = sorted(prod_filtrado["grupo_productos"].unique())
    grupo_sel = st.multiselect(
        "Grupo de productos",
        options=grupos_disponibles,
        placeholder="Todos los grupos",
    )

    # Subgrupo (anidado en grupo)
    if grupo_sel:
        subgrupos_disp = sorted(
            prod_filtrado.loc[prod_filtrado["grupo_productos"].isin(grupo_sel), "subgrupo_producto"].unique()
        )
    else:
        subgrupos_disp = sorted(prod_filtrado["subgrupo_producto"].unique())

    subgrupo_sel = st.multiselect(
        "Subgrupo",
        options=subgrupos_disp,
        placeholder="Todos los subgrupos",
    )

    # Producto (anidado en subgrupo)
    if subgrupo_sel:
        productos_disp = sorted(
            prod_filtrado.loc[prod_filtrado["subgrupo_producto"].isin(subgrupo_sel), "producto"].unique()
        )
    elif grupo_sel:
        productos_disp = sorted(
            prod_filtrado.loc[prod_filtrado["grupo_productos"].isin(grupo_sel), "producto"].unique()
        )
    else:
        productos_disp = sorted(prod_filtrado["producto"].unique())

    producto_sel = st.multiselect(
        "Producto",
        options=productos_disp,
        placeholder="Todos los productos",
    )

# ── Construir cláusulas WHERE ─────────────────────────────────────────────────

# -- Filtro geográfico --
munis_finales = set(munis_en_dep)
if muni_sel:
    munis_codigo = set(geo.loc[geo["municipio"].isin(muni_sel), "cod_muni"].tolist())
    munis_finales = munis_finales & munis_codigo

if escala == "Solo internacionales (sin Colombia)":
    filtro_geo = "p.cod_depto = 'Internacional' AND p.cod_muni != '170'"
elif escala == "SIPSAA Total" and not dep_sel and not muni_sel:
    filtro_geo = "1=1"
else:
    lista_munis = ", ".join(f"'{m}'" for m in sorted(munis_finales))
    filtro_geo = f"p.cod_muni IN ({lista_munis})" if lista_munis else "1=0"

# -- Filtro de productos --
partes_prod = []
if producto_sel:
    lista_prod = ", ".join(f"'{p}'" for p in producto_sel)
    partes_prod.append(f"p.producto IN ({lista_prod})")
elif subgrupo_sel:
    lista_sub = ", ".join(f"'{s}'" for s in subgrupo_sel)
    partes_prod.append(f"p.subgrupo_producto IN ({lista_sub})")
elif grupo_sel:
    lista_grp = ", ".join(f"'{g}'" for g in grupo_sel)
    partes_prod.append(f"p.grupo_productos IN ({lista_grp})")

# Priorizados: si no hay filtro de producto específico, restringir por lista
if priori_sel != "Todos" and not producto_sel:
    lista_priori = ", ".join(f"'{p}'" for p in prod_filtrado["producto"].tolist())
    partes_prod.append(f"p.producto IN ({lista_priori})")

filtro_prod  = " AND ".join(partes_prod) if partes_prod else "1=1"
if anios_sel:
    lista_anios = ", ".join(str(a) for a in anios_sel)
    filtro_fecha = f"YEAR(p.fecha) IN ({lista_anios})"
else:
    filtro_fecha = f"p.fecha BETWEEN '{fecha_ini}' AND '{fecha_fin}'"

# -- Filtro de destino --
partes_dest = []
if central_sel:
    lista_cent = ", ".join(f"'{c}'" for c in central_sel)
    partes_dest.append(f"p.central_may IN ({lista_cent})")
elif ciudad_sel:
    lista_ciudad = ", ".join(f"'{c}'" for c in ciudad_sel)
    partes_dest.append(f"p.ciudad_destino IN ({lista_ciudad})")
filtro_dest = " AND ".join(partes_dest) if partes_dest else "1=1"

# -- WHERE combinado --
where_sql = f"({filtro_geo}) AND ({filtro_prod}) AND ({filtro_fecha}) AND ({filtro_dest})"

# -- WHERE para CSV diario 2022-2026 (período fijo, ignora selector de fechas) --
where_diario = f"({filtro_geo}) AND ({filtro_prod}) AND (YEAR(p.fecha) BETWEEN 2022 AND 2026) AND ({filtro_dest})"

# -- WHERE anual: sin filtro de fecha para mostrar siempre todos los años --
where_anual = f"({filtro_geo}) AND ({filtro_prod}) AND ({filtro_dest})"

# ── Etiqueta visible ──────────────────────────────────────────────────────────
if escala == "Territorio funcional" and territorio_sel:
    titulo_escala = f"Territorio funcional — {territorio_sel}"
else:
    titulo_escala = escala

if dep_sel:
    titulo_escala += f" · {', '.join(dep_sel)}"
if muni_sel:
    titulo_escala += f" · {', '.join(muni_sel)}"
if grupo_sel and not subgrupo_sel and not producto_sel:
    titulo_escala += f" · {', '.join(grupo_sel)}"
if subgrupo_sel and not producto_sel:
    titulo_escala += f" · {', '.join(subgrupo_sel)}"
if producto_sel:
    titulo_escala += f" · {', '.join(producto_sel)}"

# ── Línea de filtros activos (reutilizable en todos los bloques) ──────────────
def _fmt(lst, n=2):
    """Formatea lista: máx n elementos + '…' si hay más."""
    if not lst: return ""
    return ", ".join(lst[:n]) + ("…" if len(lst) > n else "")

# Origen: escala base + depto + municipio (sin producto)
_origen_base = (
    f"Territorio funcional — {territorio_sel}"
    if (escala == "Territorio funcional" and territorio_sel)
    else escala
)
_origen_partes = [_origen_base]
if dep_sel:  _origen_partes.append(_fmt(dep_sel))
if muni_sel: _origen_partes.append(_fmt(muni_sel))
_origen_str = " · ".join(_origen_partes)

# Destino
if central_sel:
    _destino_str = _fmt(central_sel)
elif ciudad_sel:
    _destino_str = _fmt(ciudad_sel)
else:
    _destino_str = "Todos"

# Período
if anios_sel:
    _periodo_label, _periodo_str = "Años", ", ".join(str(a) for a in sorted(anios_sel))
else:
    _periodo_label, _periodo_str = "Período", f"{fecha_ini} → {fecha_fin}"

# Producto (nivel más específico activo)
if producto_sel:
    _prod_label, _prod_str = "Producto", _fmt(producto_sel)
elif subgrupo_sel:
    _prod_label, _prod_str = "Subgrupo", _fmt(subgrupo_sel)
elif grupo_sel:
    _prod_label, _prod_str = "Grupo", _fmt(grupo_sel)
else:
    _prod_label, _prod_str = "Producto", "Todos"

_partes_filtros = [
    f"**Origen:** {_origen_str}",
    f"**Destino:** {_destino_str}",
    f"**{_periodo_label}:** {_periodo_str}",
    f"**{_prod_label}:** {_prod_str}",
]
if priori_sel != "Todos":
    _partes_filtros.append(f"**FAO 178:** {priori_sel}")

linea_filtros       = "  ·  ".join(_partes_filtros)
# Versión sin período — para la sección anual (que ignora el filtro de fechas)
linea_filtros_anual = "  ·  ".join(
    p for p in _partes_filtros if not p.startswith(f"**{_periodo_label}")
)

# ── Consultas ─────────────────────────────────────────────────────────────────
@st.cache_data
def cargar_resumen(where: str):
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            COUNT(*)                            AS total_registros,
            ROUND(SUM(p.cantidad_kg) / 1000, 0) AS toneladas,
            MIN(p.fecha)::VARCHAR               AS fecha_inicio,
            MAX(p.fecha)::VARCHAR               AS fecha_fin,
            COUNT(DISTINCT p.producto)          AS n_productos,
            COUNT(DISTINCT p.muni_origen)       AS n_origenes
        FROM '{PARQUET}' p
        WHERE {where}
    """).df()
    con.close()
    return df

@st.cache_data
def cargar_por_mes(where: str):
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            DATE_TRUNC('month', p.fecha)::DATE      AS mes,
            COUNT(*)                                AS registros,
            ROUND(SUM(p.cantidad_kg) / 1000, 0)    AS toneladas
        FROM '{PARQUET}' p
        WHERE {where}
        GROUP BY mes
        ORDER BY mes
    """).df()
    con.close()
    df["mes"] = pd.to_datetime(df["mes"])
    return df

@st.cache_data
def cargar_por_anio(where: str):
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT
            YEAR(p.fecha)                       AS anio,
            COUNT(*)                            AS registros,
            ROUND(SUM(p.cantidad_kg) / 1000, 0) AS toneladas
        FROM '{PARQUET}' p
        WHERE {where}
        GROUP BY anio
        ORDER BY anio
    """).df()
    con.close()
    return df

# ── Métricas ──────────────────────────────────────────────────────────────────
resumen = cargar_resumen(where_sql)

st.subheader(f"📊 {titulo_escala}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total registros",          f"{resumen['total_registros'][0]:,.0f}")
col2.metric("Toneladas totales",        f"{resumen['toneladas'][0]:,.0f}")
col3.metric("Productos",                resumen['n_productos'][0])
col4.metric("Municipios/países origen", resumen['n_origenes'][0])

st.markdown(linea_filtros)
st.caption(f"Datos disponibles: {resumen['fecha_inicio'][0]} → {resumen['fecha_fin'][0]}")

st.divider()

# ── Tabla y gráfico por año ───────────────────────────────────────────────────
st.subheader("📅 Abastecimiento anual — toneladas y viajes registrados")
st.caption("Totales históricos del período SIPSA-A disponible · No se afecta por el filtro de fechas — sirve como referencia fija")
st.markdown(linea_filtros_anual + "  ·  **Período:** _todos los años disponibles_")

# Usa where_anual (sin filtro de fecha) para mostrar siempre todos los años
df_anio = cargar_por_anio(where_anual)
df_anio["anio"] = df_anio["anio"].astype(str)

col_tabla, col_grafico = st.columns([1, 2])

with col_tabla:
    # Filas de datos
    filas = {
        "Año":       df_anio["anio"].tolist(),
        "Registros": df_anio["registros"].apply(lambda x: f"{int(x):,}").tolist(),
        "Toneladas": df_anio["toneladas"].apply(lambda x: f"{int(x):,}").tolist(),
    }
    # Fila de totales
    filas["Año"].append("TOTAL")
    filas["Registros"].append(f"{int(df_anio['registros'].sum()):,}")
    filas["Toneladas"].append(f"{int(df_anio['toneladas'].sum()):,}")
    df_tabla = pd.DataFrame(filas)
    st.dataframe(df_tabla, use_container_width=True, hide_index=True)

with col_grafico:
    fig_anio = go.Figure()
    fig_anio.add_trace(go.Bar(
        x=df_anio["anio"],
        y=df_anio["toneladas"],
        name="Toneladas",
        marker_color="#4C9BE8",
        yaxis="y1",
        hovertemplate="%{x}<br>Toneladas: %{y:,.0f}<extra></extra>",
    ))
    fig_anio.add_trace(go.Scatter(
        x=df_anio["anio"],
        y=df_anio["registros"],
        name="Viajes (registros)",
        mode="lines+markers",
        marker=dict(size=6, color="#F4A261"),
        line=dict(color="#F4A261", width=2),
        yaxis="y2",
        hovertemplate="%{x}<br>Viajes: %{y:,.0f}<extra></extra>",
    ))
    fig_anio.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(
            title=dict(text="Toneladas", font=dict(color="#4C9BE8")),
            tickfont=dict(color="#4C9BE8"),
            tickformat=",",
        ),
        yaxis2=dict(
            title=dict(text="Viajes (registros)", font=dict(color="#F4A261")),
            tickfont=dict(color="#F4A261"),
            tickformat=",",
            overlaying="y",
            side="right",
            showgrid=False,
        ),
        xaxis=dict(title=""),
        barmode="group",
    )
    st.plotly_chart(fig_anio, use_container_width=True)

st.divider()

# ── Gráfica mensual doble eje ─────────────────────────────────────────────────
st.subheader("📈 Serie mensual — Toneladas y Registros")
st.markdown(linea_filtros)

df_mes = cargar_por_mes(where_sql)

fig = go.Figure()

fig.add_trace(go.Bar(
    x=df_mes["mes"],
    y=df_mes["toneladas"],
    name="Toneladas",
    marker_color="#4C9BE8",
    yaxis="y1",
    hovertemplate="%{x|%b %Y}<br>Toneladas: %{y:,.0f}<extra></extra>",
))

fig.add_trace(go.Scatter(
    x=df_mes["mes"],
    y=df_mes["registros"],
    name="Registros",
    mode="lines",
    line=dict(color="#F4A261", width=2),
    yaxis="y2",
    hovertemplate="%{x|%b %Y}<br>Registros: %{y:,.0f}<extra></extra>",
))

fig.update_layout(
    xaxis=dict(
        rangeslider=dict(visible=True),
        type="date",
        tickformat="%b %Y",
    ),
    yaxis=dict(
        title=dict(text="Toneladas", font=dict(color="#4C9BE8")),
        tickfont=dict(color="#4C9BE8"),
        tickformat=",",
    ),
    yaxis2=dict(
        title=dict(text="Registros", font=dict(color="#F4A261")),
        tickfont=dict(color="#F4A261"),
        tickformat=",",
        overlaying="y",
        side="right",
    ),
    legend=dict(orientation="h", y=1.08),
    hovermode="x unified",
    height=480,
    margin=dict(l=10, r=10, t=30, b=60),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Mapa de flujos de abastecimiento ─────────────────────────────────────────
_MAPA_VISIBLE = True  # ← cambiar a False para ocultar el mapa
if _MAPA_VISIBLE: st.subheader("🗺️ Mapa de flujos de abastecimiento")
if _MAPA_VISIBLE: st.markdown(linea_filtros)

_PALETA_MAPA = [
    [64, 224, 208, 210], [255, 165,   0, 210], [100, 149, 237, 210],
    [255,  99, 132, 210], [ 50, 205,  50, 210], [255, 215,   0, 210],
    [147, 112, 219, 210], [255,  69,   0, 210], [  0, 255, 200, 210],
    [255,  20, 147, 210], [154, 205,  50, 210], [255, 127,  80, 210],
    [ 30, 144, 255, 210], [220,  20,  60, 210], [  0, 250, 154, 210],
    [255, 160, 122, 210], [186,  85, 211, 210], [  0, 206, 209, 210],
    [127, 255,   0, 210], [255,   0, 255, 210], [135, 206, 235, 210],
    [240, 128, 128, 210], [144, 238, 144, 210], [255, 182, 193, 210],
    [173, 255,  47, 210], [ 70, 130, 180, 210], [255,  99,  71, 210],
    [  0, 191, 255, 210], [255, 140,   0, 210], [186, 225, 255, 210],
    [240, 230, 140, 210], [255, 228, 196, 210], [200, 100, 100, 210],
]

@st.cache_data
def cargar_flujos_mapa(where: str):
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT p.cod_muni, p.muni_origen, p.depto_origen,
               p.ciudad_destino, p.central_may,
               ROUND(SUM(p.cantidad_kg) / 1000, 0) AS toneladas,
               COUNT(*) AS n_viajes
        FROM '{PARQUET}' p
        WHERE {where}
        GROUP BY p.cod_muni, p.muni_origen, p.depto_origen,
                 p.ciudad_destino, p.central_may
        ORDER BY toneladas DESC
    """).df()
    con.close()
    return df

if _MAPA_VISIBLE and not os.path.exists(COORD_MUNI):
    st.warning(
        "⚠️ Falta el archivo de coordenadas de municipios.  \n"
        "Ejecuta este script **una sola vez** en VS Code con `.venv` activado:  \n"
        "```\ncd L:\\DATA\\SIPSAA\n.venv\\Scripts\\activate\npython CSV/generar_coordenadas_muni.py\n```  \n"
        "Tarda ~30 minutos. El progreso se guarda en `tmaestra_coordenadas_muni.csv`."
    )
elif _MAPA_VISIBLE:
    _coord_muni = pd.read_csv(
        COORD_MUNI, sep=";", encoding="utf-8-sig",
        dtype={"cod_muni": str},
        usecols=["cod_muni", "lat", "lon"],
    )
    _coord_muni = _coord_muni.dropna(subset=["lat", "lon"])
    _coord_muni["lat"] = pd.to_numeric(_coord_muni["lat"], errors="coerce")
    _coord_muni["lon"] = pd.to_numeric(_coord_muni["lon"], errors="coerce")
    _coord_muni = _coord_muni.dropna()

    _coord_cent = pd.read_csv(COORD_CENTRALES, sep=";", encoding="utf-8-sig")

    df_flujos_raw = cargar_flujos_mapa(where_sql)

    df_flujos_m = df_flujos_raw.merge(
        _coord_muni.rename(columns={"lat": "lat_orig", "lon": "lon_orig"}),
        on="cod_muni", how="inner",
    )
    df_flujos_m = df_flujos_m.merge(
        _coord_cent[["central_may", "lat", "lon"]].rename(
            columns={"lat": "lat_dest", "lon": "lon_dest"}
        ),
        on="central_may", how="inner",
    )

    if df_flujos_m.empty:
        st.info("Sin datos georreferenciados para los filtros actuales.")
    else:
        # ── Controles ────────────────────────────────────────────────────────
        col_mc1, col_mc2 = st.columns([1, 2])
        with col_mc1:
            metrica_mapa = st.radio(
                "Grosor del arco por",
                ["Toneladas", "Viajes"],
                horizontal=True, key="radio_mapa",
            )
        with col_mc2:
            umbral_mapa = st.slider(
                "% de cobertura (Pareto)", min_value=50, max_value=100,
                value=80, step=5, key="slider_mapa",
            )
        st.caption(
            "🖱️ **Navegar:** arrastrar = mover  ·  scroll = zoom  ·  "
            "clic derecho + arrastrar = inclinar/rotar  ·  Ctrl + arrastrar = rotar"
        )

        val_col = "toneladas" if metrica_mapa == "Toneladas" else "n_viajes"

        # ── Corte Pareto ──────────────────────────────────────────────────────
        df_sorted = df_flujos_m.sort_values(val_col, ascending=False).copy()
        _total    = df_sorted[val_col].sum()
        _n_pareto = int((df_sorted[val_col].cumsum() < _total * umbral_mapa / 100).sum()) + 1
        df_mapa   = df_sorted.head(_n_pareto).copy()

        # ── Color por central (asignado sobre TODOS los flujos, no solo el Pareto) ──
        # Orden global para que los colores sean estables al mover el slider
        centrales_ord = (
            df_flujos_m.groupby("central_may")[val_col]
            .sum().sort_values(ascending=False).index.tolist()
        )
        color_map = {c: _PALETA_MAPA[i % len(_PALETA_MAPA)]
                     for i, c in enumerate(centrales_ord)}

        # Arcos: degradado del mismo color — origen muy transparente, destino opaco
        df_mapa["_c"] = df_mapa["central_may"].map(color_map)
        df_mapa["color_dest"] = df_mapa["_c"].apply(
            lambda c: [c[0], c[1], c[2], 220]
        )
        df_mapa["color_orig"] = df_mapa["_c"].apply(
            lambda c: [c[0], c[1], c[2], 40]
        )

        # ── Grosor (escala lineal, 0.5–8 px) ─────────────────────────────────
        _max_val = df_mapa[val_col].max()
        df_mapa["ancho"] = ((df_mapa[val_col] / _max_val) * 7 + 0.5).clip(0.5, 8)

        # ── Popup para arcos ──────────────────────────────────────────────────
        df_mapa["_ton_fmt"]    = df_mapa["toneladas"].apply(lambda x: f"{int(x):,}")
        df_mapa["_viajes_fmt"] = df_mapa["n_viajes"].apply(lambda x: f"{int(x):,}")
        df_mapa["_popup"] = (
            "<b>" + df_mapa["muni_origen"] + "</b> (" + df_mapa["depto_origen"] + ")<br/>"
            "→ <b>" + df_mapa["ciudad_destino"] + "</b> · " + df_mapa["central_may"] + "<br/>"
            + df_mapa["_ton_fmt"] + " ton &nbsp;·&nbsp; " + df_mapa["_viajes_fmt"] + " viajes"
        )

        # ── Puntos de centrales coloreados + popup ────────────────────────────
        _coord_cent_col = _coord_cent.copy()
        _coord_cent_col["color"] = _coord_cent_col["central_may"].apply(
            lambda c: color_map.get(c, [200, 200, 200, 200])
        )
        _coord_cent_col["_popup"] = (
            "<b>" + _coord_cent_col["central_may"] + "</b><br/>"
            + _coord_cent_col["ciudad_destino"]
        )

        # ── Capas ─────────────────────────────────────────────────────────────
        layer_arcos = pdk.Layer(
            "ArcLayer",
            data=df_mapa,
            get_source_position=["lon_orig", "lat_orig"],
            get_target_position=["lon_dest", "lat_dest"],
            get_source_color="color_orig",
            get_target_color="color_dest",
            get_width="ancho",
            width_scale=1,
            width_min_pixels=0.5,
            width_max_pixels=8,
            auto_highlight=True,
            pickable=True,
        )

        layer_dest = pdk.Layer(
            "ScatterplotLayer",
            data=_coord_cent_col,
            get_position=["lon", "lat"],
            get_fill_color="color",
            get_radius=18_000,
            radius_min_pixels=5,
            radius_max_pixels=14,
            stroked=True,
            get_line_color=[255, 255, 255, 180],
            line_width_min_pixels=1,
            auto_highlight=True,
            pickable=True,
        )

        view = pdk.ViewState(
            latitude=5.5, longitude=-74.5,
            zoom=5, pitch=30, bearing=0,
        )

        deck = pdk.Deck(
            layers=[layer_arcos, layer_dest],
            initial_view_state=view,
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            tooltip={
                "html": "{_popup}",
                "style": {
                    "backgroundColor": "rgba(20,20,20,0.88)",
                    "color": "white",
                    "fontSize": "12px",
                    "padding": "6px 10px",
                    "borderRadius": "4px",
                },
            },
        )

        st.pydeck_chart(deck, use_container_width=True, height=560)

        # ── Caption y leyenda ─────────────────────────────────────────────────
        _pct_real = df_mapa[val_col].sum() / _total * 100 if _total > 0 else 0
        st.caption(
            f"{len(df_mapa):,} flujos representan el {_pct_real:.1f}% "
            f"({'toneladas' if metrica_mapa == 'Toneladas' else 'viajes'}) "
            f"del total filtrado ({len(df_flujos_m):,} flujos)  ·  "
            "Arco: transparente en origen → opaco en destino, mismo color que la central"
        )

        _leyenda = "".join([
            f'<span style="display:inline-flex;align-items:center;'
            f'margin:3px 14px 3px 0;white-space:nowrap;">'
            f'<span style="display:inline-block;width:13px;height:13px;border-radius:3px;'
            f'background:rgb({color_map[c][0]},{color_map[c][1]},{color_map[c][2]});'
            f'margin-right:5px;flex-shrink:0;border:1px solid rgba(255,255,255,0.3);"></span>'
            f'<span style="font-size:11px;">{c}</span></span>'
            for c in centrales_ord if c in color_map
        ])
        st.markdown(
            f'<div style="line-height:2;padding:4px 0;">{_leyenda}</div>',
            unsafe_allow_html=True,
        )

st.divider()

# ── Heatmap: Orígenes por mes ─────────────────────────────────────────────────
st.subheader("🗺️ Orígenes por mes — ¿de dónde vienen los alimentos?")
st.caption(
    "Porcentaje del abastecimiento mensual por origen. "
    "Intensidad de color = mayor participación. "
    "Las celdas con ★ y valor forman el 80% del abastecimiento de ese mes."
)

st.markdown(linea_filtros)

MESES = {1:"Ene", 2:"Feb", 3:"Mar", 4:"Abr", 5:"May", 6:"Jun",
         7:"Jul", 8:"Ago", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dic"}

@st.cache_data
def cargar_heatmap(where: str, nivel: str):
    col = "p.depto_origen" if nivel == "Departamento" else "p.muni_origen"
    con = duckdb.connect()
    df  = con.execute(f"""
        SELECT MONTH(p.fecha) AS mes,
               {col}          AS origen,
               ROUND(SUM(p.cantidad_kg) / 1000, 3) AS toneladas
        FROM '{PARQUET}' p
        WHERE {where}
        GROUP BY mes, origen
    """).df()
    con.close()
    return df

col_hm1, col_hm2 = st.columns([1, 1])
with col_hm1:
    nivel_hm = st.radio("Ver por", options=["Departamento", "Municipio"],
                        horizontal=True, key="radio_hm")
with col_hm2:
    top_n = st.slider("Top orígenes", min_value=5, max_value=30,
                      value=15, step=5, key="slider_hm")

@st.cache_data
def cargar_sankey(where: str, nivel: str):
    col = "p.depto_origen" if nivel == "Departamento" else "p.muni_origen"
    con = duckdb.connect()
    df  = con.execute(f"""
        SELECT {col} AS origen,
               p.ciudad_destino || ' · ' || p.central_may AS destino,
               ROUND(SUM(p.cantidad_kg) / 1000, 0) AS toneladas,
               COUNT(*) AS n_viajes
        FROM '{PARQUET}' p
        WHERE {where}
        GROUP BY origen, destino
        ORDER BY toneladas DESC
    """).df()
    con.close()
    return df

@st.cache_data
def cargar_resumen_por_mes(where: str):
    con = duckdb.connect()
    df  = con.execute(f"""
        SELECT MONTH(p.fecha)                       AS mes,
               COUNT(*)                             AS n_registros,
               ROUND(SUM(p.cantidad_kg) / 1000, 0) AS toneladas
        FROM '{PARQUET}' p
        WHERE {where}
        GROUP BY mes ORDER BY mes
    """).df()
    con.close()
    return df

df_hm       = cargar_heatmap(where_sql, nivel_hm)
df_resumen_mes = cargar_resumen_por_mes(where_sql)

if df_hm.empty:
    st.info("No hay datos para mostrar con los filtros actuales.")
else:
    # Métrica de toneladas totales
    total_ton_hm = df_hm["toneladas"].sum()
    st.metric("Total toneladas en selección", f"{total_ton_hm:,.0f}")

    # Top N orígenes por volumen total
    top_origenes = (df_hm.groupby("origen")["toneladas"]
                    .sum().nlargest(top_n).index.tolist())
    df_top = df_hm[df_hm["origen"].isin(top_origenes)]

    # Pivot valores absolutos (top N)
    pivot_abs = (df_top.pivot_table(index="origen", columns="mes",
                                    values="toneladas", fill_value=0)
                 .reindex(columns=range(1, 13), fill_value=0))
    pivot_abs = pivot_abs.loc[pivot_abs.sum(axis=1).sort_values(ascending=True).index]

    # Porcentajes sobre el total real de cada mes (todos los orígenes, no solo top N)
    ton_mes_total = df_resumen_mes.set_index("mes")["toneladas"].reindex(range(1, 13), fill_value=1)
    pivot_pct = pivot_abs.div(ton_mes_total.values, axis=1).mul(100).round(1)

    # Renombrar columnas
    pivot_abs.columns = [MESES[c] for c in pivot_abs.columns]
    pivot_pct.columns = [MESES[c] for c in pivot_pct.columns]

    # Máscara 80% sobre TODOS los orígenes (no solo top N)
    origenes_en_80 = {}   # {mes_nombre: n_orígenes necesarios}
    mask_80 = pd.DataFrame(False, index=pivot_pct.index, columns=pivot_pct.columns)
    for mes_num in range(1, 13):
        mes_nombre = MESES[mes_num]
        # Contar sobre todos los orígenes
        df_mes_all = df_hm[df_hm["mes"] == mes_num].sort_values("toneladas", ascending=False)
        total_mes  = df_mes_all["toneladas"].sum()
        acum, count = 0, 0
        if total_mes > 0:
            for _, row in df_mes_all.iterrows():
                count += 1
                acum  += row["toneladas"] / total_mes * 100
                if acum >= 80:
                    break
        origenes_en_80[mes_nombre] = count
        # Máscara sobre top N (para resaltar en el heatmap)
        acum2 = 0
        for origen in pivot_pct[mes_nombre].sort_values(ascending=False).index:
            if pivot_pct.loc[origen, mes_nombre] > 0:
                mask_80.loc[origen, mes_nombre] = True
                acum2 += pivot_pct.loc[origen, mes_nombre]
                if acum2 >= 80:
                    break

    # Texto: todas las celdas con valor, ★ en las del 80%
    text_matrix = []
    for origen in pivot_pct.index:
        fila = []
        for mes in pivot_pct.columns:
            val = pivot_pct.loc[origen, mes]
            if val == 0:
                fila.append("")
            elif mask_80.loc[origen, mes]:
                fila.append(f"★ {val:.1f}%")
            else:
                fila.append(f"{val:.1f}%")
        text_matrix.append(fila)

    fig_hm = go.Figure(go.Heatmap(
        z             = pivot_pct.values,
        x             = pivot_pct.columns.tolist(),
        y             = pivot_pct.index.tolist(),
        colorscale    = "Blues",
        text          = text_matrix,
        texttemplate  = "%{text}",
        textfont      = dict(size=9, color="white"),
        colorbar      = dict(title="%", ticksuffix="%"),
        customdata    = pivot_abs.values,
        hovertemplate = "%{y}<br>%{x}: %{customdata:,.0f} ton (%{z:.1f}%)<extra></extra>",
    ))
    fig_hm.update_layout(
        height        = max(350, top_n * 24),
        margin        = dict(l=10, r=10, t=30, b=10),
        xaxis         = dict(title="", side="top"),
        yaxis         = dict(title=""),
        plot_bgcolor  = "rgba(0,0,0,0)",
        paper_bgcolor = "rgba(0,0,0,0)",
    )
    st.plotly_chart(fig_hm, use_container_width=True)
    st.caption("★ = forma parte del 80% del abastecimiento de ese mes · El hover muestra toneladas absolutas y porcentaje")

    # ── Tabla resumen por mes ─────────────────────────────────────────────────
    res_idx = df_resumen_mes.set_index("mes")
    tabla_data = {
        "": ["Toneladas totales", f"Orígenes en 80% (de todos)", "N° de viajes"],
    }
    for mes_num in range(1, 13):
        mes_nombre = MESES[mes_num]
        if mes_num in res_idx.index:
            ton = f"{int(res_idx.loc[mes_num, 'toneladas']):,}"
            reg = f"{int(res_idx.loc[mes_num, 'n_registros']):,}"
        else:
            ton, reg = "—", "—"
        orig = str(origenes_en_80.get(mes_nombre, "—"))
        tabla_data[mes_nombre] = [ton, orig, reg]

    st.dataframe(
        pd.DataFrame(tabla_data),
        use_container_width=True,
        hide_index=True,
    )

    # ── Sankey: flujos origen → central mayorista ─────────────────────────────
    st.markdown("---")
    st.markdown("**🔀 Flujos de abastecimiento: origen → central mayorista**")
    st.caption(
        f"Las bandas muestran el flujo desde cada {nivel_hm.lower()} de origen hacia cada central mayorista destino. "
        "Ancho proporcional al volumen. Usa el mismo nivel (Departamento/Municipio) y top N del heatmap."
    )

    df_sk_raw = cargar_sankey(where_sql, nivel_hm)

    if df_sk_raw.empty:
        st.info("Sin datos para el Sankey con los filtros actuales.")
    else:
        top_orig_sk = (df_sk_raw.groupby("origen")["toneladas"]
                       .sum().nlargest(top_n).index)
        df_sk = df_sk_raw[df_sk_raw["origen"].isin(top_orig_sk)].copy()

        # Nodos ordenados por volumen total
        origins_list = (df_sk.groupby("origen")["toneladas"]
                        .sum().sort_values(ascending=False).index.tolist())
        dests_list   = (df_sk.groupby("destino")["toneladas"]
                        .sum().sort_values(ascending=False).index.tolist())
        all_nodes    = origins_list + dests_list
        idx          = {n: i for i, n in enumerate(all_nodes)}
        node_colors  = ["#4C9BE8"] * len(origins_list) + ["#F4A261"] * len(dests_list)

        link_src = [idx[o] for o in df_sk["origen"]]
        link_tgt = [idx[d] for d in df_sk["destino"]]
        h_sk     = max(480, top_n * 22 + len(dests_list) * 14)

        col_sk1, col_sk2 = st.columns(2)

        with col_sk1:
            st.markdown("**Por toneladas**")
            fig_sk_ton = go.Figure(go.Sankey(
                node=dict(
                    label=all_nodes, color=node_colors, pad=12, thickness=14,
                    line=dict(color="rgba(0,0,0,0)", width=0),
                ),
                link=dict(
                    source=link_src, target=link_tgt,
                    value=df_sk["toneladas"].tolist(),
                    color="rgba(76,155,232,0.28)",
                    customdata=df_sk["toneladas"].tolist(),
                    hovertemplate=(
                        "%{source.label} → %{target.label}<br>"
                        "%{customdata:,.0f} toneladas<extra></extra>"
                    ),
                ),
                textfont=dict(size=9),
            ))
            fig_sk_ton.update_layout(
                height=h_sk, margin=dict(l=5, r=5, t=10, b=5),
                paper_bgcolor="rgba(0,0,0,0)", font=dict(size=9),
            )
            st.plotly_chart(fig_sk_ton, use_container_width=True)

        with col_sk2:
            st.markdown("**Por viajes (registros)**")
            fig_sk_vj = go.Figure(go.Sankey(
                node=dict(
                    label=all_nodes, color=node_colors, pad=12, thickness=14,
                    line=dict(color="rgba(0,0,0,0)", width=0),
                ),
                link=dict(
                    source=link_src, target=link_tgt,
                    value=df_sk["n_viajes"].tolist(),
                    color="rgba(244,162,97,0.28)",
                    customdata=df_sk["n_viajes"].tolist(),
                    hovertemplate=(
                        "%{source.label} → %{target.label}<br>"
                        "%{customdata:,.0f} viajes<extra></extra>"
                    ),
                ),
                textfont=dict(size=9),
            ))
            fig_sk_vj.update_layout(
                height=h_sk, margin=dict(l=5, r=5, t=10, b=5),
                paper_bgcolor="rgba(0,0,0,0)", font=dict(size=9),
            )
            st.plotly_chart(fig_sk_vj, use_container_width=True)

st.divider()

# ── EXPORTAR ──────────────────────────────────────────────────────────────────
import io
import re

def construir_nombre_archivo():
    """Genera un nombre de archivo descriptivo basado en los filtros activos."""
    partes = ["SIPSAA"]
    abrev = {
        "SIPSAA Total":                        "Total",
        "Región Central total":                "RC",
        "RC externa":                          "RCext",
        "RMBC":                                "RMBC",
        "Municipios Conmutados":               "Conmutados",
        "Solo internacionales (sin Colombia)": "Internacional",
    }
    if escala == "Territorio funcional":
        sufijo = territorio_sel if territorio_sel and territorio_sel != "Todos" else "Todos"
        partes.append(f"TF-{sufijo}")
    else:
        partes.append(abrev.get(escala, escala))
    if dep_sel:
        partes.append("-".join(d[:12] for d in dep_sel[:2]))
    if muni_sel:
        partes.append("-".join(m[:12] for m in muni_sel[:2]))
    if central_sel:
        partes.append("-".join(c[:12] for c in central_sel[:2]))
    elif ciudad_sel:
        partes.append("-".join(c[:12] for c in ciudad_sel[:2]))
    if producto_sel:
        partes.append("-".join(p[:12] for p in producto_sel[:2]))
    elif subgrupo_sel:
        partes.append("-".join(s[:12] for s in subgrupo_sel[:2]))
    elif grupo_sel:
        partes.append("-".join(g[:12] for g in grupo_sel[:2]))
    if anios_sel:
        partes.append("_".join(str(a) for a in sorted(anios_sel)))
    else:
        partes.append(f"{fecha_ini.year}-{fecha_fin.year}")
    nombre = "_".join(partes)
    nombre = re.sub(r"[^\w\-]", "-", nombre)
    nombre = re.sub(r"-{2,}", "-", nombre)
    return nombre[:80] + ".xlsx"


def construir_metadatos(df_export, n_filas):
    """Genera el DataFrame de metadatos con fuente, filtros y diccionario de datos."""
    import datetime
    filas = []

    # ── Sección 1: Fuente y descripción ───────────────────────────────────────
    filas += [
        ("FUENTE Y DESCRIPCIÓN", ""),
        ("Fuente original",
         "DANE Colombia — Sistema de Información de Precios y Abastecimiento del "
         "Sector Agropecuario (SIPSA), componente Abastecimiento de Alimentos (SIPSA_A)"),
        ("URL fuente",            "https://microdatos.dane.gov.co/index.php/catalog/697"),
        ("Versión del dataset",   "SIPSAA_TOTAL_V9.parquet"),
        ("Período total en V9",   "2018-01-02 → 2026-05-31"),
        ("Total registros en V9", "16,261,743"),
        ("Fecha de exportación",  datetime.datetime.now().strftime("%Y-%m-%d %H:%M")),
        ("Nota",
         "Este archivo es un subconjunto filtrado del dataset SIPSAA_TOTAL_V9. "
         "Los datos representan ingresos de carga agropecuaria a centrales mayoristas "
         "de Colombia, agregados por mes. Cada fila corresponde a una combinación "
         "única de período, origen, destino y producto."),
        ("", ""),
    ]

    # ── Sección 2: Filtros aplicados ──────────────────────────────────────────
    filas.append(("FILTROS APLICADOS", ""))
    if escala == "Territorio funcional":
        filas.append(("Escala geográfica",
                       f"Territorio funcional — {territorio_sel or 'Todos'}"))
    else:
        filas.append(("Escala geográfica", escala))
    filas += [
        ("Departamento(s)",           ", ".join(dep_sel)      if dep_sel      else "Todos"),
        ("Municipio(s)",              ", ".join(muni_sel)     if muni_sel     else "Todos"),
        ("Ciudad destino",            ", ".join(ciudad_sel)   if ciudad_sel   else "Todas"),
        ("Central mayorista",         ", ".join(central_sel)  if central_sel  else "Todas"),
        ("Período",
         f"Años: {', '.join(str(a) for a in sorted(anios_sel))}" if anios_sel
         else f"{fecha_ini} → {fecha_fin}"),
        ("Grupo de productos",        ", ".join(grupo_sel)    if grupo_sel    else "Todos"),
        ("Subgrupo de productos",     ", ".join(subgrupo_sel) if subgrupo_sel else "Todos"),
        ("Producto",                  ", ".join(producto_sel) if producto_sel else "Todos"),
        ("Alimento priorizado FAO 178", priori_sel),
        ("", ""),
        ("Total filas exportadas",    f"{n_filas:,}"),
        ("Total toneladas",           f"{df_export['toneladas'].sum():,.1f}"),
        ("", ""),
    ]

    # ── Sección 3: Diccionario de datos ───────────────────────────────────────
    filas.append(("DICCIONARIO DE DATOS", ""))
    diccionario = [
        ("anio",              "Año del registro de ingreso del vehículo a la central mayorista"),
        ("mes",               "Mes del registro (número: 1 = enero, 12 = diciembre)"),
        ("fecha_mes",         "Fecha del primer día del mes (formato YYYY-MM-DD). Permite agrupar y filtrar por fecha en Excel, Power Query y Power BI"),
        ("ciudad_destino",    "Ciudad donde está ubicada la central mayorista de destino"),
        ("central_may",       "Nombre de la central mayorista de destino"),
        ("cod_depto",         "Código DIVIPOLA del departamento de origen (2 dígitos). Para orígenes internacionales: 'Internacional'"),
        ("depto_origen",      "Nombre del departamento de origen. Para orígenes internacionales: 'Internacional'"),
        ("cod_muni",          "Código DIVIPOLA del municipio de origen (5 dígitos). Para orígenes internacionales: código ISO 3166-1 numérico del país"),
        ("muni_origen",       "Nombre del municipio de origen. Para orígenes internacionales: nombre del país en mayúsculas"),
        ("provincia",         "Subregión o provincia a la que pertenece el municipio según la clasificación del proyecto. Vacío para orígenes internacionales"),
        ("rc_total",          "1 = el municipio pertenece a la Región Central (Bogotá D.C., Cundinamarca, Boyacá, Huila, Meta, Tolima). 0 = no pertenece"),
        ("rc_externa",        "1 = el municipio pertenece a la Región Central excluida la RMBC (sin Bogotá D.C. ni Cundinamarca). 0 = no pertenece"),
        ("rmbc",              "1 = el municipio pertenece a la Región Metropolitana de Bogotá-Cundinamarca. 0 = no pertenece"),
        ("muni_conmutados",   "1 = municipio clasificado como conmutado en el proyecto. 0 = no clasificado"),
        ("terri_funcional",   "Nombre del territorio funcional al que pertenece el municipio. 'Ninguno' si no está asignado a ningún territorio"),
        ("muni_priori178",    "1 = municipio priorizado en el proyecto FAO 178. 0 = no priorizado"),
        ("muni_muestra178",   "1 = municipio incluido en la muestra del proyecto FAO 178. 0 = no incluido"),
        ("grupo_productos",   "Grupo de productos SIPSA — 8 grupos fijos definidos por el DANE"),
        ("subgrupo_producto", "Subgrupo de productos — clasificación secundaria construida en este proyecto, no existe en la fuente DANE original"),
        ("producto",          "Nombre del producto específico dentro de la canasta SIPSA (196 productos)"),
        ("alim_priori178",    "1 = producto priorizado en el proyecto FAO 178. 0 = no priorizado"),
        ("n_registros",       "Número de vehículos que ingresaron con esa combinación de características en ese mes. En el parquet original cada vehículo es 1 fila"),
        ("toneladas",         "Peso total del cargamento en toneladas métricas (suma de cantidad_kg / 1000), redondeado a 3 decimales"),
    ]
    filas += diccionario

    return pd.DataFrame(filas, columns=["Campo", "Descripción / Valor"])


EXCEL_LIMIT = 1_048_576

@st.cache_data(show_spinner="Preparando datos, espera un momento...")
def generar_df_export(where: str, _geo: pd.DataFrame, _prod: pd.DataFrame):
    con = duckdb.connect()
    con.register("tterr", _geo)
    con.register("tprod", _prod)
    df = con.execute(f"""
        SELECT
            YEAR(p.fecha)                       AS anio,
            MONTH(p.fecha)                      AS mes,
            p.ciudad_destino,
            p.central_may,
            p.cod_depto,
            p.depto_origen,
            p.cod_muni,
            p.muni_origen,
            t.provincia,
            t.rc_total,
            t.rc_externa,
            t.rmbc,
            t.muni_conmutados,
            t.terri_funcional,
            t.muni_priori178,
            t.muni_muestra178,
            p.grupo_productos,
            p.subgrupo_producto,
            p.producto,
            pr.alim_priori178,
            COUNT(*)                            AS n_registros,
            ROUND(SUM(p.cantidad_kg) / 1000, 3) AS toneladas
        FROM '{PARQUET}' p
        LEFT JOIN tterr t  ON p.cod_muni       = t.cod_muni
        LEFT JOIN tprod pr ON p.grupo_productos = pr.grupo_productos
                          AND p.producto        = pr.producto
        WHERE {where}
        GROUP BY ALL
        ORDER BY anio, mes, p.ciudad_destino, p.depto_origen, p.muni_origen,
                 p.grupo_productos, p.producto
    """).df()
    con.close()
    df.fillna("", inplace=True)   # internacionales: celdas vacías en vez de error
    # Agregar columna fecha_mes (primer día del mes) para facilitar análisis en Excel
    df.insert(2, "fecha_mes",
              pd.to_datetime(df["anio"].astype(str) + "-" + df["mes"].astype(str).str.zfill(2) + "-01")
              .dt.strftime("%Y-%m-%d"))
    return df


# ── Módulo 1: Exportar CSV ────────────────────────────────────────────────────
st.subheader("📄 Exportar datos agregados por mes (CSV)")
st.caption(
    "Formato sin límite de filas: puede superar las 1,048,576 filas que admite una "
    "hoja de Excel. Ideal para períodos largos o selecciones amplias. "
    "El archivo se puede cargar directamente en Power Query, Power BI o cualquier "
    "herramienta de análisis. Separador: punto y coma (;) · Decimal: coma (,) · Codificación: UTF-8."
)

if st.button("🔍 Preparar descarga CSV", type="primary", key="btn_csv"):
    df_export_csv = generar_df_export(where_sql, geo, prod)
    n_filas_csv   = len(df_export_csv)

    if n_filas_csv == 0:
        st.warning("El filtro activo no devuelve datos. Ajusta los filtros e intenta de nuevo.")
    else:
        nombre_csv = construir_nombre_archivo().replace(".xlsx", ".csv")
        csv_bytes  = df_export_csv.to_csv(index=False, sep=";", decimal=",", encoding="utf-8-sig").encode("utf-8-sig")

        st.success(f"✅ {n_filas_csv:,} filas listas.")
        st.download_button(
            label="⬇️ Descargar CSV",
            data=csv_bytes,
            file_name=nombre_csv,
            mime="text/csv",
            key="dl_csv",
        )
        st.info(
            f"📂 El archivo **{nombre_csv}** se descargará en tu carpeta de "
            "**Descargas**. Si no aparece de inmediato, revisa la barra de descargas "
            "de tu navegador."
        )

st.divider()

# ── Módulo 2: Exportar Excel ──────────────────────────────────────────────────
st.subheader("📊 Exportar datos agregados por mes (Excel)")
st.caption(
    "Genera un archivo .xlsx con dos hojas: los datos filtrados y una hoja de "
    "metadatos con la fuente, los filtros aplicados y el diccionario de columnas. "
    f"Límite: **1,048,576 filas** (restricción del formato Excel). "
    "Si el resultado supera ese número, usa la exportación CSV."
)

if st.button("🔍 Preparar descarga Excel", type="primary", key="btn_excel"):
    df_export = generar_df_export(where_sql, geo, prod)
    n_filas   = len(df_export)

    if n_filas == 0:
        st.warning("El filtro activo no devuelve datos. Ajusta los filtros e intenta de nuevo.")
    elif n_filas > EXCEL_LIMIT:
        st.error(
            f"⚠️ El resultado tiene **{n_filas:,} filas**, que supera el límite de Excel "
            f"({EXCEL_LIMIT:,} filas). Usa la exportación CSV para este volumen de datos."
        )
    else:
        nombre_archivo = construir_nombre_archivo()
        df_meta        = construir_metadatos(df_export, n_filas)

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_export.to_excel(writer, index=False, sheet_name="SIPSAA")
            df_meta.to_excel(writer, index=False, sheet_name="Metadatos")
        buffer.seek(0)

        st.success(f"✅ {n_filas:,} filas listas — dentro del límite de Excel.")
        st.download_button(
            label="⬇️ Descargar Excel",
            data=buffer,
            file_name=nombre_archivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_excel",
        )
        st.info(
            f"📂 El archivo **{nombre_archivo}** se descargará en tu carpeta de "
            "**Descargas**. Si no aparece de inmediato, revisa la barra de descargas "
            "de tu navegador (parte inferior o superior según el navegador)."
        )

st.divider()

# ── Módulo 3: CSV Diario 2022-2026 ───────────────────────────────────────────
# DESHABILITADO EN VERSIÓN EN LÍNEA
# Este módulo escribe el archivo directamente al disco del servidor usando
# os.path.join(DIR, nombre_diario). En Streamlit Cloud el servidor es un
# contenedor efímero: el archivo se perdería y el usuario nunca podría acceder
# a él. Además, sin filtros activos puede superar los 10 millones de filas,
# bloqueando la app para todos los usuarios simultáneos.
# Para usar este módulo, ejecutar el dashboard localmente con .venv activado.
#
# st.subheader("🗂️ Exportar datos diarios 2022-2026 (CSV)")
# st.caption(
#     "Exporta cada registro individual (un vehículo = una fila) para el período "
#     "2022-2026, con todas las columnas de clasificación geográfica y de producto. "
#     "El período es fijo (2022-2026) e ignora el selector de fechas del sidebar. "
#     "Los demás filtros (origen, destino, producto) sí aplican. "
#     "El archivo se guarda directamente en la carpeta CSV del proyecto — "
#     "no se descarga por el navegador. Separador: punto y coma (;) · Decimal: coma (,) · Codificación: UTF-8."
# )
#
# if st.button("🗂️ Generar y guardar CSV diario", type="primary", key="btn_diario"):
#
#     # 1. Contar filas primero para estimar tamaño y mostrar progreso
#     with st.spinner("Contando registros..."):
#         con_count = duckdb.connect()
#         n_diario = con_count.execute(
#             f"SELECT COUNT(*) FROM '{PARQUET}' p WHERE {where_diario}"
#         ).fetchone()[0]
#         con_count.close()
#
#     if n_diario == 0:
#         st.warning("El filtro activo no devuelve datos. Ajusta los filtros e intenta de nuevo.")
#     else:
#         # 2. Construir nombre del archivo
#         nombre_base  = construir_nombre_archivo().replace(".xlsx", "")
#         nombre_diario = f"{nombre_base}_diario_2022-2026.csv"
#         output_path  = os.path.join(DIR, nombre_diario)
#
#         query_diario = f"""
#             SELECT
#                 p.fecha::VARCHAR                        AS fecha,
#                 p.ciudad_destino,
#                 p.central_may,
#                 p.cod_depto,
#                 p.depto_origen,
#                 p.cod_muni,
#                 p.muni_origen,
#                 t.provincia,
#                 t.rc_total,
#                 t.rc_externa,
#                 t.rmbc,
#                 t.muni_conmutados,
#                 t.terri_funcional,
#                 t.muni_priori178,
#                 t.muni_muestra178,
#                 p.grupo_productos,
#                 p.subgrupo_producto,
#                 p.producto,
#                 pr.alim_priori178,
#                 p.cantidad_kg
#             FROM '{PARQUET}' p
#             LEFT JOIN tterr t  ON p.cod_muni       = t.cod_muni
#             LEFT JOIN tprod pr ON p.grupo_productos = pr.grupo_productos
#                               AND p.producto        = pr.producto
#             WHERE {where_diario}
#             ORDER BY p.fecha, p.ciudad_destino, p.muni_origen,
#                      p.grupo_productos, p.producto
#         """
#
#         # 3. Escribir en chunks para no saturar la memoria
#         CHUNK = 200_000
#         con = duckdb.connect()
#         con.register("tterr", geo)
#         con.register("tprod", prod)
#         result  = con.execute(query_diario)
#         columns = [d[0] for d in result.description]
#
#         barra    = st.progress(0, text="Iniciando escritura...")
#         escritas = 0
#         primera  = True
#
#         while True:
#             rows = result.fetchmany(CHUNK)
#             if not rows:
#                 break
#             df_chunk = pd.DataFrame(rows, columns=columns)
#             df_chunk.fillna("", inplace=True)   # internacionales: celdas vacías en vez de error
#             df_chunk.to_csv(
#                 output_path,
#                 mode      = "w" if primera else "a",
#                 index     = False,
#                 header    = primera,
#                 sep       = ";",
#                 decimal   = ",",
#                 encoding  = "utf-8-sig",
#             )
#             primera   = False
#             escritas += len(rows)
#             pct = min(escritas / n_diario, 1.0)
#             barra.progress(pct, text=f"Escribiendo… {escritas:,} de {n_diario:,} filas ({pct*100:.0f}%)")
#
#         con.close()
#         barra.empty()
#         st.success(f"✅ {escritas:,} filas guardadas.")
#         st.info(f"📂 Archivo guardado en: `L:\\DATA\\SIPSAA\\CSV\\{nombre_diario}`")
