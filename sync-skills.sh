#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="${SCRIPT_DIR}/inherit_skills"

sync_skills() {
    local provider="$1"    # claude, codex, kimi, droid, generic
    local dst_dir="$2"
    local src_dir="${SKILLS_SRC}/${provider}_skills"

    if [[ ! -d "${src_dir}" ]]; then
        echo "WARN: source dir not found: ${src_dir}"
        return 0
    fi

    mkdir -p "${dst_dir}"

    local count=0
    for skill_dir in "${src_dir}"/*/; do
        local skill_name
        skill_name="$(basename "${skill_dir}")"
        local dst_skill_dir="${dst_dir}/${skill_name}"

        # Prefer .bash variant for Claude, otherwise plain SKILL.md
        if [[ "${provider}" == "claude" && -f "${skill_dir}/SKILL.md.bash" ]]; then
            mkdir -p "${dst_skill_dir}"
            cp -f "${skill_dir}/SKILL.md.bash" "${dst_skill_dir}/SKILL.md"
        elif [[ -f "${skill_dir}/SKILL.md" ]]; then
            mkdir -p "${dst_skill_dir}"
            cp -f "${skill_dir}/SKILL.md" "${dst_skill_dir}/SKILL.md"
        else
            continue
        fi

        # Copy any additional files
        for extra in "${skill_dir}"/*; do
            local extra_name
            extra_name="$(basename "${extra}")"
            if [[ "${extra_name}" != "SKILL.md" && "${extra_name}" != "SKILL.md.bash" ]]; then
                cp -f "${extra}" "${dst_skill_dir}/${extra_name}"
            fi
        done

        echo "  ${skill_name}"
        ((count++))
    done

    echo "OK: ${count} ${provider} skills → ${dst_dir}"
}

echo "=== CCB Skill Sync ==="

# Claude
sync_skills "claude" "${HOME}/.claude/skills"

# Codex
CODEX_SKILLS="${CODEX_CONFIG_DIR:-${HOME}/.codex}/skills"
sync_skills "codex" "${CODEX_SKILLS}"

# Kimi
KIMI_SKILLS="${KIMI_CONFIG_DIR:-${HOME}/.kimi}/skills"
sync_skills "kimi" "${KIMI_SKILLS}"

# Droid
DROID_SKILLS="${DROID_CONFIG_DIR:-${HOME}/.droid}/skills"
sync_skills "droid" "${DROID_SKILLS}"

# Generic (shared across providers)
GENERIC_DST="${HOME}/.claude/skills"
sync_skills "generic" "${GENERIC_DST}"

echo
echo "=== Done ==="
