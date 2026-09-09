# Datos y reproducibilidad

## Qué contiene el repositorio

La aplicación se puede ejecutar con el snapshot de `app_data/`. Este snapshot reúne 27 tablas Parquet derivadas de los resultados congelados de los notebooks 08–11 y un manifiesto con recuentos, tipos, huellas SHA-256 y reglas de alcance.

Los resultados curados de `results/` permiten revisar métricas, matrices de confusión, importancia global y por clase, falsos negativos con denominador, política operativa y análisis descriptivo de viajes.

Los modelos serializados de `models/` corresponden a la validación externa previa al test. No son cargados por la aplicación. Un fichero Pickle solo debe abrirse cuando procede de una fuente de confianza; las huellas publicadas permiten comprobar que no ha cambiado.

## Qué se excluye

- los datos originales descargados de los portales públicos;
- tablas intermedias estación-hora y predicciones CSV duplicadas;
- entornos virtuales, cachés y checkpoints;
- notebooks duplicados o experimentos descartados;
- borradores de la memoria y documentación académica privada;
- cualquier secreto, credencial o ruta personal.

La exclusión reduce un proyecto local de aproximadamente 39 GB a un repositorio técnico de alrededor de 36 MB y evita subir ficheros redundantes de hasta 91 MB.

## Reconstrucción integral

Para ejecutar el flujo desde el notebook 01 se deben descargar las fuentes abiertas citadas en la memoria y conservar su estructura local. Después se ejecutan los notebooks en orden: `01`, `02`, `03`, `04`, `05`, `06`, `06b`, `07`, `08`, `09`, `10` y `11`.

La secuencia metodológica debe respetar estas reglas:

1. entrenamiento con 2019, 2021 y enero-septiembre de 2022;
2. validación en octubre de 2022;
3. test final único en noviembre-diciembre de 2022;
4. ninguna selección de modelo, recalibración o cambio de umbral a partir del test;
5. 2023 limitado a viajes observados, sin inventar estados de estación;
6. interpretabilidad entendida como asociación predictiva, no causalidad.

El script `scripts/preparar_datos_app.py` valida los CSV congelados y crea el snapshot Parquet. Como los CSV masivos no se redistribuyen, el script sirve para auditar o reconstruir el empaquetado cuando el investigador dispone de esas salidas. Para comprobar el snapshot ya incluido basta con:

```bash
python -m app.data
```

## Entornos

`requirements.txt` reproduce la aplicación verificada. Los notebooks finales registran en sus propias celdas las versiones con las que fueron ejecutados; algunos experimentos previos utilizaron entornos distintos. Por ello no se presenta un único entorno como reproducción bit a bit de todas las fases históricas.

## Integridad

- `app_data/manifiesto_app.json` contiene SHA-256 de cada Parquet y los recuentos esperados.
- `models/SHA256SUMS` contiene SHA-256 de los artefactos congelados.
- Los manifiestos de `results/` documentan el alcance de las fases 08–11.

