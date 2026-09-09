# Texto sugerido para el anexo de la memoria

## Repositorio de código y resultados

El código desarrollado, los notebooks que documentan el flujo analítico, los artefactos del modelo final, una selección de resultados y la aplicación interactiva se encuentran disponibles en el repositorio de GitHub **https://github.com/xabibecerra/TFM---Xabier**. El repositorio incluye instrucciones de instalación, estructura de contenidos, restricciones de interpretación y pruebas automatizadas. Los datos brutos no se redistribuyen; se indican sus fuentes públicas y se incorpora únicamente un snapshot derivado y compacto necesario para ejecutar la demostración histórica.

El historial debe citar una versión concreta —preferiblemente una *release* etiquetada como `v1.0.0-tfm`— y no solo la rama principal. Si se deposita esa versión en Zenodo, es preferible añadir también el DOI para que la referencia permanezca estable.

## Elementos que conviene añadir en la memoria

1. URL del repositorio y fecha de última consulta.
2. Etiqueta o identificador del commit utilizado en la entrega.
3. Instrucción mínima de ejecución: `python -m streamlit run app/streamlit_app.py`.
4. Aclaración de que la interfaz es una simulación histórica sobre noviembre-diciembre de 2022.
5. Nota de que enero-febrero de 2023 se dedica exclusivamente al análisis descriptivo de viajes.
6. Referencia a la licencia finalmente elegida y a las condiciones de las fuentes abiertas.

## Comprobación previa a entregar

- Comprobar que la URL definitiva sigue accesible.
- Crear una *release* después de la revisión final.
- Copiar en la memoria el hash del commit de esa *release*.
- Comprobar el enlace desde una ventana privada del navegador.
- Confirmar que no se ha publicado ningún dato, documento o credencial ajeno al TFM.
