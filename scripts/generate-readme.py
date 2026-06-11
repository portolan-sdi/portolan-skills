#!/usr/bin/env python3
"""Generate README.md skills section from SKILL.md frontmatter."""

import re
import sys
from pathlib import Path


def extract_frontmatter(skill_path: Path) -> dict | None:
    """Extract YAML frontmatter from a SKILL.md file."""
    content = skill_path.read_text()
    match = re.match(r"^---\n(.+?)\n---", content, re.DOTALL)
    if not match:
        return None

    frontmatter = {}
    for line in match.group(1).strip().split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()
    return frontmatter


def generate_skills_section(skills_dir: Path) -> str:
    """Generate the ## Skills section from all SKILL.md files."""
    lines = ["## Skills", ""]

    skill_dirs = sorted(skills_dir.iterdir())
    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue

        fm = extract_frontmatter(skill_file)
        if not fm or "name" not in fm:
            continue

        lines.append(f"### `{fm['name']}`")
        lines.append("")
        if "description" in fm:
            lines.append(fm["description"])
            lines.append("")

    return "\n".join(lines)


def update_readme(readme_path: Path, skills_section: str) -> bool:
    """Update README.md with the generated skills section.

    Returns True if changes were made.
    """
    content = readme_path.read_text()

    # Find and replace the skills section between markers
    pattern = r"(<!-- BEGIN GENERATED: skills -->\n).+?(<!-- END GENERATED: skills -->)"
    replacement = rf"\1{skills_section}\n\2"

    new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)

    if count == 0:
        print("ERROR: Missing <!-- BEGIN/END GENERATED: skills --> markers in README.md")
        sys.exit(1)

    if new_content == content:
        return False

    readme_path.write_text(new_content)
    return True


def main():
    repo_root = Path(__file__).parent.parent
    skills_dir = repo_root / "skills"
    readme_path = repo_root / "README.md"

    skills_section = generate_skills_section(skills_dir)
    changed = update_readme(readme_path, skills_section)

    if changed:
        print("README.md updated")
    else:
        print("README.md already up to date")

    # Exit with code 1 if --check flag and changes needed
    if "--check" in sys.argv and changed:
        sys.exit(1)


if __name__ == "__main__":
    main()
