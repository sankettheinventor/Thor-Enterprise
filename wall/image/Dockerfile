# THOR Room image (Module 1, the Wall) — one image, four task_types (FR-15).
# Minimal Linux + a cook runtime + git. Built UNGOVERNED; hardened further as we go (D2).
#
# Day-one scope matches the approved starter: a slim Python base with git so a cook can make
# a real commit (AC-1). The in-room Leash proxy (:8001) and skill-loader are added with the
# Leash (Module 2) — see PRD §2 (1.1 Image Builder) and the build-order note (§14).
FROM python:3.11-slim

# git so the cook can commit; the worktree is mounted in at runtime (FR-8).
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Unprivileged user — the container cannot weaken its own jail from inside (D2).
RUN useradd -m -u 1000 cook
USER cook
WORKDIR /work

# task slice is mounted read-only at /task/feature.json by the Mount Manager (FR-6).
# the cook's agent-server / entrypoint goes here as it's built (Module 2+).
ENTRYPOINT ["/bin/bash"]
