# Q-GPT Login Test Automation

A UI test automation framework for the Q-GPT login flow, built with
[Playwright](https://playwright.dev/python/) and `pytest` using the
Page Object Model.

## Features

- Page Object Model (`pages/`)
- JSON-based configuration (`config/config.json`)
- JSON-based test data (`data/input_data.json`)
- Excel data utility (`utils/excel_reader.py`)
- Self-contained HTML reports (`reports/report.html`)
- Automatic screenshot on test failure (`screenshots/`)
- Logger utility (`utils/logger.py`)
- Cross-browser support (Chromium / Firefox / WebKit)

## Project Structure

```
Qgpt/
├── config/          # config.json (base_url, browser, headless)
├── data/            # input_data.json (test data)
├── pages/           # Page Objects (base_page, login_page, home_page)
├── tests/           # Test cases + conftest.py fixtures
├── utils/           # Helpers (common, excel_reader, logger)
├── reports/         # Generated HTML reports
├── screenshots/     # Failure screenshots
├── logs/            # Log output
├── requirements.txt # Python dependencies
└── pytest.ini       # pytest configuration
```

## Installation

```bash
pip install -r requirements.txt
playwright install
```

## Configuration

Edit `config/config.json` to control the run:

```json
{
  "base_url": "https://qgpt.indorama.com/auth/login?...",
  "browser": "chromium",
  "headless": false
}
```

- `browser` — `chromium`, `firefox`, or `webkit`
- `headless` — `true` to run without a visible browser window

Test credentials live in `data/input_data.json`.

## Run Tests

```bash
# Run the full suite
pytest

# Run a single test
pytest tests/test_login.py::test_valid_login

# Run in parallel (pytest-xdist)
pytest -n auto
```

An HTML report is written to `reports/report.html` after each run, and a
screenshot of any failing test is saved to `screenshots/`.
