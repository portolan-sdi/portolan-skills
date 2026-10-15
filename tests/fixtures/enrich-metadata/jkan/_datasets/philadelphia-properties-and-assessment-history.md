---
category:
- Real Estate / Land Records
license: City of Philadelphia License
maintainer: maps@phila.gov
maintainer_email: opadata@phila.gov
notes: "***This data updates nightly.*** Property characteristic and assessment history\
  \ from the Office of Property Assessment for all properties in Philadelphia."
organization: City of Philadelphia
resources:
- format: HTML
  name: Properties (Visualization)
  url: https://data.phila.gov/visualizations/property-assessments
- format: CSV
  name: Properties  (CSV)
  url: https://opendata-downloads.s3.amazonaws.com/opa_properties_public.csv
- format: GeoJSON
  name: Properties (GeoJSON)
  url: https://phl.carto.com/api/v2/sql?filename=opa_properties_public&format=geojson&skipfields=cartodb_id&q=SELECT+*+FROM+opa_properties_public
- format: API
  name: Properties  (API)
  url: https://cityofphiladelphia.github.io/carto-api-explorer/#opa_properties_public
- format: CSV
  name: Property Assessment History (CSV)
  url: https://opendata-downloads.s3.amazonaws.com/assessments.csv
- format: API
  name: Property Assessment History (API)
  url: https://cityofphiladelphia.github.io/carto-api-explorer/#assessments
tags:
- Office of Property Assessment
- assessment
- properties
title: Philadelphia Properties and Assessment History
---
