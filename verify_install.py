#!/usr/bin/env python3
"""
Quick verification script to check if all dependencies are installed correctly.
"""
import sys


def check_dependencies():
    """Check if all required packages are installed."""
    missing = []
    versions = {}

    # Core dependencies
    required = {
        'pandas': 'pd',
        'numpy': 'np',
        'requests': 'requests',
        'yaml': 'yaml',
        'scipy.stats': 'stats',
        'dotenv': 'dotenv'
    }

    print("Checking dependencies...\n")

    for module, alias in required.items():
        try:
            if '.' in module:
                # Handle submodules
                parts = module.split('.')
                imported = __import__(parts[0])
                for part in parts[1:]:
                    imported = getattr(imported, part)
            else:
                imported = __import__(module)

            version = getattr(imported, '__version__', 'unknown')
            versions[module] = version
            print(f"✓ {module:20} {version}")

        except ImportError as e:
            missing.append(module)
            print(f"✗ {module:20} MISSING")

    print(f"\nPython version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")

    if missing:
        print(f"\n❌ Missing dependencies: {', '.join(missing)}")
        print("\nInstall with:")
        print("  pip install -r requirements-core.txt")
        return False
    else:
        print("\n✅ All dependencies installed successfully!")
        return True


def check_unwanted_packages():
    """Check if any unwanted heavy packages are installed."""
    try:
        import pkg_resources
    except ImportError:
        print("\nNote: Cannot check for unwanted packages (pkg_resources not available)")
        return

    unwanted = ['streamlit', 'altair', 'pydeck', 'plotly', 'dash', 'bokeh']
    installed = {pkg.key for pkg in pkg_resources.working_set}

    found_unwanted = [pkg for pkg in unwanted if pkg in installed]

    if found_unwanted:
        print(f"\n⚠️  Warning: Found unnecessary packages: {', '.join(found_unwanted)}")
        print("These are NOT required by UltraQuality and may slow down imports.")
        print("\nTo clean up:")
        print(f"  pip uninstall {' '.join(found_unwanted)}")
    else:
        print("\n✓ No unwanted packages found")


def check_api_key():
    """Check if FMP API key is configured."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv('FMP_API_KEY')

    print("\nAPI Key Configuration:")
    if api_key and not api_key.startswith('your_'):
        print(f"✓ FMP_API_KEY is set ({api_key[:10]}...)")
        return True
    else:
        print("✗ FMP_API_KEY not configured")
        print("\nSet your API key:")
        print("  1. Copy .env.example to .env")
        print("  2. Edit .env and add your key")
        print("  3. Get a key at: https://financialmodelingprep.com")
        return False


def main():
    print("=" * 60)
    print("UltraQuality Installation Verification")
    print("=" * 60)
    print()

    deps_ok = check_dependencies()
    print()
    check_unwanted_packages()
    print()
    api_ok = check_api_key()

    print()
    print("=" * 60)

    if deps_ok and api_ok:
        print("✅ All checks passed! Ready to run screener.")
        print()
        print("Next steps:")
        print("  python run_screener.py")
        return 0
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
