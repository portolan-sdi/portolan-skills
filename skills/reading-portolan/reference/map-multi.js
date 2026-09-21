// Draw two Portolan collections on one map.
// Each PMTILES_URL comes from that collection's rel: pmtiles link.
// Each "source-layer" comes from that link's pmtiles:layers array.
// When a collection ships a style asset, copy its layers[] entries
// and its paint expressions instead of writing new ones.

const PARKS_PMTILES = "https://example.com/catalog/parks/parks.pmtiles";
const BUILDINGS_PMTILES = "https://example.com/catalog/buildings/buildings.pmtiles";

const map = new maplibregl.Map({
    container: "map",
    style: {
        version: 8,
        sources: {
            parks: { type: "vector", url: "pmtiles://" + PARKS_PMTILES },
            buildings: { type: "vector", url: "pmtiles://" + BUILDINGS_PMTILES }
        },
        layers: [
            {
                id: "parks-fill",
                type: "fill",
                source: "parks",
                "source-layer": "parks",
                paint: { "fill-color": "#2d6a4f", "fill-opacity": 0.3 }
            },
            {
                id: "parks-outline",
                type: "line",
                source: "parks",
                "source-layer": "parks",
                paint: { "line-color": "#1b4332", "line-width": 2 }
            },
            {
                id: "buildings-fill",
                type: "fill",
                source: "buildings",
                "source-layer": "buildings",
                paint: {
                    "fill-color": ["match", ["get", "category"],
                        "residential", "#4361ee",
                        "industrial", "#e63946",
                        "office", "#f4a261",
                        "#999999"
                    ],
                    "fill-opacity": 0.7
                }
            }
        ]
    }
});
