import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from screener.qualitative import QualitativeAnalyzer
from screener.ingest import FMPClient
import yaml

config_file = 'settings_premium.yaml'
with open(config_file, 'r') as f:
    config = yaml.safe_load(f)

api_key = "qGDE52LhIJ9CQSyRwKpAzjLXeLP4Pwkt"
fmp = FMPClient(api_key, config)

# Create qualitative analyzer
qa = QualitativeAnalyzer(fmp, config)

# Test META geographic revenue
print("Testing META Revenue Geographic Analysis...")
result = qa._analyze_revenue_geographic('META')

if result:
    print("\nSUCCESS! Geographic revenue data extracted:")
    print(f"  Total Revenue: ${result['total_revenue']:,.0f}")
    print(f"  Risk Level: {result['risk_level']}")
    print(f"\n  Breakdown:")
    for item in result['breakdown']:
        print(f"    - {item['region']}: ${item['revenue']:,.0f} ({item['percentage']:.1f}%)")
    if result['risk_regions']:
        print(f"\n  Risk Regions: {result['risk_regions']}")
else:
    print("FAILED! No data returned")
