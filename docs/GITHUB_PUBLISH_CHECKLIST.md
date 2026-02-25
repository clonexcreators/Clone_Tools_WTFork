# GitHub Publish Checklist

## Scope
This repository is configured to publish:
- addon source code
- docs
- pose libraries under `content_packs/poses/**`

Large character/build payloads are intentionally ignored.

## Pre-push checks
1. Confirm `.gitignore` is present and excludes `build/`, `publish/`, and `crash_logs/`.
2. Run a quick syntax check:
   - `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile __init__.py clone_tools_compat.py clone_tools_props.py clone_tools_utils.py clone_tools_ops.py clone_tools_ui.py addon_updater_ops.py`
3. Verify addon metadata/version in `__init__.py` and `CHANGELOG.md`.
4. Ensure `README.md` reflects Blender version support and setup steps.
5. Confirm attribution files/notes are present and accurate:
   - `CREDITS.md`
   - `README.md` Attribution section

## Initialize and commit
1. `git init`
2. `git add .`
3. `git status` (confirm no large payload dirs are staged)
4. `git commit -m "Prepare CloneX WTFork addon source for GitHub publish"`

## Connect remote and push
1. `git branch -M main`
2. `git remote add origin <your-github-repo-url>`
3. `git push -u origin main`

## Optional: publish binaries
If you want to distribute large sample assets/content packs:
- Use GitHub Releases attachments, or
- External storage (Drive/S3), and link from `README.md`.
