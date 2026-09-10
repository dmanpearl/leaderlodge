(function () {
  const US_CENTER = { lat: 39.8283, lon: -98.5795 };
  const DEFAULT_ZOOM = 4;
  /** City / municipality overview when opening the map near the user. */
  const MUNICIPALITY_ZOOM = 12;
  /** Street-level zoom after Use my location or placing a pin. */
  const FOCUS_ZOOM = 16;

  const NEARBY_TYPES = [
    "park",
    "restaurant",
    "cafe",
    "community_center",
    "shopping_mall",
    "library",
    "sports_complex",
    "athletic_field",
    "campground",
    "rv_park",
    "tourist_attraction",
    "zoo",
    "aquarium",
    "museum",
    "hospital",
    "food_court",
  ];

  let mapsPromise = null;

  function loadGoogleMaps(apiKey) {
    if (mapsPromise) return mapsPromise;
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
          if (typeof google?.maps?.importLibrary === "function") {
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

  function extractAddressParts(addressComponents) {
    const parts = {
      city: "",
      state: "",
      country: "",
      postal_code: "",
      street_address: "",
    };
    if (!addressComponents) return parts;

    let route = "";
    let streetNumber = "";
    for (const c of addressComponents) {
      const types = c.types || [];
      if (types.includes("locality")) {
        parts.city = c.longText || c.shortText || "";
      } else if (types.includes("administrative_area_level_1")) {
        parts.state = c.shortText || "";
      } else if (types.includes("country")) {
        parts.country = (c.shortText || "").toUpperCase();
      } else if (types.includes("postal_code")) {
        parts.postal_code = c.longText || c.shortText || "";
      } else if (types.includes("route")) {
        route = c.longText || c.shortText || "";
      } else if (types.includes("street_number")) {
        streetNumber = c.longText || c.shortText || "";
      }
    }
    parts.street_address = route || (streetNumber ? streetNumber : "");
    return parts;
  }

  function extractCityState(addressComponents) {
    const parts = extractAddressParts(addressComponents);
    if (parts.city && parts.state) return `${parts.city}, ${parts.state}`;
    return parts.city || parts.state || "";
  }

  function placeLatLon(place) {
    const loc = place?.location;
    if (!loc) return null;
    const lat = typeof loc.lat === "function" ? loc.lat() : loc.lat;
    const lng = typeof loc.lng === "function" ? loc.lng() : loc.lng;
    if (lat == null || lng == null) return null;
    return { lat: Number(lat), lon: Number(lng) };
  }

  function placeIdOf(place) {
    return place?.id || place?.placeId || "";
  }

  function placeDisplayName(place) {
    if (!place) return "";
    const name = place.displayName;
    if (typeof name === "string") return name;
    return name?.text || name?.toString?.() || "";
  }

  function geoFromPlace(place, source) {
    const coords = placeLatLon(place);
    if (!coords) return null;
    const parts = extractAddressParts(place.addressComponents);
    return {
      lat: coords.lat,
      lon: coords.lon,
      city: parts.city,
      state: parts.state,
      country: parts.country,
      postal_code: parts.postal_code,
      street_address: parts.street_address,
      place_id: placeIdOf(place),
      geocode_source: source,
      place_display_name: placeDisplayName(place),
      label: formatPlaceLabel(place),
    };
  }

  function formatPlaceLabel(place) {
    const name = placeDisplayName(place);
    const cs = extractCityState(place.addressComponents);
    return cs ? `${name}, ${cs}` : name;
  }

  function getPosition() {
    return new Promise((resolve, reject) => {
      if (!navigator.geolocation) {
        reject(new Error("Geolocation is not supported."));
        return;
      }
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false,
        timeout: 10000,
        maximumAge: 60000,
      });
    });
  }

  function roundCoord(value) {
    return Math.round(Number(value) * 1e6) / 1e6;
  }

  class LocationMapPicker {
    constructor(container, options) {
      this.container = container;
      this.apiKey = options.apiKey;
      this.readOnly = Boolean(options.readOnly);
      this.onSelectionChange = options.onSelectionChange || (() => {});
      this.onStatus = options.onStatus || (() => {});
      this.map = null;
      this.marker = null;
      this.resultMarkers = [];
      this.selection = null;
      this._clickListener = null;
      this._dragListener = null;
    }

    async init(initial) {
      await loadGoogleMaps(this.apiKey);
      const { Map } = await google.maps.importLibrary("maps");
      const center = await this._initialCenter(initial);
      this.map = new Map(this.container, {
        center: { lat: center.lat, lng: center.lon },
        zoom: center.zoom,
        mapTypeControl: false,
        streetViewControl: false,
        fullscreenControl: true,
        gestureHandling: this.readOnly ? "cooperative" : "auto",
      });

      if (!this.readOnly) {
        this._clickListener = this.map.addListener("click", (event) => {
          this.setPin(event.latLng.lat(), event.latLng.lng(), {
            geocode_source: "map_pin",
          });
        });
      }

      if (initial?.lat != null && initial?.lon != null) {
        this.setPin(initial.lat, initial.lon, {
          geocode_source: initial.geocode_source || "map_pin",
          silent: true,
        });
      }
    }

    async _initialCenter(initial) {
      if (initial?.lat != null && initial?.lon != null) {
        return {
          lat: Number(initial.lat),
          lon: Number(initial.lon),
          zoom: initial.zoom || FOCUS_ZOOM,
        };
      }
      try {
        const pos = await getPosition();
        return {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          zoom: MUNICIPALITY_ZOOM,
        };
      } catch (_err) {
        return { ...US_CENTER, zoom: DEFAULT_ZOOM };
      }
    }

    destroy() {
      this.clearResultMarkers();
      if (this._dragListener) {
        google.maps.event.removeListener(this._dragListener);
        this._dragListener = null;
      }
      if (this._clickListener) {
        google.maps.event.removeListener(this._clickListener);
        this._clickListener = null;
      }
      if (this.marker) {
        this.marker.setMap(null);
        this.marker = null;
      }
      this.map = null;
      this.selection = null;
      this.container.innerHTML = "";
    }

    setStatus(message, isError) {
      this.onStatus(message || "", Boolean(isError));
    }

    clearResultMarkers() {
      for (const m of this.resultMarkers) {
        m.setMap(null);
      }
      this.resultMarkers = [];
    }

    ensureMarker(lat, lon) {
      if (!this.map) return;
      const pos = { lat: Number(lat), lng: Number(lon) };
      if (!this.marker) {
        this.marker = new google.maps.Marker({
          map: this.map,
          position: pos,
          draggable: !this.readOnly,
          title: this.readOnly ? "Place" : "Selected pin",
        });
        if (!this.readOnly) {
          this._dragListener = this.marker.addListener("dragend", () => {
            const p = this.marker.getPosition();
            this.setPin(p.lat(), p.lng(), { geocode_source: "map_pin" });
          });
        }
      } else {
        this.marker.setPosition(pos);
        this.marker.setMap(this.map);
      }
      this.map.panTo(pos);
      if (this.map.getZoom() < FOCUS_ZOOM) {
        this.map.setZoom(FOCUS_ZOOM);
      }
    }

    applySelection(geo) {
      this.selection = geo;
      this.onSelectionChange(geo);
    }

    clearSelection() {
      this.selection = null;
      this.onSelectionChange(null);
      this.clearResultMarkers();
      if (this.marker) {
        this.marker.setMap(null);
      }
    }

    async setPin(lat, lon, opts = {}) {
      const roundedLat = roundCoord(lat);
      const roundedLon = roundCoord(lon);
      this.ensureMarker(roundedLat, roundedLon);
      this.clearResultMarkers();

      if (opts.silent) {
        return;
      }

      const source = opts.geocode_source || "map_pin";
      if (opts.place) {
        const geo = geoFromPlace(opts.place, source);
        if (geo) {
          this.applySelection(geo);
          return;
        }
      }

      try {
        const geo = await this.reverseGeocode(roundedLat, roundedLon, source);
        this.applySelection(geo);
      } catch (err) {
        this.applySelection({
          lat: roundedLat,
          lon: roundedLon,
          city: "",
          state: "",
          country: "",
          postal_code: "",
          street_address: "",
          place_id: "",
          geocode_source: source,
          place_display_name: "",
          label: `${roundedLat}, ${roundedLon}`,
        });
        this.setStatus(err?.message || "Could not reverse geocode pin.", true);
      }
    }

    reverseGeocode(lat, lon, source) {
      return new Promise((resolve, reject) => {
        const geocoder = new google.maps.Geocoder();
        geocoder.geocode(
          { location: { lat: Number(lat), lng: Number(lon) } },
          (results, status) => {
            if (status !== "OK" || !results?.length) {
              reject(new Error("Reverse geocode failed."));
              return;
            }
            const top = results[0];
            const parts = {
              city: "",
              state: "",
              country: "",
              postal_code: "",
              street_address: "",
            };
            for (const c of top.address_components || []) {
              const types = c.types || [];
              if (types.includes("locality")) {
                parts.city = c.long_name || "";
              } else if (types.includes("administrative_area_level_1")) {
                parts.state = c.short_name || "";
              } else if (types.includes("country")) {
                parts.country = (c.short_name || "").toUpperCase();
              } else if (types.includes("postal_code")) {
                parts.postal_code = c.long_name || "";
              } else if (types.includes("route")) {
                parts.street_address = c.long_name || "";
              }
            }
            const label = top.formatted_address || `${lat}, ${lon}`;
            resolve({
              lat: roundCoord(lat),
              lon: roundCoord(lon),
              city: parts.city,
              state: parts.state,
              country: parts.country,
              postal_code: parts.postal_code,
              street_address: parts.street_address,
              place_id: top.place_id || "",
              geocode_source: source,
              place_display_name: label,
              label,
            });
          },
        );
      });
    }

    showResultMarkers(places, onPick) {
      this.clearResultMarkers();
      for (const place of places) {
        const coords = placeLatLon(place);
        if (!coords) continue;
        const marker = new google.maps.Marker({
          map: this.map,
          position: { lat: coords.lat, lng: coords.lon },
          title: placeDisplayName(place),
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            scale: 7,
            fillColor: "#0d6efd",
            fillOpacity: 0.85,
            strokeColor: "#ffffff",
            strokeWeight: 2,
          },
        });
        marker.addListener("click", () => onPick(place));
        this.resultMarkers.push(marker);
      }
      if (places.length) {
        const first = placeLatLon(places[0]);
        if (first) {
          this.map.panTo({ lat: first.lat, lng: first.lon });
          if (this.map.getZoom() < FOCUS_ZOOM) {
            this.map.setZoom(FOCUS_ZOOM);
          }
        }
      }
    }

    async textSearch(query) {
      const text = String(query || "").trim();
      if (!text) {
        throw new Error("Enter a search term.");
      }
      const { Place } = await google.maps.importLibrary("places");
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Places search timed out.")), 12000),
      );
      const searchPromise = Place.searchByText({
        textQuery: text,
        fields: ["displayName", "addressComponents", "location", "id"],
        maxResultCount: 8,
      });
      const { places } = await Promise.race([searchPromise, timeoutPromise]);
      return places || [];
    }

    async nearbySearch(lat, lon) {
      const { Place } = await google.maps.importLibrary("places");
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error("Places search timed out.")), 10000),
      );
      const searchPromise = Place.searchNearby({
        fields: ["displayName", "addressComponents", "location", "id"],
        locationRestriction: {
          center: { lat: Number(lat), lng: Number(lon) },
          radius: 600,
        },
        includedTypes: NEARBY_TYPES,
        maxResultCount: 8,
      });
      const { places } = await Promise.race([searchPromise, timeoutPromise]);
      return places || [];
    }

    async searchPlaces(query) {
      this.setStatus("");
      const places = await this.textSearch(query);
      if (!places.length) {
        throw new Error("No places found for that search.");
      }
      return places;
    }

    async pinLookup() {
      this.setStatus("");
      if (!this.marker) {
        throw new Error("Drop a pin on the map first.");
      }
      const pos = this.marker.getPosition();
      const places = await this.nearbySearch(pos.lat(), pos.lng());
      if (!places.length) {
        throw new Error("No nearby places found at this pin.");
      }
      return places;
    }

    async useMyLocation() {
      this.setStatus("");
      const pos = await getPosition();
      await this.setPin(pos.coords.latitude, pos.coords.longitude, {
        geocode_source: "gps",
      });
      if (this.map) {
        this.map.setZoom(FOCUS_ZOOM);
      }
      return { lat: pos.coords.latitude, lon: pos.coords.longitude };
    }

    selectPlace(place, source) {
      const coords = placeLatLon(place);
      if (!coords) {
        throw new Error("Selected place has no coordinates.");
      }
      this.ensureMarker(coords.lat, coords.lon);
      const geo = geoFromPlace(place, source);
      if (!geo) {
        throw new Error("Could not read place details.");
      }
      this.applySelection(geo);
      this.setStatus("");
    }
  }

  window.LeaderLodgeLocationMap = {
    LocationMapPicker,
    loadGoogleMaps,
    formatPlaceLabel,
    geoFromPlace,
    placeDisplayName,
    extractCityState,
    MUNICIPALITY_ZOOM,
    FOCUS_ZOOM,
  };
})();
