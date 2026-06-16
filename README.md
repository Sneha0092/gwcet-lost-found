# Track&Return — Airport Lost & Found Portal

A full-stack Lost & Found portal for airports with **AI-powered matching** using Claude.

## Tech Stack
- **Backend**: Python + Flask + SQLite
- **AI Matching**: Anthropic Claude API (claude-sonnet-4-6)
- **Frontend**: Vanilla HTML/CSS/JS (no framework needed)

## Setup

### 1. Install dependencies
```bash
pip install flask flask-cors
```

### 2. Set your Anthropic API key
```bash
export ANTHROPIC_API_KEY=your_key_here
```
Get your key from: https://console.anthropic.com

### 3. Run the server
```bash
python3 server.py
```

### 4. Open the portal
Visit: http://localhost:5050

---

## Features

### Traveler View
- Report a lost item (category, description, location, time, email)
- Click "Find matches with AI" — Claude reads all found items and scores them
- View matched items highlighted with % score and reasons
- Submit a claim with one click

### Staff View
- Log found items submitted by staff across all terminals
- Dashboard with live stats (lost reports, found items, matches, claims)
- Recent found items list

### API Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/report-lost | Submit a lost item report + trigger AI matching |
| GET | /api/found-items | List all available found items (filter by ?category=) |
| GET | /api/matches/:lost_id | Get AI match results for a report |
| POST | /api/log-found | Staff logs a found item |
| POST | /api/claim | Traveler submits a claim |
| GET | /api/stats | Dashboard statistics |

## Database
SQLite database at `db/lostfound.db` with 4 tables:
- `lost_reports` — traveler submissions
- `found_items` — staff-logged found items (pre-seeded with 7 sample items)
- `matches` — AI match results with scores and reasons
- `claims` — submitted claims

## How AI Matching Works
When a traveler submits a lost report, the server:
1. Fetches all available found items from the DB
2. Sends both to Claude with a structured prompt
3. Claude returns a JSON array of match scores (0-100) and reasons
4. Results are saved to the `matches` table and returned to the UI

## Project Structure
```
lost-found/
├── server.py          # Flask backend + AI matching
├── public/
│   └── index.html     # Frontend (Traveler + Staff views)
├── db/
│   └── lostfound.db   # SQLite database (auto-created)
└── README.md
```
