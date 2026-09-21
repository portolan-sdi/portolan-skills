---
name: bad
description: Fixture skill with one defect per check.
---
<!-- drift: depends-on: portolan-cli, rashid -->

```bash
# a comment line
portolan add . --nope
portolan init . --auto
```

Rule PTL-LNK-005 was removed in rashid 0.1.8.

<!-- drift-skip: exempt block, the flag below is on purpose -->
```bash
portolan add . --also-nope
```
