import os
from pathlib import Path

def purgar_directorio(directorio):
    path = Path(directorio)
    if not path.exists():
        print(f"[-] Omitiendo {directorio} (No existe)")
        return
        
    borrados = 0
    # Recorrer todos los archivos en el directorio (sin importar la profundidad)
    for p in path.rglob("*"):
        if p.is_file() and p.suffix.lower() in [".pdf", ".json", ".xlsx", ".csv"]:
            # Proteger archivos de configuración como settings.json o .json de auth
            if p.name in ["settings.json", "accounts.json", "plantilla_dte.json"] or p.name.startswith("client_secret") or p.name.startswith("token_"):
                continue
            
            try:
                p.unlink()
                borrados += 1
            except Exception as e:
                print(f"[!] Error al borrar {p.name}: {e}")
                
    print(f"[+] Limpiados {borrados} archivos de prueba en {directorio}")

def main():
    print("=== Iniciando Purga de Datos de Prueba ===")
    
    base_dir = Path(__file__).resolve().parent
    nucleo_dir = base_dir / "nucleo"
    
    carpetas_a_limpiar = [
        base_dir / "Descarga-doc",
        base_dir / "mineria-finalizada",
        nucleo_dir / "filtro_service" / "cola0",
        nucleo_dir / "filtro_service" / "cola1",
        nucleo_dir / "Procesados",
        nucleo_dir / "Respaldo_PDF",
        nucleo_dir / "Revision_Manual",
        nucleo_dir / "Otros_Documentos",
        nucleo_dir / "Invalidos",
        nucleo_dir / "Duplicados",
        nucleo_dir / "Historico_Procesados"
    ]
    
    for carpeta in carpetas_a_limpiar:
        purgar_directorio(carpeta)
        
    # Limpiar base de datos SQLite si existe
    db_path = nucleo_dir / "filtro_service" / "filtro_dte.db"
    if db_path.exists():
        try:
            db_path.unlink()
            print(f"[+] Base de datos SQLite {db_path.name} reseteada")
        except Exception as e:
            print(f"[!] Error al borrar {db_path.name}: {e}")

    # Limpiar logs
    log_path = nucleo_dir / "conection_service" / "log.csv"
    if log_path.exists():
        try:
            log_path.unlink()
            print(f"[+] Log {log_path.name} limpiado")
        except Exception as e:
            pass
            
    print("\n=== Purga Completada Exitosamente ===")
    print("Tu proyecto está listo para producción.")

if __name__ == "__main__":
    main()
