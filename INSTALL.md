# Installation Guide

## Quick Start (Production)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install core dependencies only (fastest)
pip install -r requirements-core.txt

# 3. Configure API key
cp .env.example .env
nano .env  # Add your FMP_API_KEY

# 4. Run screener
python run_screener.py
```

## Installation Options

### Option 1: Core Dependencies Only (Recommended for Production)

**Fastest installation** - Only essential libraries:

```bash
pip install -r requirements-core.txt
```

**Packages installed** (6 total):
- pandas: Data manipulation
- numpy: Numerical operations
- requests: HTTP client
- pyyaml: Configuration
- scipy: Statistics (z-scores)
- python-dotenv: Environment variables

**Install time**: ~30-60 seconds

---

### Option 2: With Testing (For Development)

```bash
pip install -r requirements-dev.txt
```

**Additional packages**:
- pytest: Unit testing
- pytest-cov: Coverage reports
- black: Code formatting
- flake8: Linting
- mypy: Type checking

**Install time**: ~2-3 minutes

---

### Option 3: Standard Install (Default)

```bash
pip install -r requirements.txt
```

Uses same packages as requirements-core.txt but without testing tools.

---

## Using uv (Fast Alternative)

If you have `uv` installed:

```bash
# Faster installation
uv pip install -r requirements-core.txt
```

---

## Troubleshooting

### Problem: Slow Installation / Too Many Packages

**Symptom**: Installing streamlit, altair, pydeck, etc. (NOT needed!)

**Cause**: Wrong requirements file or cached dependencies

**Solution**:
```bash
# 1. Create fresh virtual environment
deactivate  # If in a venv
rm -rf venv
python -m venv venv
source venv/bin/activate

# 2. Install ONLY core requirements
pip install --no-cache-dir -r requirements-core.txt

# 3. Verify installed packages
pip list
```

**Expected output** (should only have ~15 packages total):
```
Package         Version
--------------- --------
numpy           1.26.4
pandas          2.2.1
python-dateutil 2.9.0
python-dotenv   1.0.1
pytz            2024.1
PyYAML          6.0.1
requests        2.31.0
scipy           1.13.0
six             1.16.0
urllib3         2.2.1
...
```

**NOT expected**: streamlit, altair, pydeck, pillow, protobuf, etc.

---

### Problem: Missing API Key

```bash
# Check if key is set
echo $FMP_API_KEY

# If empty, set it:
export FMP_API_KEY="your_key_here"

# Or edit .env file
nano .env
```

---

### Problem: Import Errors

```bash
# Ensure you're in virtual environment
which python  # Should show venv/bin/python

# If not:
source venv/bin/activate

# Reinstall if needed
pip install --force-reinstall -r requirements-core.txt
```

---

## Minimal Installation (No Virtual Environment)

If you just want to test quickly:

```bash
# Install globally (not recommended)
pip install pandas numpy requests pyyaml scipy python-dotenv

# Run
export FMP_API_KEY="your_key"
python run_screener.py
```

---

## Docker Installation (Coming Soon)

```bash
# Build image
docker build -t ultraquality .

# Run screener
docker run -e FMP_API_KEY=$FMP_API_KEY ultraquality
```

---

## System Requirements

- **Python**: 3.9 or higher (tested on 3.9, 3.10, 3.11, 3.12, 3.13)
- **RAM**: 1GB minimum (2GB recommended)
- **Disk**: 500MB for cache
- **OS**: Linux, macOS, Windows (WSL recommended on Windows)

---

## Verifying Installation

Run this to verify everything is installed correctly:

```python
python -c "
import sys
import pandas as pd
import numpy as np
import requests
import yaml
from scipy import stats
from dotenv import load_dotenv

print(f'✓ Python {sys.version_info.major}.{sys.version_info.minor}')
print(f'✓ pandas {pd.__version__}')
print(f'✓ numpy {np.__version__}')
print(f'✓ requests {requests.__version__}')
print(f'✓ scipy {stats.__version__}')
print('✓ All dependencies installed successfully!')
"
```

Expected output:
```
✓ Python 3.11
✓ pandas 2.2.1
✓ numpy 1.26.4
✓ requests 2.31.0
✓ scipy 1.13.0
✓ All dependencies installed successfully!
```

---

## Uninstalling

```bash
# Remove virtual environment
deactivate
rm -rf venv

# Or uninstall packages
pip uninstall -r requirements-core.txt -y
```

---

## Next Steps

After installation:

1. **Configure API key**: `cp .env.example .env && nano .env`
2. **Test connection**: `python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key:', os.getenv('FMP_API_KEY')[:10] + '...')"`
3. **Run screener**: `python run_screener.py`
4. **View results**: `cat data/screener_results.csv | head -20`

See [README.md](README.md) for usage instructions.
