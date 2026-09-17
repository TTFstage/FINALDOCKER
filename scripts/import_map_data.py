import os

import pandas as pd

from app import create_app
from app.map.models import BicycleParking, Station, Toilet
from extensions import db


def import_csv_to_model(file_path, model_cls):
    """Legge un CSV con pandas e inserisce solo i record con ID non esistenti."""
    if not os.path.exists(file_path):
        print(f"File non trovato: {file_path}")
        return

    # Carica il CSV sostituendo i valori vuoti/NaN con None
    df = pd.read_csv(file_path)
    df = df.where(pd.notnull(df), None)

    # Ottieni tutti gli ID già presenti nel database per evitare query individuali
    existing_ids = {row[0] for row in db.session.query(model_cls.id).all()}

    # Filtra il DataFrame mantenendo solo le righe nuove
    df_new = df[~df['id'].isin(existing_ids)]

    if df_new.empty:
        print(f"Nessun nuovo record da importare per {model_cls.__name__}.")
        return

    # Converte il DataFrame in una lista di dizionari e crea gli oggetti ORM
    records = df_new.to_dict(orient='records')
    db.session.bulk_insert_mappings(model_cls, records)
    db.session.commit()
    print(f"Importati {len(records)} record per {model_cls.__name__}.")

def import_data():
    app = create_app()
    with app.app_context():
        db.create_all()

        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

        import_csv_to_model(os.path.join(base_dir, 'stations.csv'), Station)
        import_csv_to_model(os.path.join(base_dir, 'toilets.csv'), Toilet)
        import_csv_to_model(os.path.join(base_dir, 'bicycle_parkings.csv'), BicycleParking)

        print("Import completato con successo.")

if __name__ == "__main__":
    import_data()