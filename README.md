# Consultorio3 — Medical Practice Management System

A full-stack web application to manage patients, clinical records and medical studies for a private medical practice. Built end-to-end as a personal project in 2025.

## Tech Stack

- **Backend:** Python 3 · Flask 3
- **Database:** PostgreSQL (psycopg2)
- **Templates:** Jinja2
- **PDF generation:** ReportLab
- **Security:** Werkzeug — password hashing, secure file uploads
- **Frontend:** HTML, CSS

## Features

- Secure user authentication with hashed passwords and per-request DB connections following Flask best practices
- CRUD for patients (create, view, edit, search)
- Clinical records (fichas) — full edit history, separate from the patient profile
- Medical study uploads — PDFs are stored under `uploads/estudios/` with secure UUID filenames
- Clinical history exporter — generates a downloadable PDF with the full patient history using ReportLab
- Search engine across patient records
- Login / session management with `flask.session`

## Project structure

```
.
├── App.py              # Flask app, routes and business logic (~1,000 lines)
├── db.py               # Database connection, schema bootstrap (~140 lines)
├── requirements.txt    # Flask, psycopg2-binary, reportlab
├── templates/          # 9 Jinja2 templates
│   ├── base.html
│   ├── login.html
│   ├── index.html
│   ├── buscar.html
│   ├── nuevo_paciente.html
│   ├── editar_paciente.html
│   ├── ficha.html
│   ├── editar_ficha.html
│   └── export_historial.html
└── uploads/
    └── estudios/       # PDF medical studies (gitignored in production)
```

## Running locally

```bash
# 1. Clone and enter the project
git clone https://github.com/<your-username>/Consultorio3.git
cd Consultorio3

# 2. Set up a virtualenv
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your PostgreSQL connection
# Set the env var DATABASE_URL or edit db.py
export DATABASE_URL="postgresql://user:password@localhost:5432/consultorio3"
export FLASK_SECRET_KEY="your-random-secret-here"

# 5. Run
python3 App.py
# Open http://localhost:5000
```

The schema is bootstrapped automatically on first run via `ensure_schema()`.

## What I learned building this

- Designing a relational schema for a real-world domain (patients, clinical records, file attachments)
- Handling secure file uploads with collision-safe UUID filenames
- Generating PDFs programmatically from database content using ReportLab
- Per-request DB connection lifecycle (`g`, `teardown_appcontext`)
- Authentication flow with hashed passwords (no plain text storage)

## Author

Valentín Santamaría — final-year Software Development student, based in Dublin.
[LinkedIn](https://www.linkedin.com/in/valentin-santamaria-dev)
