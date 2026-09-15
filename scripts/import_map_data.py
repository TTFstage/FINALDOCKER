import os
import sqlite3
import sys

from app import create_app
from app.map.models import BicycleParking, Playground, Station, Toilet
from extensions import db

def import_data():
    app = create_app()
    with app.app_context():
        # Crea le tabelle in postgres se non esistono
        db.create_all()
        
        sqlite_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'MAP', 'data', 'fontanelle.db')
        if not os.path.exists(sqlite_db_path):
            print(f"SQLite DB non trovato: {sqlite_db_path}")
            return
            
        print(f"Lettura da {sqlite_db_path}...")
        conn = sqlite3.connect(sqlite_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Import stations
        print("Importing stations...")
        cursor.execute("SELECT id, lat, lng, name, cap, type, gh5 FROM stations")
        stations = cursor.fetchall()
        for row in stations:
            if not Station.query.get(row['id']):
                s = Station(id=row['id'], lat=row['lat'], lng=row['lng'], name=row['name'], cap=row['cap'], type=row['type'], gh5=row['gh5'])
                db.session.add(s)
        db.session.commit()
        print(f"Imported {len(stations)} stations.")
        
        # Import toilets
        print("Importing toilets...")
        cursor.execute("SELECT id, lat, lng, fee, openingHours, changingTable, gh5 FROM toilets")
        toilets = cursor.fetchall()
        for row in toilets:
            if not Toilet.query.get(row['id']):
                t = Toilet(id=row['id'], lat=row['lat'], lng=row['lng'], fee=bool(row['fee']), openingHours=row['openingHours'], changingTable=bool(row['changingTable']), gh5=row['gh5'])
                db.session.add(t)
        db.session.commit()
        print(f"Imported {len(toilets)} toilets.")
        
        # Import bicycle_parkings
        print("Importing bicycle parkings...")
        cursor.execute("SELECT id, lat, lng, covered, indoor, access, fee, bicycleParking, surveillance, capacity, gh5 FROM bicycle_parkings")
        bps = cursor.fetchall()
        for row in bps:
            if not BicycleParking.query.get(row['id']):
                b = BicycleParking(id=row['id'], lat=row['lat'], lng=row['lng'], covered=bool(row['covered']), indoor=bool(row['indoor']), access=row['access'], fee=bool(row['fee']), bicycleParking=row['bicycleParking'], surveillance=bool(row['surveillance']), capacity=row['capacity'], gh5=row['gh5'])
                db.session.add(b)
        db.session.commit()
        print(f"Imported {len(bps)} bicycle parkings.")
        
        # Import playgrounds
        print("Importing playgrounds...")
        cursor.execute("SELECT id, lat, lng, name, openingHours, indoor, fee, supervised, gh5 FROM playgrounds")
        playgrounds = cursor.fetchall()
        for row in playgrounds:
            if not Playground.query.get(row['id']):
                p = Playground(id=row['id'], lat=row['lat'], lng=row['lng'], name=row['name'], openingHours=row['openingHours'], indoor=bool(row['indoor']), fee=bool(row['fee']), supervised=bool(row['supervised']), gh5=row['gh5'])
                db.session.add(p)
        db.session.commit()
        print(f"Imported {len(playgrounds)} playgrounds.")
        
        conn.close()
        print("Import completato con successo.")

if __name__ == "__main__":
    import_data()
