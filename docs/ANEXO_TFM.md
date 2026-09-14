# Texto sugerido para el anexo de la memoria

## Repositorio de código y resultados

El código desarrollado, los notebooks que documentan el flujo analítico, los artefactos del modelo final, una selección de resultados y la aplicación interactiva se encuentran disponibles en el repositorio de GitHub **https://github.com/xabibecerra/TFM---Xabier**. La versión de entrega está fijada mediante la *release* **v1.0.0-tfm** (**https://github.com/xabibecerra/TFM---Xabier/releases/tag/v1.0.0-tfm**) y la aplicación puede consultarse en **https://tfm---xabier-cifshluvqdsrae5yvby4df.streamlit.app/**. El repositorio incluye instrucciones de instalación, estructura de contenidos, restricciones de interpretación y pruebas automatizadas. Los datos brutos no se redistribuyen; se indican sus fuentes públicas y se incorpora únicamente un snapshot derivado y compacto necesario para ejecutar la demostración histórica.

La consulta y comprobación de los enlaces se realizó el 14 de septiembre de 2026. La memoria debe citar el identificador completo del commit asociado a la *release*, además de la etiqueta, para fijar sin ambigüedad la versión examinada. Si más adelante se deposita en Zenodo, puede añadirse también el DOI.

## Elementos incluidos en la memoria

1. URL del repositorio, URL de la aplicación y fecha de consulta.
2. Etiqueta e identificador completo del commit utilizado en la entrega.
3. Instrucción mínima de ejecución: `python -m streamlit run app/streamlit_app.py`.
4. Aclaración de que la interfaz es una simulación histórica sobre noviembre-diciembre de 2022.
5. Nota de que enero-febrero de 2023 se dedica exclusivamente al análisis descriptivo de viajes.
6. Referencia a la licencia MIT del código y a las condiciones específicas de las fuentes abiertas.

## Comprobación de entrega

- La aplicación desplegada responde y utiliza el snapshot publicado de 27 tablas.
- La *release* `v1.0.0-tfm` fija la versión de entrega.
- El anexo LaTeX registra la fecha, la etiqueta y el hash completo del commit.
- El repositorio no necesita credenciales para ejecutar la demostración histórica.
- La licencia del código y el aviso sobre datos de terceros se mantienen separados.
