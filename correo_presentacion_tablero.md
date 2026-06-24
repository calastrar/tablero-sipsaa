Asunto: Tablero interactivo SIPSAA — Sistema de Abastecimiento de Alimentos (versión en revisión)


Estimados,

Compartimos con ustedes un tablero interactivo desarrollado a partir de los microdatos del componente de Abastecimiento de Alimentos (SIPSA_A) del Sistema de Información de Precios y Abastecimiento del Sector Agropecuario, operado por el DANE Colombia.

El tablero está disponible en:
https://tablero-sipsaa.streamlit.app


FUENTE DE DATOS

Los datos provienen del repositorio oficial de microdatos del DANE (https://microdatos.dane.gov.co/index.php/catalog/697) y cubren el período enero de 2018 a mayo de 2026. El conjunto de datos consolidado cuenta con 16.261.743 registros, donde cada fila representa el ingreso de un vehículo cargado con productos agropecuarios a una central mayorista del país. En total se registran aproximadamente 55.155 millones de kilogramos movilizados a lo largo del período, provenientes de 1.047 municipios y países de origen.


FILTROS DISPONIBLES

El tablero permite segmentar la información de manera flexible a través de los siguientes filtros, todos interactivos y aplicados en tiempo real:

    - Destino: ciudad de la central mayorista y nombre de la central.
    - Origen: escala geográfica (total nacional, Región Central, territorios funcionales, municipios conmutados, registros internacionales), departamento y municipio.
    - Período: selección por año(s) o por rango de fechas.
    - Productos: grupo, subgrupo y producto específico de la canasta SIPSA (196 productos).
    - Priorización FAO 178: permite filtrar por productos priorizados en el marco del proyecto FAO 178.


MÓDULOS DEL TABLERO

1. Indicadores principales. Muestra en tiempo real el número de registros, las toneladas totales, el número de productos distintos y el número de municipios o países de origen correspondientes a la selección activa.

2. Abastecimiento anual. Tabla y gráfico de doble eje con toneladas y número de viajes por año. Este módulo es inmune al filtro de fechas y sirve como referencia histórica fija para comparar cualquier selección con el comportamiento del período completo.

3. Serie mensual. Gráfico de barras y línea con toneladas y registros por mes, con selector de rango integrado para explorar subperíodos de interés.

4. Mapa de flujos. Visualización geográfica de los flujos de abastecimiento desde los municipios de origen hacia las centrales mayoristas de destino. Los arcos se colorean por central y su grosor es proporcional al volumen o al número de viajes. Por defecto muestra los flujos que concentran el 80% del total filtrado (criterio de Pareto), con un control deslizante para ajustar ese umbral.

5. Mapa de calor y Sankey. Heatmap mensual que muestra la participación porcentual de cada departamento o municipio de origen en el abastecimiento de cada mes, con marcadores en las celdas que forman el 80% del volumen. Incluye tabla resumen y dos diagramas de Sankey (flujos por toneladas y por viajes) que ilustran la relación entre orígenes y centrales mayoristas.

6. Exportación de datos. Permite descargar los datos filtrados en formato CSV o Excel, agregados por mes, con una hoja de metadatos que documenta la fuente, los filtros aplicados y el diccionario de columnas. El archivo exportado facilita el análisis complementario en Power BI, Power Query o cualquier herramienta de análisis.


ESTADO DEL DESARROLLO

El tablero se encuentra actualmente en fase de revisión. Si bien opera sobre la totalidad de los 16 millones de registros disponibles y cubre ocho años de información, aún hay espacio para incorporar nuevas visualizaciones, ampliar las escalas geográficas y refinar la experiencia de usuario.

Agradecemos cualquier comentario, sugerencia o pregunta que puedan tener. La retroalimentación de quienes lo utilicen es fundamental para orientar las próximas mejoras.

Quedamos atentos.

Cordialmente,

Camilo Andrés Lastra Romero
