#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extract_parser import process_all_extracts
from datetime import datetime


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Procesando extractos...")
    result = process_all_extracts()
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Resultado: {result}")
    print("Extractos procesados.")


if __name__ == "__main__":
    main()
