# SNIES Bogotá Analytics MVP

This repository contains a minimal, cost‑efficient data engineering MVP for producing the **ratio of students per teacher** for higher education institutions (IES) in Bogotá using official SNIES data for the years **2022–2024**.  The project downloads the required datasets from the SNIES portal, validates them, transforms and loads them into PostgreSQL, and exposes an analytics‑ready mart that can be consumed by BI tools such as Tableau or PowerBI.

## Problem statement

The technical challenge requires calculating the student/teacher ratio for IES in Bogotá between 2022 and 2024.  Only six datasets are needed: **Docentes 2022–2024** and **Estudiantes Matriculados 2022–2024**.  These datasets are published on the official [SNIES Bases Consolidadas portal](https://snies.mineducacion.gov.co/portal/ESTADISTICAS/Bases-consolidadas/), which defines *Matriculados* as all enrolled students and *Docentes* as teaching staff.  The goal of this MVP is to automate the ingestion, validation, transformation and storage of these datasets while prioritising simplicity and cost.

## Scope

This MVP intentionally limits its scope in order to maximise cost efficiency and minimise operational overhead:

* Only the six required datasets (Docentes and Estudiantes Matriculados for 2022, 2023 and 2024) are consumed.
* Only institutions located in Bogotá (according to the SNIES metadata) are processed.
* The solution uses PostgreSQL as the analytical serving layer and avoids heavier orchestration frameworks.
* A dual validation strategy is implemented: discovery of dataset URLs from the SNIES portal, followed by technical validation of each downloaded file (existence, size, format, basic schema).
* Fallback URLs are configurable in `app/config/sources.yml` so that the pipeline can continue if the portal structure changes.

## High‑level architecture

The following diagram summarises the solution flow:

```
SNIES portal (Bases Consolidadas)    →    Downloader & Validator    →    Raw storage    →    Transformer    →    PostgreSQL (staging)    →    Analytics mart    →    BI/Reporting
```

1. **Downloader & Validator** – Scrapes the SNIES portal, discovers the required dataset URLs, downloads the Excel files, validates their integrity (HTTP status, file size, extension, ability to open as Excel) and caches them locally.
2. **Raw storage** – Stores the original downloaded files in `data/raw/`.
3. **Transformer** – Uses `pandas` and `openpyxl` to normalise column names, enforce schema, filter to the years 2022–2024 and the city of Bogotá, and prepare staging tables.
4. **Loader** – Loads the cleaned data into PostgreSQL staging tables, aggregates the student and teacher counts at the IES/year level and computes the student‑teacher ratio.
5. **Analytics mart** – Exposes the final result in the view `analytics.mart_student_teacher_ratio`, which can be consumed by BI tools.

This architecture deliberately avoids unnecessary complexity (no Spark, Airflow or distributed systems) to keep the MVP lightweight and inexpensive while fulfilling the challenge requirements.

## Technology stack

* **Python 3.11** – Main programming language.
* **pandas** – Data manipulation and transformation.
* **requests** & **BeautifulSoup** – Downloading and parsing SNIES portal pages.
* **openpyxl** – Reading Excel files.
* **psycopg2‑binary** – Loading data into PostgreSQL.
* **PostgreSQL 14** – Analytical database.
* **Docker Compose** – Reproducible local deployment.

## Quickstart

### Running with Docker Compose

1. Clone the repository and change into the project directory:

   ```bash
   git clone https://github.com/YOUR_USER/snies-bogota-analytics-mvp.git
   cd snies-bogota-analytics-mvp
   ```

2. Copy the example environment file and adjust variables if necessary:

   ```bash
   cp .env.example .env
   # Edit .env to set DRY_RUN_ONLY=false once validation succeeds
   ```

3. Build and run the containers:

   ```bash
   docker compose up --build
   ```

The pipeline will download and validate the required files, create the database schemas, load the data, compute the mart and then exit.  Logs are written to the `logs/` directory and a manifest of downloaded files is saved in `logs/manifest.json`.

### Running without Docker

If you prefer not to use Docker, you can run the pipeline directly on your machine.  You will need Python 3.11 and PostgreSQL available locally.

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Create a `.env` file (copy from `.env.example`) and set the connection variables for your local PostgreSQL instance.

3. Run the pipeline:

   ```bash
   python app/main.py
   ```

## Expected outputs

When the pipeline finishes successfully you should see:

* A table `staging.students` with normalised student data for Bogotá (2022–2024).
* A table `staging.teachers` with normalised teacher data for Bogotá (2022–2024).
* A table `analytics.fact_ies_year` aggregating counts by IES and year.
* A view `analytics.mart_student_teacher_ratio` with the student/teacher ratio for each IES and year.

You can query the final mart with:

```sql
SELECT * FROM analytics.mart_student_teacher_ratio ORDER BY ies_code, year;
```

## Engineering decisions

This project makes several deliberate choices to prioritise cost, simplicity and maintainability:

* **Narrow scope** – We limit the ingestion to six specific datasets and filter to the city of Bogotá and years 2022–2024.  This reduces processing time and storage requirements.
* **Dual validation** – Before processing each file we verify that it is actually published on the SNIES portal and then perform a technical validation (HTTP status, file size, Excel format, basic schema).  If a file fails either check, the pipeline stops or falls back to a user‑configured URL.
* **PostgreSQL** – Using a relational database keeps the solution easy to understand, cheap to run and compatible with BI tools.  For an MVP the overhead of distributed processing frameworks would be unjustified.
* **Configurable fallback** – A `sources.yml` file allows you to define fallback URLs in case the SNIES portal changes structure or certain links break.  This avoids manual code changes when only the URLs need updating.
* **Docker Compose** – We use Docker Compose for reproducible local deployment without the need for heavy infrastructure.  A single command builds the image, starts the database, runs the pipeline and cleans up.

## Repository structure

```text
snies-bogota-analytics-mvp/
├── app/                  # Python source code
│  ├── config/           # Configuration files (sources.yml, settings)
│  ├── extract/          # Downloading and validation logic
│  ├── transform/        # Data cleaning and normalisation
│  ├── load/             # Database loading logic
│  ├── utils/            # Shared helpers (logging, validation)
│  └── main.py           # Entry point coordinating the pipeline
├── sql/                  # SQL scripts to create schemas, tables and views
├── docs/                 # Additional documentation and diagrams
├── data/
│  ├── raw/              # Downloaded source files (not tracked in git)
│  └── processed/        # Intermediate processed files (not tracked in git)
├── logs/                 # Pipeline logs and manifest
├── tests/                # Unit and integration tests
├── docker-compose.yml    # Orchestration of the application and PostgreSQL
├── Dockerfile            # Builds the Python application image
├── requirements.txt      # Python dependencies
├── .env.example          # Example environment variables
├── .gitignore            # Git ignore patterns
├── LICENSE               # Project license
└── README.md             # This documentation
```

## Contributing

Contributions, issues and feature requests are welcome!  Feel free to fork the repository, open issues or submit pull requests.

## License

This project is licensed under the MIT License.  See the [LICENSE](LICENSE) file for details.
