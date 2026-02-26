"""
Hot-patch for Jobright testing to print EXACTLY why jobs are dropped.
"""

with open('job_discovery.py', 'r', encoding='utf-8') as f:
    code = f.read().replace('\r\n', '\n')

import re
old_js_start = '        print(f"    [Jobright DEBUG] Found {len(js_data)} raw cards via JS")'
new_js_start = '''        print(f"    [Jobright DEBUG] Found {len(js_data)} raw cards via JS")

        # Let's see the first extracted card raw data
        if js_data:
            print(f"    [Jobright DEBUG] Card 1 Sample:\\n      Title: {js_data[0].get('title')!r}\\n      Company: {js_data[0].get('company')!r}\\n      Loc: {js_data[0].get('location')!r}\\n      Date: {js_data[0].get('date')!r}")'''

if old_js_start in code:
    code = code.replace(old_js_start, new_js_start)

old_filter_block = '''                if not self._is_role_match(title):
                    continue
                if not self._is_us_location(loc):
                    continue'''

new_filter_block = '''                if not self._is_role_match(title):
                    print(f"      [Drop] Role Match Failed: {title!r}")
                    continue
                if not self._is_us_location(loc):
                    print(f"      [Drop] Loc Match Failed: {loc!r}")
                    continue
                print(f"      [Keep] MATCHED: {title!r} @ {company!r}")'''

if old_filter_block in code:
    code = code.replace(old_filter_block, new_filter_block)

old_empty_title = '''                if not title or len(title) < 3:
                    continue'''
new_empty_title = '''                if not title or len(title) < 3:
                    print(f"      [Drop] Empty Title: {title!r} (Inner Text snippet: {inner[:50]!r}...)")
                    continue'''

if old_empty_title in code:
    code = code.replace(old_empty_title, new_empty_title)

with open('job_discovery.py', 'w', encoding='utf-8') as f:
    f.write(code)
print("job_discovery.py patched with deep trace logging.")
