# Resultados curados

- `evaluacion_final_2022/`: métricas, informes por clase, matrices de confusión, calibración y PR-AUC/AP por clase de la evaluación temporal retrospectiva con modelos congelados.
- `interpretabilidad/`: ganancia, SHAP, discrepancias y falsos negativos con soporte y tasa.
- `recomendaciones/`: política, auditoría y resúmenes operativos.
- `viajes_2023/`: cobertura y análisis descriptivo de enero-febrero de 2023.

Las tablas masivas que alimentan la interfaz se publican una sola vez en formato Parquet dentro de `../app_data/`. Esto evita duplicar 266 MB de CSV con la misma información.

La carpeta de evaluación incluye además:

- `pr_auc_por_clase_evaluacion_retrospectiva.csv`, con prevalencia, soporte y *average precision* para cada modelo y clase;
- `curvas_pr_modelos_congelados.pdf`, con las curvas precisión--recall de las clases críticas;
- `particion_temporal_estudio.pdf`, con el esquema de entrenamiento, validación, evaluación retrospectiva y descriptivo de 2023.
