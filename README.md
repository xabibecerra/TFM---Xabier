# Predicción del riesgo de vaciado y saturación en estaciones de BiciMAD y generación de recomendaciones operativas

Repositorio técnico de un Trabajo Fin de Máster sobre la anticipación del riesgo de vaciado y saturación de estaciones de BiciMAD. Contiene el flujo metodológico en notebooks, los artefactos del modelo final, resultados curados y una aplicación Streamlit de consulta histórica.

**Autor:** Xabier Becerra Galán

**Repositorio:** <https://github.com/xabibecerra/TFM---Xabier>

**Aplicación desplegada:** <https://tfm---xabier-cifshluvqdsrae5yvby4df.streamlit.app/>

[![Abrir aplicación Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://tfm---xabier-cifshluvqdsrae5yvby4df.streamlit.app/)

> **Alcance:** es un prototipo académico retrospectivo y de solo lectura. No ofrece predicciones en tiempo real ni órdenes operativas ejecutables.

## Objetivo

El proyecto integra información temporal, disponibilidad de estaciones, viajes, meteorología y contexto espacial para:

1. clasificar cada estación-hora como estable, con riesgo de vaciado o con riesgo de saturación;
2. evaluar el modelo sin fuga temporal;
3. estudiar las señales utilizadas por el modelo y sus errores;
4. convertir predicciones críticas en candidatas técnicas de redistribución sujetas a restricciones logísticas;
5. presentar los resultados mediante una aplicación interactiva.

## Diseño temporal definitivo

| Etapa | Periodo | Finalidad |
|---|---|---|
| Entrenamiento | 2019, 2021 y enero-septiembre de 2022 | Ajuste del modelo |
| Validación externa | Octubre de 2022 | Selección del modelo y cierre del protocolo |
| Evaluación temporal retrospectiva | Noviembre-diciembre de 2022 | Comparación histórica con modelos y preprocesadores congelados |
| Análisis descriptivo | Enero-febrero de 2023 | Solo viajes |

El año 2020 no forma parte del entrenamiento principal por su carácter anómalo. Enero-febrero de 2023 no se utiliza para inferir estados, etiquetas, riesgos ni recomendaciones porque el proyecto no dispone de estados de estaciones para ese periodo.

Noviembre-diciembre de 2022 había sido consultado durante el desarrollo. Por tanto, sus resultados no se presentan como una estimación completamente independiente de generalización futura, aunque el modelo, el preprocesamiento y la política permanezcan congelados durante la evaluación publicada.

## Resultado principal

El modelo final es `xgboost_refined`. Sobre 379.104 observaciones de la evaluación retrospectiva obtuvo `F1-macro = 0,8068` y `balanced accuracy = 0,8208`. Su precisión media (*average precision*, área bajo la curva precisión--recall) fue `0,9949` para estable, `0,8932` para riesgo de vaciado y `0,6722` para riesgo de saturación. Los resultados completos y la regresión logística de referencia están en [`results/evaluacion_final_2022`](results/evaluacion_final_2022/).

Las importancias por ganancia y SHAP describen señales utilizadas por el modelo, no relaciones causales. Las recomendaciones exportadas son candidatas técnicas: separan señal predictiva, factibilidad logística y explicación operativa.

## Aplicación interactiva

Requiere Python 3.13. Desde la raíz del repositorio:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m app.data
python -m streamlit run app/streamlit_app.py
```

La comprobación de datos debe terminar con `Carga correcta: 27 tablas verificadas`. La aplicación utiliza exclusivamente los Parquet de `app_data/`; no entrena el modelo, no modifica umbrales y no recalcula recomendaciones. La documentación detallada está en [`README_APP.md`](README_APP.md).

## Notebooks

| Notebook | Contenido |
|---|---|
| `01` | Creación de variables y conjuntos temporales |
| `02` | Baselines y modelización inicial sin fuga |
| `03` | Modelos no lineales |
| `04` | Extensión de modelos no lineales |
| `05` | Primera interpretabilidad y análisis de errores |
| `06` | Optimización temporal de hiperparámetros |
| `06b` | Refinamiento de XGBoost y regresión logística |
| `07` | Modelo final y validación externa de octubre de 2022 |
| `08` | Evaluación temporal retrospectiva de los modelos congelados en noviembre-diciembre de 2022 |
| `09` | Interpretabilidad del modelo final y análisis de errores |
| `10` | Candidatas de recomendación operativa |
| `11` | Análisis descriptivo independiente de viajes de 2023 |

Las copias públicas no contienen salidas de ejecución ni rutas personales. Los resultados relevantes se conservan en `results/` y `app_data/`. La ejecución integral de los notebooks requiere obtener las fuentes abiertas y reconstruir las capas intermedias descritas en [`docs/DATOS_Y_REPRODUCIBILIDAD.md`](docs/DATOS_Y_REPRODUCIBILIDAD.md).

## Estructura

```text
app/             Aplicación Streamlit
app_data/        Snapshot compacto utilizado por la aplicación
models/          Modelos congelados y huellas SHA-256
notebooks/       Flujo analítico 01–11
results/         Tablas y figuras curadas
scripts/         Preparación e integración de datos
tests/           Pruebas automatizadas
docs/            Alcance, reproducibilidad y texto para el anexo
```

## Verificación

```bash
python -m unittest discover -s tests -v
```

Las pruebas comprueban integridad de datos, navegación, reglas temporales, separación del análisis 2023, restricciones operativas y ausencia de reentrenamiento en la aplicación.

## Límites de interpretación

- `critical_risk_score` se usa para ordenar, no para ajustar umbrales con el test.
- `critical_risk_type` no origina una acción cuando la predicción es estable.
- SHAP y la ganancia reflejan asociaciones predictivas, no causas.
- Las horas y estaciones sensibles son indicadores de cautela, siempre acompañados de soporte, falsos negativos y tasa.
- Cada estación-hora es un escenario independiente; las unidades sumadas entre horas no representan bicicletas únicas ni rutas de vehículos.
- La factibilidad publicada no incorpora flota, red viaria, turnos, tiempos ni costes reales.

## Versión de entrega

La entrega se identifica mediante la *release* [`v1.0.0-tfm`](https://github.com/xabibecerra/TFM---Xabier/releases/tag/v1.0.0-tfm), publicada el 14 de septiembre de 2026. La etiqueta fija el código, los notebooks, los resultados curados, el snapshot de la aplicación y sus pruebas; la rama `main` puede recibir cambios posteriores.

## Datos y licencia

El código original se publica con licencia MIT, disponible en [`LICENSE`](LICENSE). Esta licencia no sustituye las condiciones aplicables a los datos ni concede derechos sobre materiales de terceros. `app_data/` contiene tablas derivadas y compactas necesarias para ejecutar la demostración histórica; las fuentes, atribución y límites de reutilización se documentan en [`NOTICE.md`](NOTICE.md) y [`docs/DATOS_Y_REPRODUCIBILIDAD.md`](docs/DATOS_Y_REPRODUCIBILIDAD.md).

## Relación con el TFM

El repositorio constituye el anexo técnico: permite inspeccionar la preparación, modelización, validación temporal, interpretabilidad, análisis de errores, recomendaciones y aplicación que sustentan la memoria. El texto sugerido para citarlo se encuentra en [`docs/ANEXO_TFM.md`](docs/ANEXO_TFM.md).
