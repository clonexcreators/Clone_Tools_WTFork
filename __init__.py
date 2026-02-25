bl_info = {
    "name": "Clonex.WTFork",
    "author": "WTFork Community",
    "version": (2, 5, 0),
    "blender": (5, 0, 0),
    "description": "A community fork of Clone Tools - Enhanced CloneX 3D workflow addon",
    "category": "Animation",
    "support": "COMMUNITY",
    "doc_url": "https://github.com/wtfork/clonex-wtfork",
    "tracker_url": "https://github.com/wtfork/clonex-wtfork/issues"
}

if "bpy" in locals():
    import importlib
    importlib.reload(clone_tools_compat)
    importlib.reload(addon_updater_ops)
    importlib.reload(clone_tools_props)
    importlib.reload(clone_tools_ops)
    importlib.reload(clone_tools_ui)
else:
    from . import clone_tools_compat
    from . import addon_updater_ops
    from . import clone_tools_props
    from . import clone_tools_ops
    from . import clone_tools_ui

import bpy, os, csv
from pathlib import Path

def register():
    import bpy.utils.previews

    if bpy.app.version < (5, 0, 0):
        raise Exception(
            f"Clonex.WTFork requires Blender 5.0.0 or higher "
            + f"but the current version is {'.'.join(map(str, bpy.app.version))}"
        )

    preview_collections = {}

    pcoll = bpy.utils.previews.new()
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")
    pcoll.load('rtfkt_logo', os.path.abspath(os.path.join(icons_dir, 'rtfkt_logo_white_32x32.png')), 'IMAGE')
    preview_collections["main"] = pcoll

    bpy.types.WindowManager.preview_collections = preview_collections

    trait_catalog_dict = {}
    mapping_file_path = os.path.join(Path(__file__).resolve().parent, 'assets', 'catalog_trait_mapping.csv')

    with open(mapping_file_path, 'r') as data:
        for row in csv.DictReader(data, fieldnames=('trait_name','catalog_id')):
            trait_catalog_dict[row['trait_name'].lower()] = row['catalog_id']

    bpy.types.WindowManager.TRAIT_MAPPING = trait_catalog_dict

    addon_updater_ops.register(bl_info)    
    clone_tools_props.register()
    clone_tools_ops.register()
    clone_tools_ui.register()

def unregister():
    import bpy.utils.previews

    wm = bpy.context.window_manager if bpy.context and bpy.context.window_manager else None
    if wm and hasattr(wm, "preview_collections"):
        for pcoll in wm.preview_collections.values():
            bpy.utils.previews.remove(pcoll)
        wm.preview_collections.clear()

    if hasattr(bpy.types.WindowManager, "TRAIT_MAPPING"):
        del bpy.types.WindowManager.TRAIT_MAPPING

    clone_tools_ui.unregister()
    clone_tools_ops.unregister()
    clone_tools_props.unregister()
    addon_updater_ops.unregister()
    
if __name__ == "__main__":
    register()
