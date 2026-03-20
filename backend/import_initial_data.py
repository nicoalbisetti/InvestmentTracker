"""
Script para importar datos iniciales desde Inversiones.xlsx.
Ejecutar desde el directorio backend/ con:
    python import_initial_data.py [ruta_al_excel]
"""
import sys
import os

# Add parent directory to path so app module is found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import create_tables, SessionLocal
from app.services.importer import import_excel


def main():
    excel_path = sys.argv[1] if len(sys.argv) > 1 else "../Inversiones.xlsx"

    if not os.path.exists(excel_path):
        print(f"ERROR: Archivo no encontrado: {excel_path}")
        print("Uso: python import_initial_data.py [ruta_al_excel]")
        sys.exit(1)

    print(f"Creando tablas de base de datos...")
    create_tables()

    print(f"Importando datos desde: {excel_path}")
    db = SessionLocal()
    try:
        report = import_excel(excel_path, db)

        print("\n" + "="*60)
        print("RESULTADO DE IMPORTACION")
        print("="*60)
        print(f"  Instrumentos creados : {report['instruments']}")
        print(f"  Posiciones mensuales : {report['positions']}")
        print(f"  Snapshots portfolio  : {report['snapshots']}")
        print(f"  Resumen anual        : {report['annual']}")
        print(f"  Proventos            : {report['proventos']}")
        print(f"  Cotizaciones         : {report['quotes']}")
        print(f"  Ranking actualizado  : {report['ranking']}")

        if report['warnings']:
            print(f"\nWARNINGS ({len(report['warnings'])}):")
            for w in report['warnings'][:20]:
                print(f"  ⚠  {w}")
            if len(report['warnings']) > 20:
                print(f"  ... y {len(report['warnings']) - 20} warnings mas")

        if report['errors']:
            print(f"\nERRORS ({len(report['errors'])}):")
            for e in report['errors'][:20]:
                print(f"  ✗  {e}")
            if len(report['errors']) > 20:
                print(f"  ... y {len(report['errors']) - 20} errores mas")

        status = "EXITOSA" if not report['errors'] else "CON ERRORES"
        print(f"\nImportacion {status}")
        print("="*60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
