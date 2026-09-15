# Vendored Leaflet 1.9.4

Source: https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/
License: BSD-2-Clause, © Volodymyr Agafonkin and contributors.

Vendored so the page's Content-Security-Policy can stay at `script-src 'self'`
with no CDN allowance.

| File | Subresource integrity |
|---|---|
| `leaflet.js` | `sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=` |
| `leaflet.css` | `sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=` |

The `images/` folder is copied whole so the stylesheet's relative icon paths resolve.
