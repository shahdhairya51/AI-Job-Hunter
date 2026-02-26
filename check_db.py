import sqlite3

def check():
    conn = sqlite3.connect('job_hunter.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, title, company, url FROM jobs WHERE source='LinkedIn' ORDER BY id DESC LIMIT 20")
    rows = c.fetchall()
    
    with open('latest_jobs.txt', 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(f"Company: {r['company']}\nURL: {r['url']}\nTitle: {r['title']}\n\n")
    conn.close()

if __name__ == '__main__':
    check()
