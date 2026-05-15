# Data Quality Auditor

A web-based tool for auditing CSV datasets and identifying common data quality issues such as missing values, datatype mismatches, duplicates, and anomalies.

## Features

- CSV upload interface
- Automatic schema inference
- Data profiling
- Validation checks
- Anomaly detection
- Quality scoring
- Generated audit reports
- FastAPI backend with browser-based frontend

## Tech Stack

### Backend

- Python
- FastAPI
- Pandas
- NumPy
- Scikit-learn

### Frontend

- HTML
- CSS
- JavaScript

## Project Structure

```text
backend/
frontend/
requirements.txt
```

## Installation

Clone the repository:

```bash
git clone https://github.com/Rawatkhushi/Data-Auditor.git
cd Data-Auditor
```

Create virtual environment:

```bash
python -m venv venv
```

Activate virtual environment:

### macOS / Linux

```bash
source venv/bin/activate
```

### Windows

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the Application

```bash
uvicorn backend.main:app --reload
```

Open in browser:

```text
http://127.0.0.1:8000/ui/
```

## API Endpoints

### Health Check

```http
GET /health
```

### Run Audit

```http
POST /audit
```

### Stream Report

```http
POST /audit/report/stream
```

## Current Limitations

- Supports only CSV files
- No authentication
- Reports are template based
- Large datasets may take longer to process

## Author

Khushi Rawat

GitHub: [https://github.com/Rawatkhushi](https://github.com/Rawatkhushi)
