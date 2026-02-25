# Clone Tools WTFork (Blender 5.0+)

Community-maintained fork of the original Clone Tools addon for CloneX workflows in Blender.

## Attribution
- Original project: **Clone Tools** by **RTFKT**.
- This fork preserves original attribution and extends the addon for current Blender workflows.
- See [CREDITS.md](./CREDITS.md) for attribution details.

## Compatibility
- Blender: **5.0.0+**
- Python (bundled with Blender 5): supported

## What This Repo Includes
- Addon source code (`__init__.py`, `clone_tools_*.py`, updater modules, `lib/`)
- Bundled pose libraries:
  - `content_packs/poses/male/male_pose_pack.blend`
  - `content_packs/poses/female/female_pose_pack.blend`
- Addon assets/icons/docs used by the addon and documentation
- Build helper scripts (`build_addon*.ps1`, `build_addon.bat`)

## What This Repo Does Not Include
- CloneX character source zips / large character build payloads
- Local crash logs and local test artifacts

## Install From This Repo

### Method 1: Install via GitHub ZIP (recommended)
1. Open this repo on GitHub: `clonexcreators/Clone_Tools_WTFork`.
2. Click **Code > Download ZIP**.
3. In Blender 5.0: **Edit > Preferences > Add-ons > Install...**
4. Select the downloaded ZIP file (do not extract first).
5. Enable the addon in the Add-ons list.

### Method 2: Install by copying source folder
1. Clone the repository:
   ```bash
   git clone https://github.com/clonexcreators/Clone_Tools_WTFork.git
   ```
2. Copy the repo folder into Blender addons path as `clonex_wtfork`.
   - Windows: `%APPDATA%\Blender Foundation\Blender\5.0\scripts\addons\clonex_wtfork`
   - macOS: `~/Library/Application Support/Blender/5.0/scripts/addons/clonex_wtfork`
   - Linux: `~/.config/blender/5.0/scripts/addons/clonex_wtfork`
3. Restart Blender.
4. Enable **Clonex.WTFork** in Add-ons.

## Pose Libraries
- Male and female pose libraries are included in this repo under `content_packs/poses/`.
- After addon enable/import workflow, poses are available from the addon Pose & Animate panel.

## Quick Verification
1. Open Blender 5.0 and enable the addon.
2. Import CloneX assets via the addon panel.
3. Go to **Pose & Animate**:
   - Choose `POSE`
   - Select content pack (`[RTFKT] Male Poses` or `[RTFKT] Female Poses`)
   - Pick a pose from dropdown and click **Apply Pose**

## License
This project is distributed under **GNU GPL v3.0**. See [LICENSE](./LICENSE).

## Support / Issues
- GitHub Issues: https://github.com/clonexcreators/Clone_Tools_WTFork/issues
