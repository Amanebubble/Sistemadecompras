import time
import traceback
import sys
import os
import threading
import sqlite3

# Asegurar que la raíz del proyecto está en el PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.auditoria import registrar_error
from src.conection_service.main import cargar_cuentas, cargar_settings, procesar_cuenta_con_reintentos
from src.filtro_service.enrutador import Enrutador
from src.conversor_pdf.extractor_pdf import procesar_cola as extraer_pdfs
from src.conversor_json.estandarizador import Estandarizador, _inicializar_bd
from src.generador_excel import GeneradorExcel
from src.config import RUTA_BD_CONTROL

_corriendo = True

def sleep_con_latido(segundos, nombre_hilo):
    """Espera activa que imprime latidos para demostrar que el hilo sigue vivo."""
    for i in range(segundos):
        if not _corriendo:
            break
        if i % 10 == 0 and i > 0:
            print(f"[{nombre_hilo}] ⏳ Escuchando en 2º plano ({i}s/{segundos}s)...")
        time.sleep(1)

def hilo_imap():
    settings = cargar_settings()
    while _corriendo:
        try:
            cuentas = cargar_cuentas()
            if cuentas:
                print(f"\n[Conexión] Escaneando {len(cuentas)} cuenta(s) configurada(s)...")
            else:
                print(f"\n[Conexión] No hay cuentas configuradas en accounts.json.")
                
            for config_cuenta in cuentas:
                nombre_cuenta = config_cuenta.get("nombre", config_cuenta.get("usuario", "desconocido"))
                print(f"  -> Revisando cuenta: {nombre_cuenta} ({config_cuenta.get('protocolo', 'Desconocido')})")
                try:
                    resultado = procesar_cuenta_con_reintentos(config_cuenta, settings)
                except Exception as e_cuenta:
                    print(f"[SEMAFORO:account_error] [Error - {nombre_cuenta}] Fallo de conexión: {e_cuenta}")
                    registrar_error("Motor Stream (Cuenta)", nombre_cuenta, str(e_cuenta))
                    continue
            sleep_con_latido(15, "Conector IMAP")
        except Exception as e:
            registrar_error("Hilo IMAP", "General", str(e))
            sleep_con_latido(15, "Conector IMAP")

def hilo_enrutador():
    while _corriendo:
        try:
            # Eliminado print con FASE
            enrutador = Enrutador()
            enrutador.ejecutar()
            sleep_con_latido(5, "Enrutador")
        except Exception as e:
            registrar_error("Hilo Enrutador", "General", str(e))
            sleep_con_latido(5, "Enrutador")

def hilo_pdf():
    while _corriendo:
        try:
            # Eliminado print con FASE
            extraer_pdfs()
            sleep_con_latido(5, "Conversor PDF")
        except Exception as e:
            registrar_error("Hilo PDF", "General", str(e))
            sleep_con_latido(5, "Conversor PDF")

def hilo_json():
    while _corriendo:
        try:
            # Eliminado print con FASE
            estandarizador = Estandarizador()
            estandarizador.conexion = _inicializar_bd(str(estandarizador.ruta_bd))
            estandarizador.procesar_cola()
            if estandarizador.conexion:
                estandarizador.conexion.close()
            sleep_con_latido(5, "JSON-a-SQL")
        except Exception as e:
            registrar_error("Hilo JSON", "General", str(e))
            sleep_con_latido(5, "JSON-a-SQL")

def hilo_reportes():
    """Genera versiones Beta constantemente (Cada 1 minuto)"""
    gen = GeneradorExcel()
    while _corriendo:
        try:
            if not os.path.exists(RUTA_BD_CONTROL):
                sleep_con_latido(30, "Generador Reportes")
                continue
                
            conn = sqlite3.connect(RUTA_BD_CONTROL)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='libro_compras'")
            if not cursor.fetchone():
                conn.close()
                sleep_con_latido(30, "Generador Reportes")
                continue
                
            print("[Reportes] Generando o actualizando Libro de Compras en Excel...")
            
            cursor.execute("SELECT DISTINCT cliente, ano, mes FROM libro_compras")
            combinaciones = cursor.fetchall()
            
            if combinaciones:
                for cliente, ano, mes in combinaciones:
                    gen.generar_reporte(cliente, ano, mes)
                
                cursor.execute("SELECT DISTINCT ano, mes FROM libro_compras")
                fechas_globales = cursor.fetchall()
                for ano, mes in fechas_globales:
                    gen.generar_reporte(None, ano, mes)
                    
            conn.close()
            sleep_con_latido(60, "Generador Reportes")
        except Exception as e:
            registrar_error("Hilo Reportes", "General", str(e))
            sleep_con_latido(60, "Generador Reportes")

def ejecutar_stream():
    print("=== Iniciando Motor Concurrente (Múltiples Hilos) ===")
    
    # Daemon=True permite que los hilos mueran solos si el hilo principal termina.
    hilos = [
        threading.Thread(target=hilo_imap, daemon=True),
        threading.Thread(target=hilo_enrutador, daemon=True),
        threading.Thread(target=hilo_pdf, daemon=True),
        threading.Thread(target=hilo_json, daemon=True)
    ]
    
    for h in hilos:
        h.start()
    
    # Hilo principal se queda escuchando para evitar cerrar el proceso, 
    # e imprime un pulso ocasional.
    global _corriendo
    try:
        while True:
            time.sleep(20)
            print("\n[SEMAFORO:active] Motor Concurrente ejecutándose... [Pulso 20s]")
    except KeyboardInterrupt:
        print("\n[SEMAFORO:stopped] Sistema detenido por el usuario.")
        _corriendo = False

if __name__ == "__main__":
    try:
        ejecutar_stream()
    except Exception as e:
        print(f"[SEMAFORO:critical] Fallo crítico de sistema: {e}")
        registrar_error("Motor Stream", "Sistema", traceback.format_exc())

