import urllib.request
import re
import json

req = urllib.request.Request(
    'https://www.coches.net/search/', 
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)
try:
    with urllib.request.urlopen(req) as response:
        html = response.read().decode('utf-8')
        print("HTML length:", len(html))
        
        # Search for window.__NEXT_DATA__
        match = re.search(r'__NEXT_DATA__\s*=\s*(\{.*?\});</script>', html, re.DOTALL)
        if match:
             data = json.loads(match.group(1))
             with open('next_data.json', 'w', encoding='utf-8') as f:
                 json.dump(data, f, indent=2)
             print("next_data.json saved with length", len(match.group(1)))
        else:
             print("__NEXT_DATA__ not found")
except Exception as e:
    print("Error:", e)
