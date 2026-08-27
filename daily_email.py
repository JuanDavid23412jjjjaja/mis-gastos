#!/usr/bin/env python3
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reports import send_daily_report
from datetime import datetime


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando reporte diario...")
    for attempt in range(3):
        try:
            result = send_daily_report("juandroide7@gmail.com")
            if result:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Reporte enviado exitosamente.")
                return
            else:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error al enviar reporte.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Intento {attempt+1}/3 - Error: {e}")
            if attempt < 2:
                time.sleep(30)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Todos los intentos fallaron.")
    sys.exit(1)


if __name__ == "__main__":
    main()
