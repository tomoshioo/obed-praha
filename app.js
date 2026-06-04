/* Oběd na mapě – pražská polední menu (data: menicka.cz) */
(function () {
  "use strict";

  var PRAGUE = [50.083, 14.421];
  var $ = function (id) { return document.getElementById(id); };

  var map = L.map("map", { zoomControl: true, attributionControl: true })
    .setView(PRAGUE, 13);
  L.control.zoom({ position: "topright" }); // default already added; keep at topright on small screens via CSS if needed

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
      '&copy; <a href="https://carto.com/attributions">CARTO</a> &middot; ' +
      'menu <a href="https://www.menicka.cz" target="_blank" rel="noopener">Menicka.cz</a>',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(map);

  var cluster = L.markerClusterGroup({
    maxClusterRadius: 50,
    disableClusteringAtZoom: 16,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    chunkedLoading: true,
  });

  var ALL = []; // { m: marker, hay: searchstring }
  var meMarker = null;

  /* ---------- helpers ---------- */
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function cleanDish(t) {
    return String(t || "")
      .replace(/\s*(?:A|Alergeny)\s*:\s*[\d.,\s]+$/i, "")
      .trim();
  }
  function isSoup(t) {
    return /^(?:pol[ée]vka|vývar|bujón|bujon|krém|krem|consom|čočková|gulášov|hovězí vývar)/i.test(
      String(t || "").trim()
    );
  }
  function districtLabel(d) {
    return String(d || "").replace("praha-", "Praha ");
  }

  function card(r) {
    var rows = (r.menu || [])
      .map(function (d) {
        var name = esc(cleanDish(d.text));
        if (!name) return "";
        var price = d.price ? '<span class="d-price">' + esc(d.price) + "</span>" : "";
        return (
          '<div class="dish' + (isSoup(d.text) ? " soup" : "") + '">' +
          '<span class="d-name">' + name + "</span>" + price + "</div>"
        );
      })
      .filter(Boolean)
      .join("");
    return (
      '<div class="menu-tip">' +
      '<div class="tip-name">' + esc(r.name) + "</div>" +
      (r.address ? '<div class="tip-addr">' + esc(r.address) + "</div>" : "") +
      '<div class="tip-menu">' +
      (rows || '<span class="tip-empty">Dnes bez zveřejněného menu</span>') +
      "</div>" +
      '<div class="tip-foot"><span>' + esc(districtLabel(r.district)) + "</span>" +
      '<a href="' + esc(r.url) + '" target="_blank" rel="noopener">menicka.cz ↗</a></div>' +
      "</div>"
    );
  }

  function makeIcon() {
    return L.divIcon({
      className: "",
      html: '<div class="rest-pin"><span>🍴</span></div>',
      iconSize: [30, 30],
      iconAnchor: [15, 30],
      popupAnchor: [0, -28],
      tooltipAnchor: [0, -26],
    });
  }
  var ICON = makeIcon();

  var toastT;
  function toast(msg) {
    var t = $("toast");
    if (!t) {
      t = document.createElement("div");
      t.id = "toast";
      t.className = "toast";
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastT);
    toastT = setTimeout(function () { t.classList.remove("show"); }, 4200);
  }

  /* ---------- init ---------- */
  function init(data) {
    var list = (data && data.restaurants) || [];
    $("meta").textContent =
      list.length + " restaurací · menu " + (data.menu_date || "dnes");
    document.title =
      "Oběd na mapě (" + list.length + " restaurací) – polední menu v Praze";

    var markers = [];
    list.forEach(function (r) {
      if (typeof r.lat !== "number" || typeof r.lng !== "number") return;
      var m = L.marker([r.lat, r.lng], { icon: ICON, title: r.name });
      var html = card(r);
      m.bindTooltip(html, {
        direction: "top",
        className: "tip-wrap",
        opacity: 1,
        offset: [0, -2],
      });
      m.bindPopup(html, { className: "tip-wrap", maxWidth: 340, autoPanPadding: [24, 80] });
      markers.push(m);
      ALL.push({
        m: m,
        hay: (r.name + " " + (r.menu || []).map(function (d) { return d.text; }).join(" "))
          .toLowerCase(),
      });
    });
    cluster.addLayers(markers);
    map.addLayer(cluster);

    $("loader").classList.add("done");
    setTimeout(function () { var h = $("hint"); if (h) h.classList.add("hide"); }, 6500);

    autoLocate();
  }

  /* ---------- filter ---------- */
  var filterT;
  function applyFilter(q) {
    q = (q || "").trim().toLowerCase();
    var subset = q
      ? ALL.filter(function (x) { return x.hay.indexOf(q) !== -1; })
      : ALL;
    cluster.clearLayers();
    cluster.addLayers(subset.map(function (x) { return x.m; }));
    $("meta").textContent =
      subset.length + (q ? " odpovídá filtru" : " restaurací") +
      (window.__menuDate ? " · menu " + window.__menuDate : "");
  }
  $("filter").addEventListener("input", function (e) {
    clearTimeout(filterT);
    var v = e.target.value;
    filterT = setTimeout(function () { applyFilter(v); }, 220);
  });

  /* ---------- geolocation ---------- */
  function placeMe(latlng, accuracy) {
    if (meMarker) map.removeLayer(meMarker);
    meMarker = L.marker(latlng, {
      icon: L.divIcon({ className: "", html: '<div class="me-dot"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }),
      zIndexOffset: 2000,
      interactive: false,
    }).addTo(map);
  }
  function autoLocate() {
    if (!navigator.geolocation) return;
    map.locate({ setView: true, maxZoom: 15, enableHighAccuracy: true, timeout: 8000 });
  }
  map.on("locationfound", function (e) {
    placeMe(e.latlng, e.accuracy);
  });
  map.on("locationerror", function () {
    toast("Polohu se nepodařilo zjistit. Zadej místo do vyhledávání nahoře.");
  });
  $("locate").addEventListener("click", autoLocate);

  /* ---------- place search (Nominatim) ---------- */
  function jumpToPlace(q) {
    q = (q || "").trim();
    if (!q) return;
    if (!/praha|praha 1|vinohrad|žižkov|zizkov/i.test(q)) q = q + ", Praha";
    var url =
      "https://nominatim.openstreetmap.org/search?format=json&limit=1&accept-language=cs" +
      "&viewbox=14.22,50.18,14.71,49.94&bounded=1&q=" + encodeURIComponent(q);
    fetch(url, { headers: { Accept: "application/json" } })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res && res.length) {
          var lat = parseFloat(res[0].lat), lon = parseFloat(res[0].lon);
          map.setView([lat, lon], 16);
          placeMe([lat, lon]);
        } else {
          toast('Místo „' + q + '" jsem v Praze nenašel.');
        }
      })
      .catch(function () { toast("Vyhledávání místa selhalo, zkus to znovu."); });
  }
  $("place").addEventListener("keydown", function (e) {
    if (e.key === "Enter") jumpToPlace(e.target.value);
  });

  /* ---------- load data ---------- */
  fetch("data/restaurants.json", { cache: "no-store" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      window.__menuDate = data.menu_date;
      init(data);
    })
    .catch(function (err) {
      $("loader").innerHTML =
        '<div style="text-align:center;color:#b91c1c">Nepodařilo se načíst menu.<br><small>' +
        esc(err.message) + "</small></div>";
      console.error(err);
    });
})();
