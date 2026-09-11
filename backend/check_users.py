import pymysql

conn = pymysql.connect(host='localhost', user='parkease_app', password='Sahil#1505', database='parkease')
cur = conn.cursor()
cur.execute('SELECT id, name, email, phone, created_at FROM users')
rows = cur.fetchall()
cols = [d[0] for d in cur.description]

print(f"\n{'='*80}")
print("REGISTERED USERS")
print(f"{'='*80}")
for row in rows:
    print(f"\n  ID:      {row[0]}")
    print(f"  Name:    {row[1]}")
    print(f"  Email:   {row[2]}")
    print(f"  Phone:   {row[3]}")
    print(f"  Created: {row[4]}")
    print(f"  {'-'*40}")

print(f"\nTotal: {len(rows)} user(s)\n")
conn.close()
