# Aplicación interactiva del TFM de BiciMAD

Esta aplicación Streamlit permite consultar los resultados históricos del TFM: predicciones de riesgo del test final de noviembre-diciembre de 2022, propuestas operativas del notebook 10, interpretabilidad y errores del notebook 09, y el análisis descriptivo independiente de viajes de enero-febrero de 2023.

Es un prototipo histórico de solo lectura. No entrena modelos, no genera predicciones en tiempo real, no recalibra probabilidades, no modifica umbrales y no vuelve a calcular recomendaciones.

## Alcance temporal

| Etapa | Periodo | Uso |
|---|---|---|
| Entrenamiento | 2019, 2021 y enero-septiembre de 2022 | Ajuste de los modelos |
| Validación | Octubre de 2022 | Selección previa al test final |
| Test final | Noviembre-diciembre de 2022 | Evaluación congelada y simulación histórica de la aplicación |
| Descriptivo | Enero-febrero de 2023 | Solo viajes; febrero tiene cobertura hasta el 18/02/2023 07:22:48 |

No existen estados de estaciones para enero-febrero de 2023 dentro del proyecto. Por ese motivo, 2023 no se utiliza para crear disponibilidad, etiquetas de riesgo, predicciones o recomendaciones.

## Requisitos

- Python 3.13 recomendado. La versión utilizada para verificar la entrega es Python 3.13.5.
- Aproximadamente 24 MB para `app_data/`, además del entorno virtual.
- Conexión a internet opcional para los callejeros. Todos los mapas ofrecen un modo sin callejero.

Las versiones reproducibles están fijadas en `requirements.txt`.

## Instalación desde el principio

Abre Terminal y entra en la raíz del proyecto:

```bash
cd "/ruta/al/repositorio/tfm-bicimad-riesgo-operativo"
```

Crea y activa el entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Instala las dependencias:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

No es necesario desactivar Conda para que la aplicación funcione si el indicador `(.venv)` aparece activo. Si quieres evitar confusión entre entornos, puedes ejecutar `conda deactivate` antes de activar `.venv`.

## Datos preparados

La aplicación lee 27 tablas Parquet y su manifiesto desde `app_data/`. No lee los CSV originales al navegar por las páginas.

Comprueba su integridad antes de iniciar la aplicación:

```bash
python -m app.data
```

El resultado correcto termina con `Carga correcta: 27 tablas verificadas`. Los avisos `No runtime found, using MemoryCacheStorageManager` al ejecutar esta comprobación fuera de Streamlit son esperables.

Solo si se dispone de las salidas CSV completas de los notebooks 08-11 y se han regenerado conscientemente, prepara de nuevo las tablas:

```bash
python scripts/preparar_datos_app.py --solo-validar
python scripts/preparar_datos_app.py
python -m app.data
```

El script valida las fuentes congeladas antes de escribir una nueva preparación. No ejecuta notebooks, no carga el modelo y no ajusta umbrales.

Los CSV masivos no se redistribuyen en la copia pública de GitHub. Para usar directamente el snapshot incluido no ejecutes el script de preparación: basta con `python -m app.data`.

## Iniciar la aplicación

Desde la raíz y con `.venv` activo:

```bash
python -m streamlit run app/streamlit_app.py
```

Streamlit mostrará una dirección local, normalmente `http://localhost:8501`. Mantén la Terminal abierta. Para detener el servidor, pulsa `Control+C`.

## Contenido de las páginas

### Inicio

Resume el objetivo, el protocolo temporal, la relación entre señal predictiva, factibilidad logística y explicación, y las limitaciones de lectura.

### Riesgo 2022

Permite seleccionar únicamente fechas y horas realmente presentes en el test. Muestra la clase congelada, probabilidades, disponibilidad observada y contexto por estación. Las horas y estaciones sensibles son avisos retrospectivos y nunca correcciones del modelo.

### Recomendaciones

Consulta candidatas, parejas donante-receptora y necesidades no resueltas ya calculadas. `critical_risk_score` conserva su uso exclusivo de ordenación. Una estación estable no origina una acción desde `critical_risk_type`, aunque puede actuar como apoyo logístico. Las líneas unen estaciones; no son rutas de vehículos.

### Interpretabilidad

Compara ganancia y SHAP, permite revisar la importancia por salida de clase y presenta falsos negativos con soporte y tasa. SHAP identifica señales utilizadas por el modelo; no demuestra causas. La muestra SHAP fue estratificada con 4.000 observaciones por clase real.

### Viajes 2023

Describe cobertura, volumen, perfiles temporales, duración, actividad por estación y pares origen-destino. Los días sin cobertura se muestran como ausentes, no como demanda cero. Llegadas menos salidas es un balance de viajes, no disponibilidad de bicicletas.

## Reglas esenciales de interpretación

1. Una señal crítica es una candidata técnica, no una orden ejecutada.
2. Las probabilidades del test no se utilizan para recalibrar el modelo ni elegir umbrales.
3. Las cantidades propuestas proceden de la política operativa congelada: banda del 30-70 %, máximo de 3 km geográficos y hasta 10 bicicletas por pareja.
4. Cada hora es un escenario independiente. Las unidades agregadas entre horas no son bicicletas únicas.
5. Los rankings de errores siempre deben leerse con soporte, falsos negativos y tasa.
6. Las explicaciones SHAP son globales por clase, no locales ni causales.
7. Ninguna propuesta incorpora flota disponible, rutas viarias, turnos, tiempos o costes reales.

## Verificación

Ejecuta todas las pruebas desde la raíz:

```bash
python -m unittest discover -s tests -v
```

La entrega incluye más de 100 pruebas. Verifican integridad y caché de datos, navegación, filtros, denominadores, valores ausentes, apoyo de estaciones estables, restricciones operativas, separación de 2023, empaquetado y estados de error de la interfaz.

## Estructura relevante

```text
app/
  streamlit_app.py       Entrada y navegación
  data.py                Carga verificada y caché de solo lectura
  pages/                 Cinco páginas de la interfaz
  charts.py              Mapas y gráficos de 2022
  riesgo.py              Presentación de predicciones y errores
  operativa.py           Consulta y auditoría de propuestas
  interpretacion.py      Comparación de importancias y falsos negativos
  viajes.py              Presentación descriptiva de 2023
app_data/                 Parquet y manifiesto preparados
scripts/
  preparar_datos_app.py  Validación y preparación reproducible
tests/                    Pruebas automatizadas
```

## Problemas frecuentes

- **Falta `manifiesto_app.json` o un Parquet:** ejecuta primero `python -m app.data`. Si confirma que falta una preparación, sigue el apartado «Datos preparados».
- **El callejero no carga:** desmarca la casilla de callejero. Los puntos y las tablas seguirán disponibles.
- **La última hora del 31 de diciembre es 22:00:** es el último instante exportado; la aplicación no inventa las 23:00.
- **Febrero parece tener menos viajes:** su cobertura termina el día 18 a las 07:22:48. Compara medias de días completos, no totales brutos de meses desiguales.
- **La aplicación tarda la primera vez:** la primera lectura verifica la huella SHA-256. Las siguientes consultas utilizan la caché mientras el archivo no cambie.

## Preparación para entrega o despliegue

La entrega local debe conservar `app/`, `app_data/`, `.streamlit/config.toml` y `requirements.txt`. El punto de entrada es `app/streamlit_app.py` y el directorio de trabajo debe ser la raíz del proyecto.

Antes de publicar en un servicio externo:

1. Ejecuta la comprobación de las 27 tablas y las pruebas completas.
2. Confirma que el servicio admite el tamaño de `app_data/` y Python 3.13 con las versiones fijadas.
3. Incluye los Parquet preparados; la aplicación no descarga datos durante el arranque.
4. Decide si el callejero externo debe permanecer activado por defecto según la política de red del entorno.
5. Mantén visible que se trata de una demostración histórica, no de un servicio en tiempo real.

No hay credenciales, conexiones a bases de datos ni secretos necesarios para ejecutar esta versión.

## Relación con la Guía TFM Xabi

La aplicación materializa el apartado 10 de la guía y conecta los apartados 8 y 9: consulta de predicción por estación-hora, visualización espacial, interpretabilidad, errores y recomendaciones. La propuesta inicial de utilizar enero-febrero de 2023 como test se sustituyó por noviembre-diciembre de 2022 debido a la ausencia de estados de estaciones de 2023. Esta revisión evita inventar disponibilidad o etiquetas y conserva 2023 como análisis descriptivo de viajes.

La meteorología de 2022 se consulta como contexto histórico. No se ofrece un control para modificarla porque las predicciones y recomendaciones están congeladas y cambiar una variable aislada no produciría una predicción válida sin volver a ejecutar el flujo completo.
