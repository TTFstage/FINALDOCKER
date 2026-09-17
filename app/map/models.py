from extensions import db


class Station(db.Model):
    """Water fountains and water dispensers (table 'stations' in Prisma)."""

    __tablename__ = "stations"

    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    name = db.Column(db.String, nullable=True)
    cap = db.Column(db.Integer, nullable=True)
    type = db.Column(db.String, nullable=False)  # "fountain" | "house"
    gh5 = db.Column(db.String, index=True, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "lat": self.lat,
            "lng": self.lng,
            "name": self.name,
            "cap": self.cap,
            "type": self.type,
            "gh5": self.gh5,
        }


class BicycleRepair(db.Model):
    __tablename__ = "bicycle_repair"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    opening_hours = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)
    gh5 = db.Column(db.String, index=True, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "lat": self.lat, "lng": self.lng,
                "opening_hours": self.opening_hours, "phone": self.phone, "gh5": self.gh5}


class Toilet(db.Model):
    __tablename__ = "toilets"

    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    fee = db.Column(db.Boolean, nullable=True)
    openingHours = db.Column(db.String, nullable=True)
    changingTable = db.Column(db.Boolean, nullable=True)
    gh5 = db.Column(db.String, index=True, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "lat": self.lat,
            "lng": self.lng,
            "fee": self.fee,
            "openingHours": self.openingHours,
            "changingTable": self.changingTable,
            "gh5": self.gh5,
        }


class BicycleParking(db.Model):
    __tablename__ = "bicycle_parkings"

    id = db.Column(db.Integer, primary_key=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    covered = db.Column(db.Boolean, nullable=True)
    indoor = db.Column(db.Boolean, nullable=True)
    access = db.Column(db.String, nullable=True)
    fee = db.Column(db.Boolean, nullable=True)
    bicycleParking = db.Column(db.String, nullable=True)
    surveillance = db.Column(db.Boolean, nullable=True)
    capacity = db.Column(db.Integer, nullable=True)
    gh5 = db.Column(db.String, index=True, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "lat": self.lat,
            "lng": self.lng,
            "covered": self.covered,
            "indoor": self.indoor,
            "access": self.access,
            "fee": self.fee,
            "bicycleParking": self.bicycleParking,
            "surveillance": self.surveillance,
            "capacity": self.capacity,
            "gh5": self.gh5,
        }

