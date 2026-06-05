/* Oběd na mapě – pražská polední menu (data: menicka.cz) */
(function () {
  "use strict";

  var PRAGUE = [50.083, 14.421];
  var $ = function (id) { return document.getElementById(id); };

  var map = L.map("map", { zoomControl: true, attributionControl: true })
    .setView(PRAGUE, 13);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> ' +
      '&copy; <a href="https://carto.com/attributions">CARTO</a> &middot; ' +
      'menu <a href="https://www.menicka.cz" target="_blank" rel="noopener">Menicka.cz</a>',
    subdomains: "abcd",
    maxZoom: 20,
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
    return /^(?:pol[ée]vka|vývar|bujón|bujon|krém|krem|consom|čočková|gulášov|hovězí vývar|drůbeží vývar)/i.test(
      String(t || "").trim()
    );
  }
  function districtLabel(d) {
    return String(d || "").replace("praha-", "Praha ");
  }
  function priceNum(p) {
    var m = String(p || "").replace(/\s/g, "").match(/(\d{2,4})/);
    return m ? +m[1] : null;
  }
  // reprezentativní cena = nejlevnější "hlavní" jídlo (>= 80 Kč); levels pro barvu pinu
  function priceInfo(menu) {
    var nums = [];
    (menu || []).forEach(function (d) {
      var n = priceNum(d.price);
      if (n) nums.push(n);
    });
    var mains = nums.filter(function (n) { return n >= 80; });
    var min = mains.length ? Math.min.apply(null, mains)
            : (nums.length ? Math.min.apply(null, nums) : null);
    var level = "unknown";
    if (mains.length) {
      level = min < 130 ? "cheap" : (min < 180 ? "mid" : "high");
    }
    return { min: min, level: level, hasMain: mains.length > 0 };
  }

  function timeStr(r) {
    if (r.time_from && r.time_to) return r.time_from + "–" + r.time_to;
    if (r.time_to) return "do " + r.time_to;
    if (r.time_from) return "od " + r.time_from;
    return null;
  }
  function todayISO() {
    var d = new Date();
    return d.getFullYear() + "-" + ("0" + (d.getMonth() + 1)).slice(-2) + "-" + ("0" + d.getDate()).slice(-2);
  }

  function dishRows(menu) {
    return (menu || [])
      .map(function (d) {
        var name = esc(cleanDish(d.text));
        if (!name) return "";
        var price = d.price ? '<span class="d-price">' + esc(d.price) + "</span>" : "";
        return '<div class="dish' + (isSoup(d.text) ? " soup" : "") +
               '"><span class="d-name">' + name + "</span>" + price + "</div>";
      })
      .filter(Boolean)
      .join("");
  }

  function card(r) {
    var status = r.menu_status || "scraped";
    var pi = priceInfo(r.menu);
    var isWeb = r.source === "web";
    var t = timeStr(r);
    var timeLine = t ? '<div class="tip-time">🕚 ' + esc(t) + "</div>" : "";
    var badge = (status === "scraped" && pi.hasMain) ? '<span class="tip-badge">od ' + pi.min + " Kč</span>" : "";

    var body, linkUrl, linkLabel;
    if (status === "link") {
      body = '<div class="tip-cta"><a class="cta" href="' + esc(r.menu_url || r.website || "#") +
             '" target="_blank" rel="noopener">📋 Zobrazit dnešní polední menu ↗</a></div>';
      linkUrl = r.website || r.menu_url; linkLabel = "web restaurace ↗";
    } else if (status === "none") {
      var q = encodeURIComponent(r.name + " Praha polední menu");
      body = '<div class="tip-cta"><a class="cta cta-alt" href="https://www.google.com/search?q=' + q +
             '" target="_blank" rel="noopener">🔎 Najít dnešní menu ↗</a></div>';
      linkUrl = r.website || null; linkLabel = "web ↗";
    } else {
      var stale = isWeb && r.menu_date_web && r.menu_date_web !== "fixed" && r.menu_date_web !== todayISO();
      body = stale
        ? '<div class="tip-cta"><a class="cta" href="' + esc(r.menu_url || r.website || "#") +
          '" target="_blank" rel="noopener">📋 Dnešní menu na webu ↗</a></div>'
        : (dishRows(r.menu) || '<span class="tip-empty">Dnes bez zveřejněného menu</span>');
      linkUrl = isWeb ? (r.menu_url || r.website || r.url) : r.url;
      linkLabel = isWeb ? "web ↗" : "menicka.cz ↗";
    }

    var chips = isWeb
      ? '<span class="pill src-web">🌐 web restaurace</span>' +
        (r.web_confirmed ? '<span class="pill src-ok">✓ ověřeno</span>' : "")
      : (r.web_confirmed
          ? '<span class="pill src-men">menicka</span><span class="pill src-ok">✓ ověřeno z webu</span>'
          : '<span class="pill src-men">menicka</span>');
    var foot = '<div class="tip-foot"><span class="chips">' + chips + "</span>" +
      (linkUrl ? '<a href="' + esc(linkUrl) + '" target="_blank" rel="noopener">' + linkLabel + "</a>" : "") + "</div>";

    return (
      '<div class="menu-tip">' +
        '<div class="tip-head' + (status !== "scraped" ? " mini" : "") + '">' + badge +
          '<div class="tip-name">' + esc(r.name) + "</div>" +
          (r.address ? '<div class="tip-addr">' + esc(r.address) + "</div>" : "") +
          timeLine +
        "</div>" +
        '<div class="tip-menu">' + body + "</div>" + foot +
      "</div>"
    );
  }

  function makeIcon(level, isWeb) {
    return L.divIcon({
      className: "",
      html: '<div class="pin lvl-' + level + (isWeb ? " web" : "") + '"><span>🍴</span></div>',
      iconSize: [34, 34],
      iconAnchor: [17, 33],
      popupAnchor: [0, -30],
      tooltipAnchor: [0, -28],
    });
  }

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
    var scN = 0;
    list.forEach(function (r) { if ((r.menu_status || "scraped") === "scraped") scN++; });
    $("meta").textContent =
      list.length + " podniků · " + scN + " s menu · " + (data.menu_date || "dnes");
    document.title =
      "Oběd na mapě (" + list.length + " restaurací) – polední menu v Praze";

    var markers = [];
    list.forEach(function (r) {
      if (typeof r.lat !== "number" || typeof r.lng !== "number") return;
      var status = r.menu_status || "scraped";
      var pi = priceInfo(r.menu);
      var level = status === "scraped" ? pi.level : status;
      var m = L.marker([r.lat, r.lng], { icon: makeIcon(level, r.source === "web" && status === "scraped"), title: r.name });
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
  function placeMe(latlng) {
    if (meMarker) map.removeLayer(meMarker);
    meMarker = L.marker(latlng, {
      icon: L.divIcon({
        className: "",
        html: '<div class="me"><div class="ring"></div><div class="dot"></div></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10],
      }),
      zIndexOffset: 2000,
      interactive: false,
    }).addTo(map);
  }
  function autoLocate() {
    if (!navigator.geolocation) return;
    map.locate({ setView: true, maxZoom: 15, enableHighAccuracy: true, timeout: 8000 });
  }
  map.on("locationfound", function (e) { placeMe(e.latlng); });
  map.on("locationerror", function () {
    toast("Polohu se nepodařilo zjistit. Zadej místo do vyhledávání nahoře.");
  });
  $("locate").addEventListener("click", autoLocate);

  /* ---------- place search (Nominatim) ---------- */
  function jumpToPlace(q) {
    q = (q || "").trim();
    if (!q) return;
    if (!/praha|vinohrad|žižkov|zizkov|karlín|karlin|smíchov|smichov/i.test(q)) q = q + ", Praha";
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
