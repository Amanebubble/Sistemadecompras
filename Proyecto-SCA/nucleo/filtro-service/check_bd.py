import sqlite3

conn = sqlite3.connect("filtro_dte.db")
cursor = conn.execute("SELECT * FROM dte_procesados")
rows = cursor.fetchall()
print(f"Registros en BD: {len(rows)}")
print()
header = f"{'codigo_generacion':<40} {'nombre_cliente':<35} {'fecha_descarga':<12} {'fecha_registro'}"
print(header)
print("-" * len(header))
for row in rows:
    print(f"{row[0]:<40} {row[1]:<35} {row[2]:<12} {row[3]}")
conn.close()
