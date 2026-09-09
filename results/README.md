# Resultados curados

- `evaluacion_final_2022/`: métricas, informes por clase, matrices de confusión y calibración del test congelado.
- `interpretabilidad/`: ganancia, SHAP, discrepancias y falsos negativos con soporte y tasa.
- `recomendaciones/`: política, auditoría y resúmenes operativos.
- `viajes_2023/`: cobertura y análisis descriptivo de enero-febrero de 2023.

Las tablas masivas que alimentan la interfaz se publican una sola vez en formato Parquet dentro de `../app_data/`. Esto evita duplicar 266 MB de CSV con la misma información.

