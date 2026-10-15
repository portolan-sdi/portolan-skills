# Grader on Sonnet 5.5 instead of Opus 5.5

The catalog-grader skill runs on claude-sonnet-5-5 at effort high. The
baseline runs on claude-opus-5-5 at effort high. The skill files do not
change. The judge is claude-opus-5-5 here, because the judge must not be the
model under test. The baseline judge is claude-sonnet-5-5.
