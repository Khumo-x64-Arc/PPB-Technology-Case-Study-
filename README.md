# PPB-Technology-Case-Study-
As part of the Standard Bank Assessment centre candidate have to create a MVP (Minimum Viable Product) based on an Candidate Pack and data set. This repository contains my identified solution to a problem found in the candidate pack and dataset. In addition to to that a presentation has to be created and presented a day later. 

## Table of Contents 
1. Project Overview
2.  File Structure
3. Software Requirements and Dependencies
4. Installation Instructions 
5. How to Compile and Run
6. Deployment and Execution Instructions 
7. Screenshots of app working
8. Troubleshooting notes 
   
## 1. Project Overview 
**Problem Statement:** 
You are given a real-looking 30-day record of one customer's bank
transactions. Using it, you must: 
1. Find one meaningful money problem or opportunity this customer has —
something the data clearly shows.
2. Build a small, working digital solution that helps the customer understand
or manage their money better, and creates value for the bank (PPB — Personal
and Private Banking).
**Approach**

**Analysis** 
My key findings from the dataset are as follows 
 - The Dataset is clean as there are no missing values or incomplete fields. And by clean is that the attribute values do not have to be transformed or reinterpreted  Thus Data cleaning is no necessary.
 - Then transaction history indicates that the client has a budgeting problem (They had no debts at the beginning of the month after payday as the account balance was R42 000. At the the end of the month their cheque account went into overdraft of R2 200.
 - Each Account transaction belongs to a specific category.
 - The JSON and xlsx files are identical. This was confirmed through visual inspection and from one of the stakeholders (Mr Trevor Mavuhlele)
 - Dataset is small (less than 50 records)
 - Two transactions could be fraudulent based off the human analysis, they do not match the account owners behavior and purchasing history. These transaction will be flagged.
 - The customer could save a significant amount of money if they were to signup for a rewards program because their behavior indicates that they shop at only particular shops. For example Groceries are bought at Woolworths exclusively   
   
**Approach** 
- Create a Gamified budget manager app that has different savings tiers. It is supposed to encourage the customer to save and budget better whilst also reffering them to Standard Banks UCount rewards program.
- For example since Woolworths is a UCount rewards retailer the App will suggest how much they could save by signing up with UCount rewards by showing the saving calculations.
- The customer will reach a savings goal each month that will be displayed as achievement badges and UCount reedemable points.
- Due to time constraints the MVP will be a TKflinker and customTKinter Python GUI.
- The app is intended to be a consolidation of the Standard bank Budget Manager and UCount Rewards scheme.
- Potentially the app could suggest different account tiers and promote that to the customer. From the transaction dataset they have a Achieva account and banking fees (R120) but with the income they earn R45 000 they could qualify for a Prestige Banking Account or  Professional Banking Account. This recommendation will be rule based.   
**Dataset** 
## 2. File Structure 

```
BudgetQuest/
├── README.md
├── requirements.txt
├── main.py                        # Application entry point
├── data/
│   ├── transactions_30day.json    # Candidate pack dataset (JSON)
│   └── transactions_30day.xlsx    # Candidate pack dataset (Excel, identical contents)
├── assets/
│   ├── icons/                     # UI icons
│   ├── badges/                    # Achievement badge artwork
│   └── fonts/                     # Custom fonts used by the GUI
├── src/
│   ├── __init__.py
│   ├── data_loader.py             # Reads/validates the JSON and .xlsx datasets
│   ├── categoriser.py             # Maps transactions to spending categories
│   ├── fraud_flagging.py          # Applies the rule set behind the two flagged transactions
│   ├── savings_engine.py          # Computes monthly savings position and tier progress
│   ├── rewards_advisor.py         # UCount Rewards saving-potential calculations
│   ├── account_tier_recommender.py# Rule-based Prestige/Professional account suggestion
│   ├── gamification.py            # Badge and points logic
│   └── gui/
│       ├── __init__.py
│       ├── app.py                 # customtkinter root window and navigation
│       ├── dashboard_view.py      # Spending overview and balance trend
│       ├── savings_tier_view.py   # Savings tiers, badges, UCount points
│       ├── alerts_view.py         # Flagged/fraud-suspect transactions
│       └── account_upgrade_view.py# Account tier recommendation screen
├── tests/
│   └── test_data_loader.py        # Basic unit tests for dataset loading/parsing
└── docs/
    ├── presentation.pptx          # Assessment day presentation
    └── screenshots/               # Screenshots referenced in Section 7
```

## 3. Software Requirements and Dependencies 

The following table lists the runtime requirements of the project: 
| Software/Dependency | Minimum Version|  Development version | Relevance |
| -------- | -------- | -------- | 
| Python   | 3.1  |  3.1.2 | Programming language of the  

| Software/Dependency | Minimum Version | Development Version | Relevance |
| -------- | -------- | -------- | -------- |
| Python | 3.10 | 3.11.2 | Core programming language for the MVP |
| customtkinter | 5.2.0 | 5.2.2 | Modern themed widgets used for the gamified GUI (tiers, badges, progress bars) |
| Pillow | 10.0.0 | 10.2.0 | Image handling required by customtkinter (badge icons, illustrations) |
| pandas | 2.0.0 | 2.1.4 | Loading, aggregating, and category-grouping the transaction dataset |
| openpyxl | 3.1.0 | 3.1.2 | Reading the `.xlsx` version of the transaction dataset via pandas |
| matplotlib | 3.7.0 | 3.8.2 | Spending-by-category chart and the monthly savings/overdraft trend line |
| tkinter | Bundled with Python | Bundled with Python | Base GUI toolkit that customtkinter extends |

All dependencies are pinned in `requirements.txt` at the repository root.

---

## 4. Installation Instructions 
1. **Clone the repository**
   ```bash
   git clone https://github.com/<your-username>/PPB-Technology-Case-Study-.git
   cd PPB-Technology-Case-Study-
   ```
2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```
3. **Activate the virtual environment**
   - Windows (PowerShell):
     ```powershell
     venv\Scripts\Activate.ps1
     ```
   - macOS / Linux:
     ```bash
     source venv/bin/activate
     ```
4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
5. **Confirm the dataset files are present** under `data/` (`transactions_30day.json` and `transactions_30day.xlsx`). If they were provided separately as part of the candidate pack, copy them into `data/` before running the app.

---
## 5. How to Compile and Run 

Python is interpreted, not compiled, so there is no build step for everyday use — the app is launched directly from source.

**Run from source:**
```bash
python main.py
```
(use `python3` instead of `python` on macOS/Linux if both Python 2 and 3 are on the system PATH).

**Optional — package as a standalone executable** (useful so the presentation day demo doesn't depend on a Python installation being present on the presenting machine):
```bash
pip install pyinstaller
pyinstaller --onefile --windowed --add-data "assets:assets" --add-data "data:data" main.py
```
The packaged executable will be created under `dist/`. On Windows, replace the `:` in `--add-data` with `;`.

---
## 6. Deployment and Execution Instructions 

BudgetQuest is a **local, desktop-first MVP** — it has no server or cloud component, and all processing (dataset loading, fraud flagging, savings and rewards calculations) happens on-device using the local copies of the transaction files. There is nothing to deploy to a hosting environment for the purposes of this assessment.

For the assessment/presentation day itself:

1. Build and test the standalone executable (Section 5) ahead of time, on the same OS as the presentation machine where possible.
2. Run the packaged app once on a clean machine (or a fresh virtual environment) before the day, to confirm no dependency is missing.
3. Keep a fallback plan of running `python main.py` from source in case the packaged build is unavailable, with the virtual environment pre-activated.
4. Since the dataset is a synthetic case-study file rather than real customer data, no additional data-security or access-control steps were required for this MVP.

---
## 7. Screenshots of app working 

*(Replace the placeholders below with actual screenshots once captured — save them into `docs/screenshots/` using the same filenames.)*

| View | Screenshot |
| --- | --- |
| Dashboard — spending overview and balance trend | `docs/screenshots/dashboard.png` |
| Savings tiers, badges and UCount points | `docs/screenshots/savings_tiers.png` |
| UCount Rewards saving-potential suggestion | `docs/screenshots/rewards_advisor.png` |
| Flagged/suspicious transaction alert | `docs/screenshots/fraud_alert.png` |
| Account tier upgrade recommendation | `docs/screenshots/account_upgrade.png` |

```markdown
![Dashboard view](docs/screenshots/dashboard.png)
![Savings tiers and badges](docs/screenshots/savings_tiers.png)
![UCount Rewards suggestion](docs/screenshots/rewards_advisor.png)
![Flagged transaction alert](docs/screenshots/fraud_alert.png)
![Account tier upgrade recommendation](docs/screenshots/account_upgrade.png)
```

---


## 8. Troubleshooting notes 

- **`ModuleNotFoundError: No module named 'customtkinter'`** — the virtual environment isn't activated, or `pip install -r requirements.txt` wasn't run inside it. Re-activate the venv and reinstall.
- **UI looks blurry or tiny on Windows high-DPI displays** — Windows Tk scaling issue. Add DPI awareness near the top of `main.py`:
  ```python
  import ctypes
  try:
      ctypes.windll.shcore.SetProcessDpiAwareness(1)
  except Exception:
      pass
  ```
- **App won't launch on macOS / "Tkinter not found"** — the system Python that ships with macOS often has an outdated or missing Tk. Install Python via [python.org](https://www.python.org/downloads/) or Homebrew (`brew install python-tk`) rather than relying on the system interpreter.
- **`pandas.errors.ParserError` or blank data on load** — confirm `transactions_30day.xlsx`/`.json` are in `data/` and haven't been renamed; check the file opens correctly in Excel/a text editor first.
- **Badge icons or fonts not appearing** — asset paths are relative to `main.py`; if the app is launched from a different working directory, image loads can silently fail. Build asset paths using `os.path.join(os.path.dirname(__file__), ...)` rather than relative strings.
- **PowerShell blocks `venv\Scripts\Activate.ps1`** — this is Windows' execution policy. Run PowerShell as Administrator and execute:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
  ```
- **PyInstaller build runs but can't find the dataset or assets** — double-check the `--add-data` paths were included when building, and that any file-loading code uses `sys._MEIPASS` to resolve paths correctly when running from a frozen executable.


