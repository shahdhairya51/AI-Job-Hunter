import sqlite3
try:
    conn = sqlite3.connect('applications.db')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM jobs')
    total = cur.fetchone()[0]
    cur.execute('SELECT source, COUNT(*) as c FROM jobs GROUP BY source ORDER BY c DESC')
    sources = cur.fetchall()
    cur.execute('SELECT a.status, COUNT(*) FROM applications a GROUP BY a.status')
    statuses = cur.fetchall()
    cur.execute("SELECT COUNT(*) FROM applications WHERE resume_pdf_path IS NOT NULL AND resume_pdf_path != ''")
    tailored = cur.fetchone()[0]
    print(f'TOTAL JOBS: {total}')
    print('BY SOURCE:')
    for r in sources:
        print(f'  {r[0]}: {r[1]}')
    print('BY STATUS:')
    for s in statuses:
        print(f'  {s[0]}: {s[1]}')
    print(f'TAILORED RESUMES: {tailored}')
    conn.close()
except Exception as e:
    print(f'ERROR: {e}')
