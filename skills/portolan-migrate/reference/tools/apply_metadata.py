"""Apply per-collection metadata that `portolan add` cannot derive.

From pergamino-ide-catalog (tools/generate/apply_metadata.py). Generalized as
a reference; edit the constants under "What a new catalog must change".

Run this LAST, after every `add` invocation. `add` regenerates collection.json
and, through the hierarchical metadata.yaml resolution, overwrites each
collection's title with the catalog root's title. It also rewrites
stac_extensions with the schema version the CLI ships rather than the one the
current spec release defines.

Everything here is idempotent and derived from the harvested upstream metadata,
so it can be re-run after any add.
"""

import json
import os
import sys
from datetime import datetime, timezone

DST = sys.argv[1]
META = json.load(open(sys.argv[2], encoding="utf-8"))

# --------------------------------------------------------------------------
# What a new catalog must change.
# --------------------------------------------------------------------------

# The profile schema version the current spec release defines. Every object in
# the tree, root included, must declare the same one.
SCHEMA = "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"

ROOT_ID = "<catalog-id>"
ROOT_TITLE = "<Catalog Title>"

# Placeholder for the sibling `grouping` module, which the real catalog keeps
# in its own file because the list is long and is audited by hand. It maps each
# sub-catalog directory to the upstream layer names that belong in it. Explicit
# rather than pattern-matched, because a misfiled collection is a permanent id
# change. The real module also carries an EXCLUDED mapping of layer name to the
# reason it was not mirrored.
GROUPS = {
    "<group-directory>": ["<upstream_layer_name>", "<upstream_layer_name>"],
}

# Placeholder for the sibling `group_descriptions` module. It maps an upstream
# layer name to a (title, description) pair, hand-written in the publisher's
# own language for the layers whose upstream abstract is missing or useless.
HAND_WRITTEN = {
    "<upstream_layer_name>": ("<Title>", "<Description>"),
}

PROVIDER_PUBLISHER = {
    "name": "<Upstream publisher>",
    "description": "<Department or unit inside the publisher>",
    "roles": ["producer", "licensor"],
    "url": "<https://publisher-url>",
}
PROVIDER_HOST = {
    "name": "<Host>",
    "roles": ["host"],
    "url": "<https://host-url>",
    "email": "<email>",
}

# Upstream credits a third-party originator in a free-text attribution field.
# Map the token it uses to a full name and a URL, so the credit survives as a
# structured provider entry. Anything not listed here is dropped.
ORIGINATORS = {
    "<TOKEN>": ("<Full organisation name>", "<https://url or None>"),
}

# Titles that would otherwise render as a raw slug.
TITLE_OVERRIDES = {
    "<upstream_layer_name>": "<Title>",
}

# Upstream metadata keys to try, in order, for a title and a description. These
# come from the harvest step and depend on the source server.
TITLE_KEYS = ("gn_title", "wfs_title")
DESCRIPTION_KEYS = ("gn_abstract", "wfs_abstract")
ATTRIBUTION_KEY = "gn_attribution"

# Links added to the catalog root if absent.
ROOT_LINKS = (
    {"rel": "agents", "href": "./AGENTS.md", "type": "text/markdown",
     "title": "<Agent guide>"},
    {"rel": "describedby", "href": "./README.md", "type": "text/markdown",
     "title": "<Documentation>"},
    {"rel": "via", "href": "<https://upstream-source-url>",
     "type": "text/html", "title": "<Upstream source>"},
)

# --------------------------------------------------------------------------


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def leaf_name(group, layer):
    prefix = group.split("-")[0] + "_"
    if layer.startswith(prefix) and len(layer) > len(prefix):
        return layer[len(prefix):]
    return layer


def title_for(layer):
    if layer in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[layer]
    if layer in HAND_WRITTEN:
        return HAND_WRITTEN[layer][0]
    m = META.get(layer, {}) or {}
    for key in TITLE_KEYS:
        t = (m.get(key) or "").strip()
        if t and t.lower().replace(" ", "_") != layer.lower():
            return t
    return layer.replace("_", " ").capitalize()


def description_for(layer, existing):
    if layer in HAND_WRITTEN:
        return HAND_WRITTEN[layer][1]
    m = META.get(layer, {}) or {}
    for key in DESCRIPTION_KEYS:
        v = (m.get(key) or "").strip()
        if v:
            return v
    return existing


def providers_for(layer):
    attr = (META.get(layer, {}) or {}).get(ATTRIBUTION_KEY, "") or ""
    # The first comma-separated token is the publisher itself, already covered
    # by PROVIDER_PUBLISHER, so only the rest are looked up.
    parts = [p.strip() for p in attr.split(",")[1:] if p.strip()]
    extra = []
    for p in parts:
        if p in ORIGINATORS:
            name, url = ORIGINATORS[p]
            e = {"name": name, "roles": ["producer", "licensor"]}
            if url:
                e["url"] = url
            extra.append(e)
    if not extra:
        return [dict(PROVIDER_PUBLISHER), dict(PROVIDER_HOST)]
    # A third party produced the data, so the publisher is only a processor.
    publisher = dict(PROVIDER_PUBLISHER)
    publisher["roles"] = ["processor"]
    return extra + [publisher, dict(PROVIDER_HOST)]


def main():
    changed = 0
    for group, layers in GROUPS.items():
        gdir = os.path.join(DST, group)
        child_links = []
        for layer in sorted(layers):
            leaf = leaf_name(group, layer)
            cpath = os.path.join(gdir, leaf, "collection.json")
            if not os.path.exists(cpath):
                print(f"  missing: {group}/{leaf}", file=sys.stderr)
                continue
            col = json.load(open(cpath, encoding="utf-8"))
            col["id"] = f"{group}/{leaf}"
            col["title"] = title_for(layer)
            col["description"] = description_for(layer, col.get("description", ""))
            col["providers"] = providers_for(layer)
            col["updated"] = now()

            ext = [e for e in col.get("stac_extensions", []) if "portolan" not in e]
            col["stac_extensions"] = sorted(set(ext + [SCHEMA]))

            links = []
            for ln in col.get("links", []):
                if ln.get("rel") == "self":
                    continue
                if ln.get("rel") == "root":
                    ln["href"] = "../../catalog.json"
                elif ln.get("rel") == "parent":
                    ln["href"] = "../catalog.json"
                links.append(ln)
            col["links"] = links

            json.dump(col, open(cpath, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            changed += 1
            child_links.append({
                "rel": "child",
                "href": f"./{leaf}/collection.json",
                "type": "application/json",
                "title": col["title"],
            })

        gcat_path = os.path.join(gdir, "catalog.json")
        gcat = json.load(open(gcat_path, encoding="utf-8"))
        gcat["links"] = [l for l in gcat["links"] if l.get("rel") != "child"]
        insert = next((i for i, l in enumerate(gcat["links"])
                       if l.get("rel") in ("agents", "describedby")), len(gcat["links"]))
        gcat["links"][insert:insert] = child_links
        gcat["stac_extensions"] = [SCHEMA]
        gcat["updated"] = now()
        json.dump(gcat, open(gcat_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    # The root must declare the same profile schema version as everything under
    # it. Rashid resolves the profile from the root and validates every object
    # against that one, so a root left on an older version fails the whole tree.
    rpath = os.path.join(DST, "catalog.json")
    root = json.load(open(rpath, encoding="utf-8"))
    root["stac_extensions"] = [SCHEMA]
    root["id"] = ROOT_ID
    root["title"] = ROOT_TITLE
    root["updated"] = now()
    root["links"] = [l for l in root.get("links", []) if l.get("rel") != "self"]
    have = {(l.get("rel"), l.get("href")) for l in root["links"]}
    for extra in ROOT_LINKS:
        if (extra["rel"], extra["href"]) not in have:
            root["links"].append(dict(extra))
    json.dump(root, open(rpath, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)

    print(f"applied metadata to {changed} collections, "
          f"{len(GROUPS)} sub-catalogs, and the root")


if __name__ == "__main__":
    main()
