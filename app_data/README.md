# Snapshot de la aplicación

Contiene 27 tablas Parquet comprimidas y `manifiesto_app.json`. Son resultados históricos derivados, no datos en tiempo real. El manifiesto registra procedencia lógica, recuentos, esquema, valores ausentes y SHA-256.

Comprobación:

```bash
python -m app.data
```

No edites manualmente estos ficheros. Si cambian las fuentes congeladas, reconstruye el snapshot desde el proyecto analítico completo y vuelve a ejecutar todas las pruebas.

