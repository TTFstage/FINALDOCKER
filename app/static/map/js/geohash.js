// Implementazione minimale dell'algoritmo geohash standard (base32),
// equivalente a quanto usato lato server con la libreria "ngeohash".
(function (global) {
  const BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz";

  function encode(lat, lon, precision) {
    precision = precision || 9;
    let idx = 0;
    let bit = 0;
    let evenBit = true;
    let geohash = "";

    let latMin = -90,
      latMax = 90;
    let lonMin = -180,
      lonMax = 180;

    while (geohash.length < precision) {
      if (evenBit) {
        const lonMid = (lonMin + lonMax) / 2;
        if (lon >= lonMid) {
          idx = idx * 2 + 1;
          lonMin = lonMid;
        } else {
          idx = idx * 2;
          lonMax = lonMid;
        }
      } else {
        const latMid = (latMin + latMax) / 2;
        if (lat >= latMid) {
          idx = idx * 2 + 1;
          latMin = latMid;
        } else {
          idx = idx * 2;
          latMax = latMid;
        }
      }
      evenBit = !evenBit;

      if (++bit === 5) {
        geohash += BASE32.charAt(idx);
        bit = 0;
        idx = 0;
      }
    }
    return geohash;
  }

  function decodeBbox(geohash) {
    let evenBit = true;
    let latMin = -90,
      latMax = 90;
    let lonMin = -180,
      lonMax = 180;

    for (let i = 0; i < geohash.length; i++) {
      const chr = geohash.charAt(i).toLowerCase();
      const idx = BASE32.indexOf(chr);
      if (idx === -1) throw new Error("Invalid geohash character: " + chr);

      for (let n = 4; n >= 0; n--) {
        const bitN = (idx >> n) & 1;
        if (evenBit) {
          const lonMid = (lonMin + lonMax) / 2;
          if (bitN === 1) lonMin = lonMid;
          else lonMax = lonMid;
        } else {
          const latMid = (latMin + latMax) / 2;
          if (bitN === 1) latMin = latMid;
          else latMax = latMid;
        }
        evenBit = !evenBit;
      }
    }
    return { latMin, latMax, lonMin, lonMax };
  }

  // Restituisce l'insieme di geohash a "precision" caratteri che coprono
  // il bounding box dato (equivalente a ngeohash.bboxes).
  function bboxes(minLat, minLon, maxLat, maxLon, precision) {
    precision = precision || 5;
    const hashSW = encode(minLat, minLon, precision);
    const hashNE = encode(maxLat, maxLon, precision);

    const boxSW = decodeBbox(hashSW);
    const latStep = boxSW.latMax - boxSW.latMin;
    const lonStep = boxSW.lonMax - boxSW.lonMin;

    const result = new Set();
    for (let lat = boxSW.latMin; lat <= maxLat + latStep; lat += latStep) {
      for (let lon = boxSW.lonMin; lon <= maxLon + lonStep; lon += lonStep) {
        result.add(encode(lat, lon, precision));
      }
    }
    result.add(hashNE);
    return Array.from(result);
  }

  global.geohashLib = { encode, decodeBbox, bboxes };
})(window);
