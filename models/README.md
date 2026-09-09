# Modelos congelados

Esta carpeta conserva los dos artefactos ajustados antes de abrir el test final:

- `xgboost_refined_validacion_externa.pkl`: modelo final.
- `logistic_refined_validacion_externa.pkl`: baseline comparativo.

El notebook 08 solo los evalúa; no ejecuta `.fit()`. Los notebooks 09 y 10 mantienen el XGBoost congelado. La aplicación no deserializa ni utiliza estos ficheros.

Los Pickle pueden ejecutar código al cargarse. No deben abrirse si se han descargado de una fuente no confiable. Verifica primero `SHA256SUMS`.

