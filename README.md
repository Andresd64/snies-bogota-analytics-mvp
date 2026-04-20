# MVP de Analítica SNIES Bogotá

Este repositorio contiene un MVP mínimo y eficiente en costos de ingeniería de datos para producir la **relación de estudiantes por docente** para las instituciones de educación superior (IES) de Bogotá utilizando datos oficiales del SNIES para los años **2022–2024**. El proyecto descarga los conjuntos de datos requeridos desde el portal SNIES, los valida, los transforma y los carga en PostgreSQL, y expone un mart analítico listo para ser consumido por herramientas de BI como Tableau o PowerBI.

## Planteamiento del problema

El desafío técnico requiere calcular la relación estudiante/docente para las IES de Bogotá entre 2022 y 2024. Solo se necesitan seis conjuntos de datos: **Docentes 2022–2024** y **Estudiantes Matriculados 2022–2024**. Estos conjuntos de datos se publican en el portal oficial de [Bases Consolidadas del SNIES](https://snies.mineducacion.gov.co/portal/ESTADISTICAS/Bases-consolidadas/), que define *Matriculados* como todos los estudiantes inscritos y *Docentes* como el personal docente. El objetivo de este MVP es automatizar la ingestión, validación, transformación y almacenamiento de estos conjuntos de datos, priorizando la simplicidad y el costo.

## Alcance

Este MVP limita intencionalmente su alcance con el fin de maximizar la eficiencia en costos y minimizar la sobrecarga operativa:

* Solo se consumen los seis conjuntos de datos requeridos (Docentes y Estudiantes Matriculados para 2022, 2023 y 2024).
* Solo se procesan instituciones ubicadas en Bogotá (según la metadata del SNIES).
* La solución utiliza PostgreSQL como capa de servicio analítico y evita frameworks de orquestación más pesados.
* Se implementa una estrategia de validación dual: descubrimiento de las URL de los conjuntos de datos desde el portal SNIES, seguido de la validación técnica de cada archivo descargado (existencia, tamaño, formato, esquema básico).
* Las URL de respaldo se pueden configurar en `app/config/sources.yml` para que el pipeline pueda continuar si cambia la estructura del portal.

## Arquitectura de alto nivel

El siguiente diagrama resume el flujo de la solución:

```text
Portal SNIES (Bases Consolidadas)    →    Descargador y Validador    →    Almacenamiento raw    →    Transformador    →    PostgreSQL (staging)    →    Mart analítico    →    BI/Reportes
```

1. **Descargador y Validador** – Extrae el portal SNIES, descubre las URL de los conjuntos de datos requeridos, descarga los archivos de Excel, valida su integridad (estado HTTP, tamaño del archivo, extensión, capacidad de abrirse como Excel) y los almacena localmente en caché.
2. **Almacenamiento raw** – Almacena los archivos originales descargados en `data/raw/`.
3. **Transformador** – Usa `pandas` y `openpyxl` para normalizar nombres de columnas, aplicar el esquema, filtrar a los años 2022–2024 y a la ciudad de Bogotá, y preparar tablas de staging.
4. **Cargador** – Carga los datos limpios en tablas de staging en PostgreSQL, agrega los conteos de estudiantes y docentes a nivel de IES/año y calcula la relación estudiante-docente.
5. **Mart analítico** – Expone el resultado final en la vista `analytics.mart_student_teacher_ratio`, que puede ser consumida por herramientas de BI.

Esta arquitectura evita deliberadamente complejidad innecesaria (sin Spark, Airflow ni sistemas distribuidos) para mantener el MVP liviano y económico mientras cumple con los requisitos del desafío.

## Stack tecnológico

* **Python 3.11** – Lenguaje principal de programación.
* **pandas** – Manipulación y transformación de datos.
* **requests** & **BeautifulSoup** – Descarga y análisis de páginas del portal SNIES.
* **openpyxl** – Lectura de archivos Excel.
* **psycopg2-binary** – Carga de datos en PostgreSQL.
* **PostgreSQL 14** – Base de datos analítica.
* **Docker Compose** – Despliegue local reproducible.

## Inicio rápido

### Ejecución con Docker Compose

1. Clona el repositorio y entra al directorio del proyecto:

   ```bash
   git clone https://github.com/YOUR_USER/snies-bogota-analytics-mvp.git
   cd snies-bogota-analytics-mvp
   ```

2. Copia el archivo de entorno de ejemplo y ajusta las variables si es necesario:

   ```bash
   cp .env.example .env
   # Edita .env para establecer DRY_RUN_ONLY=false una vez la validación sea exitosa
   ```

3. Construye y ejecuta los contenedores:

   ```bash
   docker compose up --build
   ```

El pipeline descargará y validará los archivos requeridos, creará los esquemas de la base de datos, cargará los datos, calculará el mart y luego finalizará. Los logs se escriben en el directorio `logs/` y un manifiesto de los archivos descargados se guarda en `logs/manifest.json`.

### Ejecución sin Docker

Si prefieres no usar Docker, puedes ejecutar el pipeline directamente en tu máquina. Necesitarás Python 3.11 y PostgreSQL disponibles localmente.

1. Crea y activa un entorno virtual:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Crea un archivo `.env` (copiado desde `.env.example`) y configura las variables de conexión para tu instancia local de PostgreSQL.

3. Ejecuta el pipeline:

   ```bash
   python app/main.py
   ```

## Resultados esperados

Cuando el pipeline termine correctamente deberías ver:

* Una tabla `staging.students` con datos normalizados de estudiantes para Bogotá (2022–2024).
* Una tabla `staging.teachers` con datos normalizados de docentes para Bogotá (2022–2024).
* Una tabla `analytics.fact_ies_year` que agrega los conteos por IES y año.
* Una vista `analytics.mart_student_teacher_ratio` con la relación estudiante/docente para cada IES y año.

Puedes consultar el mart final con:

```sql
SELECT * FROM analytics.mart_student_teacher_ratio ORDER BY ies_code, year;
```

## Decisiones de ingeniería

Este proyecto toma varias decisiones deliberadas para priorizar costo, simplicidad y mantenibilidad:

* **Alcance acotado** – Limitamos la ingestión a seis conjuntos de datos específicos y filtramos por la ciudad de Bogotá y los años 2022–2024. Esto reduce el tiempo de procesamiento y los requisitos de almacenamiento.
* **Validación dual** – Antes de procesar cada archivo verificamos que realmente esté publicado en el portal SNIES y luego realizamos una validación técnica (estado HTTP, tamaño del archivo, formato Excel, esquema básico). Si un archivo falla cualquiera de las dos verificaciones, el pipeline se detiene o recurre a una URL configurada por el usuario.
* **PostgreSQL** – Usar una base de datos relacional mantiene la solución fácil de entender, barata de ejecutar y compatible con herramientas de BI. Para un MVP, la sobrecarga de frameworks de procesamiento distribuido sería injustificada.
* **Respaldo configurable** – Un archivo `sources.yml` permite definir URL de respaldo en caso de que el portal SNIES cambie de estructura o ciertos enlaces fallen. Esto evita cambios manuales en el código cuando solo es necesario actualizar las URL.
* **Docker Compose** – Usamos Docker Compose para un despliegue local reproducible sin necesidad de infraestructura pesada. Un solo comando construye la imagen, inicia la base de datos, ejecuta el pipeline y limpia el entorno.

## Estructura del repositorio

```text
snies-bogota-analytics-mvp/
├── app/                  # Código fuente en Python
│  ├── config/            # Archivos de configuración (sources.yml, settings)
│  ├── extract/           # Lógica de descarga y validación
│  ├── transform/         # Limpieza y normalización de datos
│  ├── load/              # Lógica de carga a la base de datos
│  ├── utils/             # Utilidades compartidas (logging, validación)
│  └── main.py            # Punto de entrada que coordina el pipeline
├── sql/                  # Scripts SQL para crear esquemas, tablas y vistas
├── docs/                 # Documentación adicional y diagramas
├── data/
│  ├── raw/               # Archivos fuente descargados (no versionados en git)
│  └── processed/         # Archivos procesados intermedios (no versionados en git)
├── logs/                 # Logs del pipeline y manifiesto
├── tests/                # Pruebas unitarias y de integración
├── docker-compose.yml    # Orquestación de la aplicación y PostgreSQL
├── Dockerfile            # Construye la imagen de la aplicación Python
├── requirements.txt      # Dependencias de Python
├── .env.example          # Variables de entorno de ejemplo
├── .gitignore            # Patrones ignorados por git
├── LICENSE               # Licencia del proyecto
└── README.md             # Esta documentación
```

## Contribuciones

Las contribuciones, los issues y las solicitudes de nuevas funcionalidades son bienvenidas. No dudes en hacer fork del repositorio, abrir issues o enviar pull requests.

## Licencia

Este proyecto está licenciado bajo la licencia MIT. Consulta el archivo [LICENSE](LICENSE) para más detalles.
