from walkshed_web.routers import data, health, lines, meta, pages, search, stations

ALL_ROUTERS = (
    health.router,
    meta.router,
    lines.router,
    stations.router,
    search.router,
    data.router,
    pages.router,
)
