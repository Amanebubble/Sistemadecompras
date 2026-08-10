import sqlite3

conn = sqlite3.connect(r"c:\Users\Lenovo P52s\Desktop\github-personal\proyecto01\Sistemadecompras\Proyecto-SCA\data\bases_de_datos\correos_procesados.db")
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM correos_procesados")
total = c.fetchone()[0]
print(f"Total processed emails: {total}")

c.execute("SELECT message_id, COUNT(*) as c FROM correos_procesados GROUP BY message_id HAVING c > 1")
dups = c.fetchall()
print(f"Duplicate message_ids in DB: {len(dups)}")
for d in dups[:10]:
    print(d)

conn.close()
