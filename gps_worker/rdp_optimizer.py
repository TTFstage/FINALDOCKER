import math


def distanza_perpendicolare(punto, p1, p2):
    """Calcola la distanza perpendicolare di un punto (lat, lon) dalla retta p1-p2."""
    lat, lon = punto[0], punto[1]
    lat1, lon1 = p1[0], p1[1]
    lat2, lon2 = p2[0], p2[1]

    if lat1 == lat2 and lon1 == lon2:
        return math.hypot(lat - lat1, lon - lon1)

    # Conversione approssimata per coordinate geografiche a corte distanze
    dx = lat2 - lat1
    dy = lon2 - lon1
    num = abs(dy * lat - dx * lon + lat2 * lon1 - lon2 * lat1)
    den = math.hypot(dx, dy)
    return num / den


def ramer_douglas_peucker(punti, epsilon=0.00005):
    """Semplifica una lista di punti (lat, lon, elev, time) mantenendo la geometria.

    :param epsilon: Tolleranza in gradi. ~0.00005 corrisponde a circa 5 metri.
    """
    if len(punti) < 3:
        return punti

    dmax = 0.0
    index = 0
    fine = len(punti) - 1

    # Cerca il punto con la massima distanza perpendicolare dalla retta che unisce inizio e fine
    for i in range(1, fine):
        d = distanza_perpendicolare(punti[i], punti[0], punti[fine])
        if d > dmax:
            index = i
            dmax = d

    # Se la distanza massima è superiore a epsilon, ricorsione sui due sotto-segmenti
    if dmax > epsilon:
        risultato1 = ramer_douglas_peucker(punti[: index + 1], epsilon)
        risultato2 = ramer_douglas_peucker(punti[index:], epsilon)
        return risultato1[:-1] + risultato2
    else:
        return [punti[0], punti[fine]]
