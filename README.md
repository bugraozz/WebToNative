# Web to Native Converter

This system accepts a web project (zip or git) and produces a React Native starter output plus a conversion report.

## Requirements
- Python 3.10+
- Node.js 18+
- Git (required for repo URL input)

## Backend
1. Create and activate a virtual environment.
2. Install dependencies:
	- pip install -r requirements.txt
3. Start the API:
	- uvicorn app.main:app --reload

## Frontend
1. Install dependencies:
	- npm install
2. Run:
	- npm run dev

## Usage
1. Upload a zip or provide a repo URL.
2. Review detected stacks and override if needed.
3. Convert to generate the report and output zip.

## Notes
- Conversion is heuristic and requires manual follow-up.
- Output artifacts are saved under backend/.data/jobs.
