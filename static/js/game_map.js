/**
 * Games map viewer: Google Maps + Supercluster pins for geocoded locations.
 * Refetches pins for the visible map area (bbox) after the first fit.
 */
(function () {
  const featuresEl = document.getElementById("game-map-features");
  const configEl = document.getElementById("game-map-config");
  const canvas = document.getElementById("game-map-canvas");
  const statusEl = document.getElementById("game-map-status");
  if (!featuresEl || !configEl || !canvas) return;

  let config;
  try {
    config = JSON.parse(configEl.textContent);
  } catch (_err) {
    return;
  }
  if (!config.apiKey) return;

  let features = [];
  try {
    features = JSON.parse(featuresEl.textContent) || [];
  } catch (_err) {
    features = [];
  }

  let mapsPromise = null;
  let map = null;
  let infoWindow = null;
  let markers = [];
  let clusterIndex = null;
  let initialFitDone = false;
  let fetchTimer = null;
  let lastBboxKey = "";
  let fetchSeq = 0;

  function setStatus(message) {
    if (statusEl) statusEl.textContent = message || "";
  }

  function loadGoogleMaps(apiKey) {
    if (mapsPromise) return mapsPromise;
    if (typeof window.google?.maps?.Map === "function") {
      mapsPromise = Promise.resolve();
      return mapsPromise;
    }
    mapsPromise = new Promise((resolve, reject) => {
      let settled = false;
      const finish = (err) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (err) {
          mapsPromise = null;
          reject(err);
        } else {
          resolve();
        }
      };
      const timer = setTimeout(
        () => finish(new Error("Google Maps load timed out.")),
        15000,
      );
      const prevAuthFailure = window.gm_authFailure;
      window.gm_authFailure = () => {
        window.gm_authFailure = prevAuthFailure;
        finish(
          new Error(
            "Google Maps API key error. Check key and referrer restrictions.",
          ),
        );
        if (prevAuthFailure) prevAuthFailure();
      };
      const script = document.createElement("script");
      script.src =
        `https://maps.googleapis.com/maps/api/js` +
        `?key=${encodeURIComponent(apiKey)}&loading=async`;
      script.async = true;
      script.onload = () => {
        const start = Date.now();
        const poll = setInterval(() => {
          if (typeof window.google?.maps?.Map === "function") {
            clearInterval(poll);
            finish(null);
          } else if (Date.now() - start > 5000) {
            clearInterval(poll);
            finish(new Error("Google Maps init timed out."));
          }
        }, 30);
      };
      script.onerror = () => finish(new Error("Google Maps failed to load."));
      document.head.appendChild(script);
    });
    return mapsPromise;
  }

  function cityState(props) {
    const parts = [props.city, props.state, props.country].filter(Boolean);
    return parts.join(", ");
  }

  function gamesListHref(locationId) {
    const params = new URLSearchParams();
    if (config.groupId) params.set("group", config.groupId);
    params.set("location", String(locationId));
    const query = params.toString();
    return `${config.gamesListUrl}${query ? `?${query}` : ""}`;
  }

  function buildPopupContent(props) {
    const root = document.createElement("div");
    root.className = "game-map-popup";

    const title = document.createElement("div");
    title.className = "game-map-popup-title";
    title.textContent = props.name || "Location";
    root.appendChild(title);

    const metaText = cityState(props);
    if (metaText) {
      const meta = document.createElement("div");
      meta.className = "game-map-popup-meta";
      meta.textContent = metaText;
      root.appendChild(meta);
    }

    const list = document.createElement("ul");
    list.className = "game-map-popup-counts";
    (props.game_count_labels || []).forEach((row) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = row.name;
      const count = document.createElement("span");
      count.textContent = String(row.count);
      li.appendChild(name);
      li.appendChild(count);
      list.appendChild(li);
    });
    root.appendChild(list);

    const link = document.createElement("a");
    link.className = "btn btn-sm btn-outline-primary";
    link.href = gamesListHref(props.location_id);
    link.textContent = "View games";
    root.appendChild(link);
    return root;
  }

  function clearMarkers() {
    markers.forEach((marker) => marker.setMap(null));
    markers = [];
  }

  function clusterIcon(count) {
    const gmaps = window.google.maps;
    return {
      path: gmaps.SymbolPath.CIRCLE,
      scale: count > 99 ? 18 : count > 9 ? 16 : 14,
      fillColor: "#0d6efd",
      fillOpacity: 1,
      strokeColor: "#ffffff",
      strokeWeight: 2,
    };
  }

  function renderClusters() {
    if (!map || !clusterIndex) return;
    clearMarkers();
    const bounds = map.getBounds();
    if (!bounds) return;
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    const bbox = [sw.lng(), sw.lat(), ne.lng(), ne.lat()];
    const zoom = Math.round(map.getZoom() || 4);
    const leaves = clusterIndex.getClusters(bbox, zoom);
    const gmaps = window.google.maps;

    leaves.forEach((item) => {
      const [lng, lat] = item.geometry.coordinates;
      const position = { lat, lng };
      const isCluster = Boolean(item.properties.cluster);
      let marker;
      if (isCluster) {
        const count = item.properties.point_count;
        marker = new gmaps.Marker({
          map,
          position,
          icon: clusterIcon(count),
          label: {
            text: String(count),
            color: "#ffffff",
            fontSize: "12px",
            fontWeight: "600",
          },
          title: `${count} places`,
          zIndex: Number(gmaps.Marker.MAX_ZINDEX) + count,
        });
        marker.addListener("click", () => {
          const expansionZoom = Math.min(
            clusterIndex.getClusterExpansionZoom(item.id),
            18,
          );
          map.setCenter(position);
          map.setZoom(expansionZoom);
        });
      } else {
        const props = item.properties;
        marker = new gmaps.Marker({
          map,
          position,
          title: props.name || "Location",
        });
        marker.addListener("click", () => {
          infoWindow.setContent(buildPopupContent(props));
          infoWindow.open({ map, anchor: marker });
        });
      }
      markers.push(marker);
    });
  }

  function loadClusterIndex(nextFeatures) {
    features = nextFeatures || [];
    clusterIndex = new Supercluster({
      radius: 56,
      maxZoom: 16,
    });
    clusterIndex.load(features);
  }

  function paddedBboxParam() {
    const bounds = map.getBounds();
    if (!bounds) return "";
    const ne = bounds.getNorthEast();
    const sw = bounds.getSouthWest();
    let lonMin = sw.lng();
    let latMin = sw.lat();
    let lonMax = ne.lng();
    let latMax = ne.lat();
    const lonPad = Math.max((lonMax - lonMin) * 0.15, 0.01);
    const latPad = Math.max((latMax - latMin) * 0.15, 0.01);
    lonMin = Math.max(lonMin - lonPad, -180);
    latMin = Math.max(latMin - latPad, -90);
    lonMax = Math.min(lonMax + lonPad, 180);
    latMax = Math.min(latMax + latPad, 90);
    return [lonMin, latMin, lonMax, latMax]
      .map((n) => n.toFixed(6))
      .join(",");
  }

  function apiUrlWithBbox(bbox) {
    const url = new URL(config.apiUrl, window.location.origin);
    if (config.query) {
      const base = new URLSearchParams(config.query);
      base.forEach((value, key) => {
        url.searchParams.set(key, value);
      });
    }
    url.searchParams.set("bbox", bbox);
    return url.toString();
  }

  async function fetchViewportFeatures() {
    if (!config.apiUrl || !map) {
      renderClusters();
      return;
    }
    const bbox = paddedBboxParam();
    if (!bbox || bbox === lastBboxKey) {
      renderClusters();
      return;
    }
    lastBboxKey = bbox;
    const seq = ++fetchSeq;
    setStatus("Updating map…");
    try {
      const response = await fetch(apiUrlWithBbox(bbox), {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) throw new Error("Map data request failed.");
      const payload = await response.json();
      if (seq !== fetchSeq) return;
      loadClusterIndex(payload.features || []);
      renderClusters();
      setStatus(
        features.length === 1
          ? "1 place in view"
          : `${features.length} places in view`,
      );
    } catch (err) {
      if (seq !== fetchSeq) return;
      console.warn("[game-map]", err);
      setStatus(err?.message || "Could not update map places.");
      renderClusters();
    }
  }

  function fitToFeatures() {
    if (!features.length) return;
    const gmaps = window.google.maps;
    const bounds = new gmaps.LatLngBounds();
    features.forEach((feature) => {
      const [lng, lat] = feature.geometry.coordinates;
      bounds.extend({ lat, lng });
    });
    map.fitBounds(bounds, 48);
    gmaps.event.addListenerOnce(map, "idle", () => {
      if (features.length === 1) {
        map.setZoom(Math.min(map.getZoom() || 14, 14));
      }
      initialFitDone = true;
      renderClusters();
    });
  }

  async function init() {
    if (!features.length) {
      setStatus("No places to show.");
      return;
    }
    if (typeof Supercluster !== "function") {
      setStatus("Cluster library failed to load.");
      return;
    }

    setStatus("Loading map…");
    try {
      await loadGoogleMaps(config.apiKey);
      const gmaps = window.google.maps;
      map = new gmaps.Map(canvas, {
        center: { lat: 39.8283, lng: -98.5795 },
        zoom: 4,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
      });
      infoWindow = new gmaps.InfoWindow();
      loadClusterIndex(features);

      map.addListener("idle", () => {
        if (!initialFitDone) {
          renderClusters();
          return;
        }
        window.clearTimeout(fetchTimer);
        fetchTimer = window.setTimeout(fetchViewportFeatures, 250);
      });
      fitToFeatures();
      setStatus(
        features.length === 1 ? "1 place" : `${features.length} places`,
      );
    } catch (err) {
      console.warn("[game-map]", err);
      setStatus(err?.message || "Could not load map.");
    }
  }

  init();
})();
