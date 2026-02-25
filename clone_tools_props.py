import bpy, os

from bpy.props import (
    StringProperty, 
    IntProperty, 
    BoolProperty, 
    FloatProperty,
    EnumProperty, 
    CollectionProperty, 
    PointerProperty
)
from bpy.types import Object, Collection, PropertyGroup, Scene, AddonPreferences
from bpy.utils import register_class, unregister_class

from . import addon_updater_ops
from . import clone_tools_utils as ctutils
from .lib.easybpy import *
from pathlib import Path
from bpy.app.handlers import persistent

@persistent
def asset_library_sync_handler(scene, depsgraph):
    if depsgraph is None:
        return

    style_lib_path = ''
    for al in bpy.context.preferences.filepaths.asset_libraries:
        if al.name == 'CloneX Style Library':
            style_lib_path = al.path
            break

    if not style_lib_path:
        return

    for update in depsgraph.updates:
        if isinstance(update.id, Collection):
            coll = get_collection(update.id.name)
            if coll and coll.asset_data:
                ctutils.request_style_library_sync(style_lib_path)
                break

@addon_updater_ops.make_annotations
class CloneToolsPreferences(AddonPreferences):
    bl_idname = __package__

    style_library_path = StringProperty(
        name='clone.tools style library path',
        subtype='DIR_PATH',
        default=''
    )

    content_packs_path = StringProperty(
        name='CloneTools Content Packs Path',
        subtype='DIR_PATH',
        default='',
        update=ctutils.refresh_content_packs
    )

    auto_check_update = BoolProperty(
		name="Auto-check for update",
		description="If enabled, auto-check for updates using an interval",
		default=True,
	)
    updater_interval_months = IntProperty(
		name='Months',
		description="Number of months between checking for updates",
		default=0,
		min=0
	)
    updater_interval_days = IntProperty(
		name='Days',
		description="Number of days between checking for updates",
		default=1,
		min=0,
	)
    updater_interval_hours = IntProperty(
		name='Hours',
		description="Number of hours between checking for updates",
		default=0,
		min=0,
		max=23
	)
    updater_interval_minutes = IntProperty(
		name='Minutes',
		description="Number of minutes between checking for updates",
		default=0,
		min=0,
		max=59
	)

    # def draw(self, context):
    #     addon_updater_ops.update_settings_ui(self,context)

class SceneLightsPropertyGroup(PropertyGroup):
    name: StringProperty()
    lighting_selected: BoolProperty(default=False, update=ctutils.update_lighting_selected)

class CloneTraitPropertyGroup(PropertyGroup):
    name: StringProperty(default='', subtype='NONE', maxlen=0)
    trait_dir: StringProperty(default='', subtype='NONE', maxlen=0)
    trait_selected: BoolProperty(default=False, update=ctutils.update_trait_selected) 

class CharSheetShotPropertyGroup(PropertyGroup):
    name: StringProperty(default='')
    file_path: StringProperty(default='', subtype='FILE_PATH')
    include_in_sheet: BoolProperty(default=True)
    scale: FloatProperty(
        name='Scale',
        description='Per-shot scale factor in stitched sheet',
        default=1.0,
        min=0.1,
        max=3.0
    )

class ClonePropertyGroup(PropertyGroup):
    home_dir: StringProperty(default='', subtype='NONE')
    gender: EnumProperty(
        items=[('male', 'Male', ''),('female', 'Female', '')],
        update=ctutils.update_gender_content_pack
    )
    import_type: EnumProperty(items=[('blend', 'BLEND', ''),('glb', 'GLB', '')])
    files_loaded: BoolProperty(default=False)
    trait_collection: CollectionProperty(type=CloneTraitPropertyGroup)
    trait_collection_index: IntProperty(default=0)
    asset_catalog_names: EnumProperty(items=ctutils.get_asset_catalog_names)
    show_facial_feature: BoolProperty(
        name='Show Facial Feature', 
        description='Show or hide face tattoos, band-aids, scars, birth marks, etc',
        default=True, 
        update=ctutils.update_facial_feature
    )
    use_realistic_skin: BoolProperty(
        name='Realistic Skin', 
        description='Uses Subsurface Scattering to give skin a more realistic look by adjusting translucency', 
        default=False,
        update=ctutils.update_realistic_skin
    )
    
    # === ENHANCED CLONE TOOLS SETTINGS ===
    auto_fix_scale: BoolProperty(
        name='Auto-Fix Scale',
        description='Automatically detect and fix scale mismatches during import',
        default=True
    )
    auto_position_traits: BoolProperty(
        name='Auto-Position Traits',
        description='Automatically position traits on character during import',
        default=False
    )
    auto_register_traits: BoolProperty(
        name='Auto-Register Traits',
        description='Automatically register all traits in Style panel during import',
        default=True
    )
    show_import_validation: BoolProperty(
        name='Show Import Validation',
        description='Display detailed validation results after import',
        default=True
    )

class CloneToolsGlobalPropertyGroup(PropertyGroup):
    env_loaded: BoolProperty(default=False)
    poses_loaded: BoolProperty(default=False)
    setup_finished: BoolProperty(default=False)
    export_mesh_only: BoolProperty(default=True)
    style_lib_initialized: BoolProperty(default=False)
    lights_collection: CollectionProperty(type=SceneLightsPropertyGroup)
    lights_collection_index: IntProperty(default=0)
    style_asset_index: IntProperty(default=0)
    staging_options: EnumProperty(
        name='Staging Options',
        description='Backgrounds and other staging items',
        items=[
            ('LightCatcherPreset', 'Light Catcher', 'Staging Preset'),
            ('SkyboxPreset', 'Skybox', 'Staging Preset')
        ],
        update=ctutils.update_staging_options
    )
    pose_or_animate: EnumProperty(
        name='Pose or Animate',
        description='Select whether to display poses or animations',
        items=[
            ('pose', 'POSE', 'Show Poses'),
            ('animate', 'ANIMATE', 'Show Animations')
        ],
        update=ctutils.refresh_pose_panel,
        default='pose'
    )
    use_bloom: BoolProperty(
        name='Bloom',
        description='High brightness pixels generate a glowing effect',
        default=False,
        update=ctutils.update_bloom
    )
    use_transparent: BoolProperty(
        name='Transparent',
        description='World background is transparent, for rendering over another background',
        default=False,
        update=ctutils.update_transparent
    )
    charsheet_preset: EnumProperty(
        name='Character Sheet Preset',
        description='Naming preset for character sheet renders',
        items=[
            ('A_POSE', 'A-Pose', 'A-Pose sheet naming'),
            ('T_POSE', 'T-Pose', 'T-Pose sheet naming'),
            ('ACTION_POSE', 'Action Pose', 'Action pose sheet naming'),
            ('CUSTOM', 'Custom', 'Custom sheet naming')
        ],
        default='CUSTOM'
    )
    charsheet_output_path: StringProperty(
        name='Character Sheet Output',
        subtype='DIR_PATH',
        default='//renders/character_sheet/'
    )
    charsheet_transparent_bg: BoolProperty(
        name='Transparent Background',
        description='Render PNGs with alpha background',
        default=True
    )
    charsheet_body_views: IntProperty(
        name='Body Views',
        description='Number of full-body orbit cameras',
        default=8,
        min=4,
        max=24
    )
    charsheet_include_closeups: BoolProperty(
        name='Include Closeups',
        description='Add three head closeup views',
        default=True
    )
    charsheet_build_page: BoolProperty(
        name='Build One-Page Sheet',
        description='Assemble all rendered views into a single contact sheet PNG',
        default=True
    )
    charsheet_page_columns: IntProperty(
        name='Sheet Columns',
        description='Number of columns in the one-page sheet',
        default=4,
        min=1,
        max=12
    )
    charsheet_shots: CollectionProperty(type=CharSheetShotPropertyGroup)
    charsheet_shot_index: IntProperty(default=0)

classes = (
    SceneLightsPropertyGroup,
    CloneToolsPreferences,
    CloneTraitPropertyGroup,
    CharSheetShotPropertyGroup,
    ClonePropertyGroup,
    CloneToolsGlobalPropertyGroup
)

def register():
    for cls in classes:
        register_class(cls)

    Scene.clone_props = PointerProperty(type=ClonePropertyGroup)
    bpy.types.WindowManager.ctglobals = PointerProperty(type=CloneToolsGlobalPropertyGroup)

    if asset_library_sync_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(asset_library_sync_handler)
    
def unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    del bpy.types.WindowManager.ctglobals
    del Scene.clone_props

    if asset_library_sync_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(asset_library_sync_handler)
