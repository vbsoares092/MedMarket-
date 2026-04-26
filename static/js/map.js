/* =============================================================================
   MedMarket — Leaflet.js Integration  (Airbnb-style price badges + GPS)
   Globals required: window.MAP_POINTS    [{id,lat,lng,nome,title,preco,
                                            especialidade,img_url}]
                     window.LOC_CENTER    {lat,lng} | null
                     window.USER_LOCATION {lat,lng} | null   (GPS position)
   ============================================================================= */

(function () {
  'use strict';

  var mapEl    = document.getElementById('map');
  var loaderEl = document.getElementById('vmMapLoader');

  function hideLoader() {
    if (!loaderEl) return;
    loaderEl.style.transition = 'opacity .2s';
    loaderEl.style.opacity    = '0';
    setTimeout(function () { if (loaderEl) loaderEl.style.display = 'none'; }, 220);
  }

  if (!mapEl) { hideLoader(); return; }

  var pts      = window.MAP_POINTS    || [];
  var center   = window.LOC_CENTER    || null;
  var userLoc  = window.USER_LOCATION || null;

  /* -- Determine initial center & zoom -- */
  var initCenter, initZoom;
  if (userLoc) {
    /* GPS active: focus on user with a ~5 km radius (zoom 13) */
    initCenter = [userLoc.lat, userLoc.lng];
    initZoom   = 13;
  } else if (pts.length > 0) {
    var sumLat = 0, sumLng = 0;
    pts.forEach(function (p) { sumLat += p.lat; sumLng += p.lng; });
    initCenter = [sumLat / pts.length, sumLng / pts.length];
    initZoom   = pts.length === 1 ? 14 : 12;
  } else if (center) {
    initCenter = [center.lat, center.lng];
    initZoom   = 11;
  } else {
    initCenter = [-14.235, -51.925]; /* geographic centre of Brazil */
    initZoom   = 5;
  }

  /* -- Create Leaflet map -- */
  var map = L.map('map', {
    center:          initCenter,
    zoom:            initZoom,
    zoomControl:     true,
    scrollWheelZoom: 'center',
  });

  /* -- Stadia Alidade Smooth tiles: minimalista premium, foco nos pins -- */
  L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://stadiamaps.com/">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom:     20,
  }).addTo(map);

  /* -- Helper: sanitise output to prevent XSS -- */
  function esc(s) {
    return String(s || '')
      .replace(/&/g,  '&amp;')
      .replace(/</g,  '&lt;')
      .replace(/>/g,  '&gt;')
      .replace(/"/g,  '&quot;');
  }

  /* -- Active marker tracking -- */
  var activeMarker = null;

  /* ── User location pulsing blue marker ─────────────────────────────── */
  if (userLoc) {
    var userIcon = L.divIcon({
      className:  'mm-user-location-wrap',
      html:       '<div class="mm-user-location-marker">' +
                    '<div class="mm-user-location-pulse"></div>' +
                    '<div class="mm-user-location-dot"></div>' +
                  '</div>',
      iconSize:   [20, 20],
      iconAnchor: [10, 10],
    });
    L.marker([userLoc.lat, userLoc.lng], {
      icon:         userIcon,
      zIndexOffset: 1000,
    }).addTo(map)
      .bindTooltip('Você está aqui', {
        permanent:  false,
        direction:  'top',
        className:  'mm-user-tooltip',
        offset:     [0, -14],
      });
  }

  /* ── Recenter control (only when GPS is active) ─────────────────────── */
  if (userLoc) {
    var RecenterCtrl = L.Control.extend({
      options: { position: 'topright' },
      onAdd: function () {
        var btn = L.DomUtil.create('button', 'mm-recenter-btn leaflet-bar');
        btn.type  = 'button';
        btn.title = 'Centralizar na minha posição';
        btn.innerHTML =
          '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" ' +
          'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
          '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>' +
          '<line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/>' +
          '<line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/>' +
          '</svg>';
        L.DomEvent.on(btn, 'click', function (e) {
          L.DomEvent.stopPropagation(e);
          map.setView([userLoc.lat, userLoc.lng], 13, { animate: true });
        });
        L.DomEvent.disableClickPropagation(btn);
        return btn;
      },
    });
    new RecenterCtrl().addTo(map);

    /* Expose globally so the GPS button in the search pill can re-center too */
    window._medMarketRecenter = function (lat, lng) {
      map.setView([lat, lng], 13, { animate: true });
    };
  }


  pts.forEach(function (p, i) {
    var label    = p.preco
      ? 'R$\u00a0' + Number(p.preco).toLocaleString('pt-BR')
      : 'Consultar';
    var isExame  = p.tipo === 'exame';
    var badgeCls = isExame ? 'mm-price-badge mm-price-badge--exame' : 'mm-price-badge';
    var tipoLbl  = isExame
      ? '<span class="mm-pin-tipo" style="color:#065f46;">Exame</span>'
      : '<span class="mm-pin-tipo" style="color:#1e40af;">Consulta</span>';

    /* L.divIcon: Airbnb-style price pill reusing existing CSS class */
    var icon = L.divIcon({
      className: 'mm-leaflet-icon-wrap',
      html: '<div class="' + badgeCls + '" style="position:relative;animation-delay:' + (i * 60) + 'ms">' +
              tipoLbl +
              esc(label) +
            '</div>',
      iconSize:   null,
      iconAnchor: [0, 0],
    });

    var marker = L.marker([p.lat, p.lng], {
      icon:        icon,
      title:       p.nome || '',
      riseOnHover: true,
    }).addTo(map);

    /* Centre the badge on its coordinate after first render */
    marker.on('add', function () {
      var el = marker.getElement();
      if (!el) return;
      var badge = el.querySelector('.mm-price-badge');
      if (!badge) return;
      requestAnimationFrame(function () {
        var w = badge.offsetWidth  || 60;
        var h = badge.offsetHeight || 28;
        el.style.marginLeft = (-w / 2) + 'px';
        el.style.marginTop  = (-h / 2) + 'px';
      });
    });

    /* -- Build popup HTML -- */
    var imgSrc = p.img_url
      ? p.img_url
      : 'https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=320&h=180&fit=crop';

    var iwBadgeCls = isExame ? 'mm-iw-badge mm-iw-badge--exame' : 'mm-iw-badge mm-iw-badge--consulta';
    var iwBadgeLbl = isExame ? 'EXAME' : 'CONSULTA';

    var popupHtml =
      '<div class="mm-infowin">' +
        '<div class="mm-iw-img-wrap">' +
          '<img class="mm-iw-img" src="' + esc(imgSrc) + '" alt="' + esc(p.nome) + '" loading="lazy" />' +
          '<span class="' + iwBadgeCls + '">' + iwBadgeLbl + '</span>' +
        '</div>' +
        '<div class="mm-iw-body">' +
          '<p class="mm-iw-spec">' + esc(p.especialidade || 'Serviço Médico') + '</p>' +
          '<h4 class="mm-iw-name">' + esc(p.nome) + '</h4>' +
          '<p class="mm-iw-price">' + label + '</p>' +
          '<a class="mm-iw-btn" href="/listing/' + Number(p.id) + '">Agendar &#8594;</a>' +
        '</div>' +
      '</div>';

    marker.bindPopup(popupHtml, {
      maxWidth:  200,
      className: 'mm-leaflet-popup',
      offset:    L.point(0, -10),
    });

    /* -- Badge interaction -- */
    marker.on('click', function () {
      if (activeMarker && activeMarker !== marker) {
        var prevEl = activeMarker.getElement();
        if (prevEl) {
          var prevBadge = prevEl.querySelector('.mm-price-badge');
          if (prevBadge) prevBadge.classList.remove('mm-price-badge--active');
        }
      }
      activeMarker = marker;
      var el = marker.getElement();
      if (el) {
        var badge = el.querySelector('.mm-price-badge');
        if (badge) badge.classList.add('mm-price-badge--active');
      }
    });

    marker.on('popupclose', function () {
      var el = marker.getElement();
      if (el) {
        var badge = el.querySelector('.mm-price-badge');
        if (badge) badge.classList.remove('mm-price-badge--active');
      }
      if (activeMarker === marker) activeMarker = null;
    });
  });

  /* -- Fit bounds to show all markers -- */
  if (userLoc) {
    /* GPS mode: stay centred on the user; nearby pins are already visible */
    if (pts.length > 0) {
      var gpsBounds = L.latLngBounds([[userLoc.lat, userLoc.lng]].concat(
        pts.slice(0, 8).map(function (p) { return [p.lat, p.lng]; })
      ));
      map.fitBounds(gpsBounds, { padding: [50, 50], maxZoom: 14 });
    } else {
      map.setView([userLoc.lat, userLoc.lng], 13);
    }
  } else if (pts.length === 1) {
    map.setView([pts[0].lat, pts[0].lng], 14);
  } else if (pts.length > 1) {
    var bounds = L.latLngBounds(pts.map(function (p) { return [p.lat, p.lng]; }));
    map.fitBounds(bounds, { padding: [60, 40] });
  } else if (center) {
    map.setView([center.lat, center.lng], 11);
  }

  /* -- Fix grey-tile rendering after layout paint -- */
  setTimeout(function () { map.invalidateSize(); }, 150);

  hideLoader();

  /* -- Map panel close / open toggle -- */
  var toggleBtn = document.getElementById('vmMapToggle');
  var mapCol    = document.getElementById('vmMapCol');
  if (toggleBtn && mapCol) {
    toggleBtn.addEventListener('click', function () {
      mapCol.classList.toggle('vm-map--hidden');
      if (!mapCol.classList.contains('vm-map--hidden')) {
        setTimeout(function () { map.invalidateSize(); }, 200);
      }
    });
  }
})();
