"""Convert graduated (class-break) SLDs into MapLibre `step` expressions.

From pergamino-ide-catalog (tools/generate/sld_graduated.py). Generalized as
a reference; edit the constants under "What a new catalog must change".

The Portolan CLI's SLD converter handles categorical rules. A filter of the
form `PropertyIsEqualTo` becomes a `match` expression. It rejects graduated
styles, whose rules carry a range filter instead:

    <ogc:And>
      <ogc:PropertyIsGreaterThan>       <field> > 0
      <ogc:PropertyIsLessThanOrEqualTo> <field> <= 3.4725

In the Pergamino migration those were the demographic indicator layers, which
carry the most considered cartography in that catalog: an 8-class ramp on one
index, a 10-class ramp on another.

A `step` expression is the right target rather than `interpolate`, because a
step can be summarised into a legend mechanically, which is how
portolan-browser derives one from the style body.
"""

import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------
# What a new catalog must change.
# --------------------------------------------------------------------------

# Stripped from the generated style name. Upstream layer names often carry a
# workspace or visibility prefix that should not reach the style.
LAYER_NAME_PREFIX = "<layer-name-prefix>_"

# Fallback paint values for the geometry kinds the SLD does not specify.
FILL_OUTLINE_COLOUR = "#ffffff"
LINE_WIDTH = 1.5
CIRCLE_RADIUS = 5

# --------------------------------------------------------------------------

NS = {
    "sld": "http://www.opengis.net/sld",
    "ogc": "http://www.opengis.net/ogc",
    "se": "http://www.opengis.net/se",
}


def _txt(el):
    return (el.text or "").strip() if el is not None else ""


def _css(sym, name):
    if sym is None:
        return None
    for p in sym.iter():
        if p.tag.endswith("CssParameter") or p.tag.endswith("SvgParameter"):
            if p.get("name") == name:
                return _txt(p)
    return None


def _bounds(rule):
    """Lower bound of a rule's range filter, and whether it is open-ended."""
    lo = hi = None
    for el in rule.iter():
        tag = el.tag.split("}")[-1]
        lit = el.find("ogc:Literal", NS)
        if lit is None:
            for c in el:
                if c.tag.endswith("Literal"):
                    lit = c
        if lit is None:
            continue
        try:
            v = float(_txt(lit))
        except ValueError:
            continue
        if tag in ("PropertyIsGreaterThan", "PropertyIsGreaterThanOrEqualTo"):
            lo = v if lo is None else min(lo, v)
        elif tag in ("PropertyIsLessThan", "PropertyIsLessThanOrEqualTo"):
            hi = v if hi is None else max(hi, v)
    return lo, hi


def _field(rule):
    for el in rule.iter():
        if el.tag.endswith("PropertyName"):
            return _txt(el)
    return None


def convert_graduated(sld_xml, source_layer):
    """Return a MapLibre style dict, or None when the SLD is not graduated."""
    root = ET.fromstring(sld_xml)
    rules = [r for r in root.iter() if r.tag.endswith("}Rule")]
    if len(rules) < 2:
        return None

    classes, field, geom = [], None, None
    for r in rules:
        lo, hi = _bounds(r)
        if lo is None and hi is None:
            continue
        f = _field(r)
        if f and not field:
            field = f
        poly = next((s for s in r if s.tag.endswith("PolygonSymbolizer")), None)
        line = next((s for s in r if s.tag.endswith("LineSymbolizer")), None)
        point = next((s for s in r if s.tag.endswith("PointSymbolizer")), None)
        if poly is not None:
            geom, colour = "fill", _css(poly, "fill")
            opacity = _css(poly, "fill-opacity")
        elif line is not None:
            geom, colour = "line", _css(line, "stroke")
            opacity = _css(line, "stroke-opacity")
        elif point is not None:
            geom, colour = "circle", _css(point, "fill")
            opacity = _css(point, "fill-opacity")
        else:
            continue
        if not colour:
            continue
        classes.append((lo if lo is not None else float("-inf"), colour,
                        float(opacity) if opacity else 1.0))

    if not field or len(classes) < 2:
        return None
    classes.sort(key=lambda c: c[0])

    expr = ["step", ["get", field], classes[0][1]]
    for lo, colour, _ in classes[1:]:
        expr += [lo, colour]

    opacity = classes[0][2]
    if geom == "fill":
        paint = {"fill-color": expr, "fill-opacity": opacity,
                 "fill-outline-color": FILL_OUTLINE_COLOUR}
    elif geom == "line":
        paint = {"line-color": expr, "line-width": LINE_WIDTH,
                 "line-opacity": opacity}
    else:
        paint = {"circle-color": expr, "circle-radius": CIRCLE_RADIUS,
                 "circle-opacity": opacity}

    return {
        "version": 8,
        "name": source_layer.replace(LAYER_NAME_PREFIX, ""),
        "sources": {"data": {"type": "vector"}},
        "layers": [{
            "id": f"graduated-{geom}",
            "type": geom,
            "source": "data",
            "source-layer": source_layer,
            "paint": paint,
        }],
    }, field, len(classes)
