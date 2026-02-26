"""Fix indentation error in dashboard.py caused by the column-selector patch."""
with open('dashboard.py', 'r', encoding='utf-8') as f:
    lines = f.read().replace('\r\n', '\n').split('\n')

out = []
i = 0
while i < len(lines):
    line = lines[i]
    # Fix: bad over-indented 'visible = st.multiselect(' inside with tab_jobs
    if '            visible = st.multiselect(' in line:
        # Replace from this line through the closing paren
        out.append('    visible = st.multiselect(')
        i += 1
        while i < len(lines):
            l = lines[i]
            # these lines are also over-indented — fix them
            if l.startswith('            '):
                out.append('        ' + l[12:])
            elif l.strip() == ')':
                out.append('    )')
                i += 1
                break
            else:
                out.append(l)
            i += 1
        # eat the blank markdown close-div line
        if i < len(lines) and '</div>' in lines[i]:
            i += 1  # skip it
        continue
    # Remove the opening padding div inside tab_jobs
    if "st.markdown(\"<div style='padding:14px 24px 0;'>" in line:
        i += 1
        continue
    out.append(line)
    i += 1

with open('dashboard.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))

print(f"Done. Lines written: {len(out)}")
