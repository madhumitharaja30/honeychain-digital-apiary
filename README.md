# HoneyChain — VS Code Full-Stack Hackathon App

HoneyChain is a software-only honey traceability and smart beekeeping management system.

## Features
- Punitha Varshini beekeeper demo account
- Registration and login/logout
- SQLite database with automatic initialization
- Hive CRUD and simulated monitoring
- Honey batch creation and traceability
- Quality verification
- Processing timeline
- Real SHA-256 hash-chain blockchain ledger
- Blockchain integrity verification
- Dynamic QR codes
- Public batch verification page
- Traceability completeness score
- Notifications
- Analytics
- Admin dashboard
- Responsive honey/nature themed UI

## Requirements
- Python 3.10+
- VS Code
- Internet is NOT required after dependencies are installed.

## Run in VS Code

### Easiest Windows method
Double-click **`run.bat`**. It creates the virtual environment, installs the required packages, and starts the app.

### Manual Windows method
```powershell
cd HoneyChain_VSCode
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use Command Prompt:
```cmd
venv\Scripts\activate.bat
pip install -r requirements.txt
python app.py
```

Then open:
http://127.0.0.1:5000

## Demo Login
Email: punitha.varshini@honeychain.demo
Password: HoneyChain@2026

Admin demo:
Email: admin@honeychain.demo
Password: Admin@2026

Change demo passwords before public deployment.

Run `python check_project.py` to perform a quick local project/syntax check.

## Main demo flow
Login → Dashboard → Add Hive → Create Honey Batch → Quality → Processing → Blockchain → Verify Chain → Generate QR → Public Verification.

## Notes
The blockchain is a local SHA-256 hash-chain MVP. It demonstrates tamper-evident chaining without requiring Ethereum, cryptocurrency, or paid services.
The Traceability Score measures record completeness; it is NOT a scientific purity score.
Hive monitoring uses simulated data; no physical sensors are required.
