#!/usr/bin/env python3
"""
Complete diagnostic and cleanup script for premium features.
Run this before starting Streamlit to ensure latest code is used.
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path

print("="*80)
print("🔍 PREMIUM FEATURES - COMPLETE DIAGNOSTIC & CLEANUP")
print("="*80)

# Step 1: Verify we're in the right directory
print("\n📁 Step 1: Verify Working Directory")
cwd = Path.cwd()
print(f"Current directory: {cwd}")

required_files = ['run_screener.py', 'settings_premium.yaml', 'src/screener/ingest.py']
missing = []
for f in required_files:
    if not Path(f).exists():
        missing.append(f)
        print(f"  ❌ Missing: {f}")
    else:
        print(f"  ✅ Found: {f}")

if missing:
    print(f"\n❌ ERROR: Missing required files. Are you in the UltraQuality directory?")
    print(f"Run: cd /home/user/UltraQuality")
    sys.exit(1)

# Step 2: Clean ALL Python bytecode
print("\n🧹 Step 2: Cleaning Python Bytecode")
cleaned = 0

# Remove __pycache__ directories
for pycache in Path('.').rglob('__pycache__'):
    shutil.rmtree(pycache, ignore_errors=True)
    cleaned += 1
    print(f"  ✓ Removed: {pycache}")

# Remove .pyc files
for pyc in Path('.').rglob('*.pyc'):
    pyc.unlink()
    cleaned += 1
    print(f"  ✓ Removed: {pyc}")

print(f"✅ Cleaned {cleaned} cached files")

# Step 3: Clean Streamlit cache
print("\n🧹 Step 3: Cleaning Streamlit Cache")
st_cache_dirs = ['.streamlit/cache', '.streamlit']
for cache_dir in st_cache_dirs:
    cache_path = Path(cache_dir)
    if cache_path.exists():
        try:
            if cache_path.is_dir():
                shutil.rmtree(cache_path / 'cache', ignore_errors=True)
                print(f"  ✓ Cleaned: {cache_path}/cache")
        except Exception as e:
            print(f"  ⚠️  Could not clean {cache_path}: {e}")

# Step 4: Verify code changes are in files
print("\n🔍 Step 4: Verify Latest Code is in Files")

# Check if get_earnings_call_transcript has 'limit' parameter
with open('src/screener/ingest.py', 'r') as f:
    ingest_content = f.read()
    if 'limit: Optional[int] = 4' in ingest_content:
        print("  ✅ ingest.py has fixed get_earnings_call_transcript method")
    else:
        print("  ❌ ingest.py MISSING fix for get_earnings_call_transcript")

# Check if run_screener.py has os_module fix
with open('run_screener.py', 'r') as f:
    screener_content = f.read()
    if 'import os as os_module' in screener_content:
        print("  ✅ run_screener.py has os_module fix")
    else:
        print("  ❌ run_screener.py MISSING os_module fix")

# Step 5: Verify settings_premium.yaml config
print("\n🔍 Step 5: Verify Premium Config")
import yaml

try:
    with open('settings_premium.yaml', 'r') as f:
        config = yaml.safe_load(f)

    premium = config.get('premium', {})
    insider = premium.get('enable_insider_trading', False)
    transcripts = premium.get('enable_earnings_transcripts', False)

    print(f"  Premium config:")
    if insider:
        print(f"    ✅ Insider Trading: ENABLED")
    else:
        print(f"    ❌ Insider Trading: DISABLED")

    if transcripts:
        print(f"    ✅ Earnings Transcripts: ENABLED")
    else:
        print(f"    ❌ Earnings Transcripts: DISABLED")

    # Check cache settings
    cache = config.get('cache', {})
    print(f"  Cache TTL:")
    print(f"    - Universe: {cache.get('ttl_universe_hours', 12)}h")
    print(f"    - Symbol: {cache.get('ttl_symbol_hours', 48)}h")
    print(f"    - Qualitative: {cache.get('ttl_qualitative_hours', 24)}h")

except Exception as e:
    print(f"  ❌ Error loading settings_premium.yaml: {e}")

# Step 6: Test importing modules fresh
print("\n🔍 Step 6: Test Fresh Import of Modules")
try:
    # Remove from sys.modules if already loaded
    modules_to_clear = []
    for mod in list(sys.modules.keys()):
        if 'screener' in mod:
            modules_to_clear.append(mod)

    for mod in modules_to_clear:
        del sys.modules[mod]

    print(f"  ✓ Cleared {len(modules_to_clear)} modules from sys.modules")

    # Fresh import
    sys.path.insert(0, 'src/screener')
    from ingest import FMPClient
    import inspect

    sig = inspect.signature(FMPClient.get_earnings_call_transcript)
    params = list(sig.parameters.keys())

    print(f"  ✓ Imported FMPClient")
    print(f"  Method signature: {sig}")

    if 'limit' in params:
        print(f"  ✅ Method HAS 'limit' parameter - FIXED!")
    else:
        print(f"  ❌ Method MISSING 'limit' parameter - NOT FIXED!")

except Exception as e:
    print(f"  ❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

# Step 7: Kill any running Streamlit processes
print("\n🔄 Step 7: Kill Running Streamlit Processes")
try:
    result = subprocess.run(['pkill', '-f', 'streamlit'], capture_output=True)
    if result.returncode == 0:
        print("  ✓ Stopped Streamlit processes")
    else:
        print("  ℹ️  No Streamlit processes running")
except Exception as e:
    print(f"  ⚠️  Could not kill processes: {e}")

# Final Summary
print("\n" + "="*80)
print("✅ CLEANUP COMPLETE")
print("="*80)
print("\n📋 Next Steps:")
print("\n1. Start Streamlit with:")
print("   python run_screener.py")
print("\n2. OR if you prefer streamlit command:")
print("   streamlit run run_screener.py")
print("\n3. When running analysis:")
print("   - First click '🔄 Clear Cache & Reload Modules'")
print("   - Then click '🔍 Run Deep Analysis'")
print("\n4. Check the Debug panel to verify premium features work")
print("="*80)
