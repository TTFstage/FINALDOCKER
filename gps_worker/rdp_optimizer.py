import math


def perpendicular_distance(point, p1, p2):
    """Calculates the perpendicular distance of a point (lat, lon) from the line p1-p2."""
    lat, lon = point[0], point[1]
    lat1, lon1 = p1[0], p1[1]
    lat2, lon2 = p2[0], p2[1]

    if lat1 == lat2 and lon1 == lon2:
        return math.hypot(lat - lat1, lon - lon1)

    # Approximate conversion for geographic coordinates at short distances
    dx = lat2 - lat1
    dy = lon2 - lon1
    num = abs(dy * lat - dx * lon + lat2 * lon1 - lon2 * lat1)
    den = math.hypot(dx, dy)
    return num / den


def ramer_douglas_peucker(points, epsilon=0.00005):
    """Simplifies a list of points (lat, lon, elev, time) while preserving geometry.

    :param epsilon: Tolerance in degrees. ~0.00005 corresponds to approximately 5 meters.
    """
    if len(points) < 3:
        return points

    dmax = 0.0
    index = 0
    end = len(points) - 1

    # Find the point with the maximum perpendicular distance from the line connecting start and end
    for i in range(1, end):
        d = perpendicular_distance(points[i], points[0], points[end])
        if d > dmax:
            index = i
            dmax = d

    # If the maximum distance exceeds epsilon, recurse on both sub-segments
    if dmax > epsilon:
        result1 = ramer_douglas_peucker(points[: index + 1], epsilon)
        result2 = ramer_douglas_peucker(points[index:], epsilon)
        return result1[:-1] + result2
    else:
        return [points[0], points[end]]
