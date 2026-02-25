import bpy, os

from pathlib import Path
from bpy.props import EnumProperty
from bpy.types import Panel, UIList, Context, WindowManager
from bpy.utils import register_class, unregister_class

from . import clone_tools_ops as ctops
from . import clone_tools_utils as ctutils
from . import addon_updater_ops
from .clone_tools_compat import get_asset_id_type, get_asset_name, get_context_asset

from .lib.easybpy import *

class CT_BasePanel:
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Clonex.WTFork'

class CT_PT_AssemblePanel(CT_BasePanel, Panel):
    bl_label = 'Clonex.WTFork'
    bl_idname = 'CT_PT_assemble_panel'
    
    @classmethod
    def poll(cls, context):
        return context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}

    def draw_header(self, context):
        pcoll = context.window_manager.preview_collections['main']
        rtfkt_logo_icon = pcoll['rtfkt_logo']
        self.layout.label(text='', icon_value=rtfkt_logo_icon.icon_id)
        
    def draw(self, context):
        layout = self.layout

        # try:
        #     addon_updater_ops.update_notice_box_ui(self, context)
        # except:
        #     pass

        # Row for gender selection
        row_gender_heading = layout.row()
        row_gender_heading.label(text="Select Clone Gender")

        row_gender_buttons = layout.row()
        row_gender_buttons.scale_y = 1.5
        row_gender_buttons.prop(get_scene().clone_props, 'gender', expand=True)
       
        # Row for Clone select button
        row_button = layout.row()
        row_button.scale_y = 1.5
        row_button.enabled = True
        row_button.active = True
        row_button.operator(
            ctops.CT_OT_CloneSelectOperator.bl_idname, 
            text='Open Clone 3D Files', 
            depress=True, 
            emboss=True, 
            icon='FILE_FOLDER'
        )

class CT_UL_TraitList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        
        checkbox = "CHECKBOX_HLT" if item.trait_selected else "CHECKBOX_DEHLT"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.alignment = 'LEFT'
            layout.prop(item, 'trait_selected', text=item.name, emboss=False, icon=checkbox)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text='', icon_value=icon)

class CT_PT_StylePanel(CT_BasePanel, Panel):
        bl_label = 'Style'
        bl_idname = 'CT_PT_style_panel'
        bl_options = {"DEFAULT_CLOSED"}

        @classmethod
        def poll(cls, context):
            return bool(
                context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
                and get_scene().clone_props.files_loaded
            )

        def draw_header(self, context):
            self.layout.label(text='', icon='MOD_CLOTH')

        def draw(self, context):
            clone_props = get_scene().clone_props
            wm = context.window_manager
            ctglobals = wm.ctglobals
            prefs = context.preferences.addons[__package__].preferences

            layout = self.layout

            if not ctglobals.style_lib_initialized:
                layout.label(text='Style Library Path')
                row = layout.row()
                row.prop(prefs, 'style_library_path', text='')
                row = layout.row()
                row.operator(
                    ctops.CT_OT_InitStyleLibraryButton.bl_idname,
                    text='Create Style Library',
                    depress=True,
                    emboss=True
                )

            if ctglobals.style_lib_initialized:
                row = layout.row()
                row.operator('ct.open_style_library_button', text='Open Style Library', icon='ASSET_MANAGER')

                # row = layout.row()
                # row.operator(
                #     ctops.CT_OT_SyncStyleLibraryButton.bl_idname,
                #     text='Sync Style Library',
                #     emboss=True,
                #     icon='FILE_REFRESH')

                row = layout.row()
                row.operator('ct.import_style_button', text='Import New Style', icon='IMPORT')

            layout.label(text=f"Currently Equipped ({len(clone_props.trait_collection)})")
            grid = layout.grid_flow(row_major=True, columns=0)

            for trait in clone_props.trait_collection:
                cell = grid.box()
                try:
                    cell.template_icon(get_collection(trait.name).preview.icon_id, scale=4)
                    row = cell.row()
                    row.alignment = 'CENTER'
                    row.scale_x = 1
                    row.label(text=trait.name)
                    row = cell.row()
                    row.operator('ct.unequip_wearable_operator', text='Remove', icon='CANCEL').wearable_name = trait.name
                    row.operator('ct.object_zoom_operator', text='View', icon='VIEW_ZOOM').wearable_name = trait.name
                except:
                    # This is probably a material
                    cell.template_icon(get_material(trait.name).preview.icon_id, scale=4)
                    cell.label(text=trait.name)
                    cell.operator('ct.unequip_wearable_operator', text='Remove', icon='CANCEL').wearable_name = trait.name

class CT_PT_PoseAndAnimatePanel(CT_BasePanel, Panel):
    bl_label = 'Pose & Animate'
    bl_idname = 'CT_PT_pose_and_animate_panel'
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):      
        return bool(
            context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
        ) 

    def draw_header(self, context):
        self.layout.label(text='', icon='ARMATURE_DATA')

    # Code lifted from official Pose Library add-on 
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        ctglobals = wm.ctglobals

        if not ctglobals.poses_loaded:
            row = layout.row()
            row.scale_y = 1.5
            row.operator(
                ctops.CT_OT_LoadPosesOperator.bl_idname, 
                text='Load Pose Library', 
                depress=True, 
                emboss=True, 
                icon='ARMATURE_DATA'
            )    
        else:
            if context.mode != 'POSE':
                # Add a button to switch to POSE mode
                row = layout.row()
                row.scale_y = 1.5
                row.operator(
                    ctops.CT_OT_PoseModeButton.bl_idname, 
                    text="Switch to Pose Mode", 
                    depress=True, icon='POSE_HLT'
                )
            else:
                row = layout.row()
                row.prop(ctglobals, 'pose_or_animate', expand=True, emboss=True)

                if context.mode == 'POSE':
                    content_pack_name = 'content_pack_poses'
                    if ctglobals.pose_or_animate == 'animate':
                        content_pack_name = 'content_pack_anims'

                    row = layout.row()
                    row.prop(wm, content_pack_name, text='')
                    row.operator(
                        ctops.CT_OT_RefreshContentPacks.bl_idname,
                        text='',
                        icon='FILE_REFRESH').sync_type = ctglobals.pose_or_animate

                    if ctglobals.pose_or_animate == 'pose':
                        row = layout.row()
                        row.prop(wm, 'selected_pose_action', text='Pose')
                        apply_row = layout.row()
                        apply_row.scale_y = 1.2
                        apply_row.operator('animation.apply_pose_from_dropdown', text='Apply Pose', icon='POSE_HLT')

                    box = layout.box()
                    box.label(text='Use Asset Browser to select pose/animation assets.', icon='ASSET_MANAGER')
                    if ctglobals.pose_or_animate == 'animate':
                        box.label(text='Right-click an animation asset to Apply/Append.', icon='INFO')
                    else:
                        box.label(text='Use pose library actions from the Asset Browser.', icon='INFO')

class CT_PT_PoseSubPanel(CT_BasePanel, Panel):
    bl_label = 'Pose'
    bl_idname = 'CT_PT_pose_sub_panel'
    bl_parent_id = 'CT_PT_pose_and_animate_panel'
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):      
        if context.mode not in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}:
            return False

        if context.window_manager.ctglobals.pose_or_animate == 'animate':
            return False

        return True

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        if context.mode == 'POSE':
            row = layout.row()
            row.prop(wm, 'content_pack_poses', text='')
            row.operator(ctops.CT_OT_RefreshContentPacks.bl_idname, text='', icon='FILE_REFRESH').sync_type = 'pose'
            layout.label(text='Browse pose assets in the Asset Browser.', icon='INFO')

class CT_PT_AnimateSubPanel(CT_BasePanel, Panel):
    bl_label = 'Animation'
    bl_idname = 'CT_PT_animation_sub_panel'
    bl_parent_id = 'CT_PT_pose_and_animate_panel'
    bl_options = {"DEFAULT_CLOSED"}
    
    @classmethod
    def poll(cls, context):      
        if context.mode not in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}:
            return False

        if context.window_manager.ctglobals.pose_or_animate == 'pose':
            return False

        return True
        
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        if context.mode == 'POSE':
            row = layout.row()
            row.prop(wm, 'content_pack_anims', text='')
            row.operator(ctops.CT_OT_RefreshContentPacks.bl_idname, text='', icon='FILE_REFRESH').sync_type = 'animate'
            layout.label(text='Browse animation assets in the Asset Browser.', icon='INFO')

class CT_UL_LightList(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):    
        indicator = "OUTLINER_OB_LIGHT" if item.lighting_selected else "LIGHT"

        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.alignment = 'LEFT'
            layout.prop(item, 'lighting_selected', text=item.name, emboss=False, icon=indicator)
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text='', icon_value=icon)


class CT_UL_CharacterSheetShots(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, 'include_in_sheet', text='')
            row.label(text=item.name)
            row.prop(item, 'scale', text='S')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.prop(item, 'include_in_sheet', text='')

class CT_PT_EnvPanel(CT_BasePanel, Panel):
    bl_label = 'Environmment'
    bl_idname = 'CT_PT_env_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bool(
            context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
        )

    def draw_header(self, context):
        self.layout.label(text='', icon='WORLD_DATA')

    def draw(self, context):
        layout = self.layout
        ctglobals = context.window_manager.ctglobals

        if not ctglobals.env_loaded:
            row = layout.row()
            row.scale_y = 1.5
            row.operator(
                ctops.CT_OT_LoadEnvOperator.bl_idname, 
                text='Load Environment Controls', 
                depress=True, 
                emboss=True, 
                icon='WORLD'
            )

class CT_PT_LightingPanel(CT_BasePanel, Panel):
    bl_label = 'Lighting'
    bl_idname = 'CT_PT_lighting_panel'
    bl_parent_id = 'CT_PT_env_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ctglobals = context.window_manager.ctglobals

        return bool(
            context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
            and ctglobals.env_loaded
        )   

    def draw(self, context):
        ctglobals = context.window_manager.ctglobals
        clone_props = get_scene().clone_props

        if ctglobals.env_loaded:
            layout = self.layout
            
            row_presets = layout.row(align=True)
            row_presets.template_list(
                'CT_UL_LightList', 
                '', 
                ctglobals,
                'lights_collection',
                ctglobals,
                'lights_collection_index'      
            )

            row_look = layout.row()
            row_look.prop(get_scene().view_settings, 'look')

class CT_PT_StagingPanel(CT_BasePanel, Panel):
    bl_label = 'Staging'
    bl_idname = 'CT_PT_staging_panel'
    bl_parent_id = 'CT_PT_env_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        ctglobals = context.window_manager.ctglobals

        return bool(
            context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
            and ctglobals.env_loaded
        )

    def draw(self, context):
        ctglobals = context.window_manager.ctglobals

        if ctglobals.env_loaded:
            layout = self.layout

            row = layout.row()
            row.label(text='Select Staging Preset:')
            row = layout.row()
            row.prop(ctglobals, 'staging_options', text='')

            if ctglobals.staging_options == 'SkyboxPreset':
                skybox_mat = get_material('skybox')
                nodes = get_nodes(skybox_mat)
                rgb_node = get_node(nodes, 'RGB')
                mix_node = get_node(nodes, 'Mix Shader.001')
                image_tex_node = get_node(nodes, 'Image Texture')
                
                layout.label(text='Background Image:')
                layout.template_ID(image_tex_node, "image", open="image.open")
                
                col = layout.column()
                col.prop(rgb_node.outputs[0], 'default_value', text='Background Color')
                col.prop(mix_node.inputs[0], 'default_value', text='Mix Factor')
            elif ctglobals.staging_options == 'LightCatcherPreset':
                lc_mat = get_material('CatcherLight')
                nodes = get_nodes(lc_mat)
                bsdf_node = get_node(nodes, 'Principled BSDF')

                col = layout.column()
                col.prop(bsdf_node.inputs[0], 'default_value', text='Background Color')
                
class CT_PT_CameraPanel(CT_BasePanel, Panel):
    bl_label = 'Camera'
    bl_idname = 'CT_PT_camera_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bool(
            context.mode in {'OBJECT', 'EDIT_MESH', 'EDIT_ARMATURE', 'POSE'}
        )

    def draw_header(self, context):
        self.layout.label(text='', icon='CAMERA_DATA')

    def draw(self, context):
        layout = self.layout
        
        col = layout.column(heading='Location')
        col.prop(get_object('Camera'), 'location', text='')

        col = layout.column(heading='Lens', align=True)
        col.prop(get_object('Camera').data, 'shift_x')
        col.prop(get_object('Camera').data, 'shift_y')
        col.prop(get_object('Camera').data, 'lens')

        col = layout.column(heading='Resolution', align=True)
        col.prop(get_scene().render, 'resolution_x', text='X')
        col.prop(get_scene().render, 'resolution_y', text='Y')

        col = layout.column()
        col.scale_y = 1.5
        render_op = col.operator('render.render', text='Render Image', depress=True, icon='RENDER_STILL')
        render_op.use_viewport = True

class CT_PT_RenderPanel(CT_BasePanel, Panel):
    bl_label = 'Render'
    bl_idname = 'CT_PT_render_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bool(
            context.mode in {'OBJECT', 'EDIT_MESH', 'EDIT_ARMATURE', 'POSE'}
        )

    def draw_header(self, context):
        self.layout.label(text='', icon='RESTRICT_RENDER_OFF')

    def draw(self, context):
        ctglobals = context.window_manager.ctglobals
        clone_props = get_scene().clone_props

        layout = self.layout
        col = layout.column()
        col.prop(get_scene().render, 'engine')

        render_engine = get_scene().render.engine
        
        if render_engine == 'CYCLES':
            col.prop(get_scene().cycles, 'device')
            col.prop(get_scene().cycles, 'samples')
        elif render_engine == 'BLENDER_EEVEE':
            col.prop(get_scene().eevee, 'taa_render_samples')
            col.prop(get_scene().eevee, 'use_ssr', text='Enhanced Reflections')
            col.prop(ctglobals, 'use_bloom', text='Bloom')

        if ctglobals.use_bloom:
            col.prop(get_scene().eevee, 'bloom_color')
            col.prop(get_scene().eevee, 'bloom_intensity')
        
        head_mat = None
        
        try:
            head_mat = get_material_from_object(ctutils.get_head_geo())
        except:
            pass

        if head_mat:
            col.prop(clone_props, 'use_realistic_skin')

            if clone_props.use_realistic_skin:                 
                nodes = get_nodes(head_mat)
                bsdf_node = get_node(nodes, 'Principled BSDF')
        
                col.prop(bsdf_node.inputs[1], 'default_value', text='Adjust')

        col.prop(ctglobals, 'use_transparent', text='Transparent')

        col = layout.column()
        col.scale_y = 1.5
        render_op = col.operator('render.render', text='Render Image', depress=True, icon='RENDER_STILL')
        render_op.use_viewport = True

        box = layout.box()
        box.label(text='Character Sheet', icon='RENDERLAYERS')
        box.prop(ctglobals, 'charsheet_preset', text='Preset')
        box.prop(ctglobals, 'charsheet_output_path', text='Output')
        box.prop(ctglobals, 'charsheet_transparent_bg')
        box.prop(ctglobals, 'charsheet_body_views')
        box.prop(ctglobals, 'charsheet_include_closeups')
        box.prop(ctglobals, 'charsheet_build_page')
        if ctglobals.charsheet_build_page:
            box.prop(ctglobals, 'charsheet_page_columns')

        row = box.row()
        row.scale_y = 1.3
        row.operator(ctops.CT_OT_RenderCharacterSheet.bl_idname, text='Render Character Sheet', icon='RENDER_STILL')

        if len(ctglobals.charsheet_shots) > 0:
            list_box = layout.box()
            list_box.label(text='Sheet Builder', icon='SEQ_PREVIEW')
            list_box.template_list(
                'CT_UL_CharacterSheetShots',
                '',
                ctglobals,
                'charsheet_shots',
                ctglobals,
                'charsheet_shot_index',
                rows=6
            )
            row = list_box.row(align=True)
            row.operator(ctops.CT_OT_RebuildCharacterSheet.bl_idname, text='Rebuild Stitched Sheet', icon='FILE_REFRESH')

class CT_PT_ExportPanel(CT_BasePanel, Panel):
    bl_label = 'Export'
    bl_idname = 'CT_PT_export_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bool(
            context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
        )

    def draw_header(self, context):
        self.layout.label(text='', icon='EXPORT')

    def draw(self, context):
        ctglobals = context.window_manager.ctglobals

        layout = self.layout
        export_op = ctops.CT_OT_ExportOperator.bl_idname

        row = layout.row()
        row.label(text='Export as filetype:')
        export_row_buttons = layout.row()
        export_row_buttons.scale_y = 1.5
        export_row_buttons.operator(export_op, text='FBX').export_type = 'fbx'
        export_row_buttons.operator(export_op, text='OBJ').export_type = 'obj'
        export_row_buttons.operator(export_op, text='GLB').export_type = 'glb'

        export_row_checkbox = layout.row()
        export_row_checkbox.prop(
            ctglobals,
            'export_mesh_only',
            text='Model only (good for Mixamo)'
        )

class CT_PT_PackPanel(CT_BasePanel, Panel):
    bl_label = 'Content Packs'
    bl_idname = 'CT_PT_pack_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bool(
            context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
        )

    def draw_header(self, context):
        self.layout.label(text='', icon='PACKAGE')

    def draw(self, context):
        prefs = context.preferences.addons[__package__].preferences

        layout = self.layout

        # row = layout.row()
        # row.label(text='Content Packs Path:')

        # row = layout.row()
        # row.prop(prefs, 'content_packs_path', text='')

        # if prefs.content_packs_path != '':
        row = layout.row()
        row.scale_y = 1.5
        row.operator(
            ctops.CT_OT_InstallContentPackOperator.bl_idname, 
            text='Load Content Pack',
            depress=True,
            emboss=True)

class CT_PT_TroubleshootingPanel(CT_BasePanel, Panel):
    bl_label = 'Troubleshooting'
    bl_idname = 'CT_PT_troubleshooting_panel'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return bool(
            context.mode in {'OBJECT','EDIT_MESH', 'EDIT_ARMATURE','POSE'}
            and get_scene().clone_props.files_loaded
        )

    def draw_header(self, context):
        self.layout.label(text='', icon='TOOL_SETTINGS')

    def draw(self, context):
        layout = self.layout
        clone_props = get_scene().clone_props

        # Automatic fixes settings
        box = layout.box()
        box.label(text="Automatic Import Fixes:", icon='SETTINGS')
        
        col = box.column()
        col.prop(clone_props, 'auto_fix_scale')
        col.prop(clone_props, 'auto_position_traits') 
        col.prop(clone_props, 'auto_register_traits')
        col.prop(clone_props, 'show_import_validation')

        # Manual fix operators
        box = layout.box()
        box.label(text="Manual Fixes:", icon='TOOL_SETTINGS')
        
        col = box.column()
        col.scale_y = 1.2
        
        col.operator(
            ctops.CT_OT_FixScaleMismatch.bl_idname,
            text='Fix Scale Mismatch',
            icon='FULLSCREEN_EXIT'
        )
        
        col.operator(
            ctops.CT_OT_AutoPositionTraits.bl_idname,
            text='Auto-Position Traits',
            icon='SNAP_FACE'
        )
        
        col.operator(
            ctops.CT_OT_ForceRegisterTraits.bl_idname,
            text='Force Register Traits',
            icon='PRESET'
        )

        # Complete fixes operator
        box = layout.box()
        box.label(text="Complete Fixes:", icon='CHECKMARK')
        
        col = box.column()
        col.scale_y = 1.5
        col.operator(
            ctops.CT_OT_EnhancedCloneImport.bl_idname,
            text='Apply All Fixes',
            icon='FILE_REFRESH'
        )

        # Debug analysis
        box = layout.box()
        box.label(text="Debug Analysis:", icon='CONSOLE')
        
        col = box.column()
        col.operator(
            ctops.CT_OT_AnalyzeCloneState.bl_idname,
            text='Analyze Clone State',
            icon='VIEWZOOM'
        )

class CT_PT_FileBrowserToolsPanel(Panel):
    bl_label = 'Important Tip'
    bl_idname = 'CT_PT_file_browser_tools_panel'
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'

    def draw_header(self, context):
        self.layout.label(text='', icon='INFO')

    def draw(self, context):
        layout = self.layout
        layout.label(text='Right-click on items for equip options!')

def style_library_list_item_context_menu(self: UIList, context: Context) -> None:
    def is_style_asset_view() -> bool:
        # Important: Must check context first, or the menu is added for every kind of list.
        list = getattr(context, "ui_list", None)
        
        if not list or list.bl_idname != "UI_UL_asset_view" or list.list_id != "style_assets":
            return False
        
        if not get_context_asset(context):
            return False
        
        return True

    def is_style_library_asset_browser() -> bool:
        asset = get_context_asset(context)
        
        if not asset:
            return False
        
        asset_type = get_asset_id_type(asset)
        return bool(asset_type == 'COLLECTION' or asset_type == 'MATERIAL')

    if not is_style_asset_view() and not is_style_library_asset_browser():
        return

    layout = self.layout
    asset = get_context_asset(context)
    if asset is None:
        return

    asset_name = get_asset_name(asset)
    asset_type = get_asset_id_type(asset)
    trait_coll = context.scene.clone_props.trait_collection

    layout.separator()
    
    if asset_type == 'COLLECTION':
        if trait_coll.find(asset_name) == -1:    
            layout.operator("ct.equip_wearable_operator", text="Equip Style")
        else:
            layout.operator('ct.unequip_wearable_operator', text='Unequip Style').wearable_name = asset_name
    elif asset_type == 'MATERIAL':
        if not asset_name.startswith('ff_'):
            layout.operator('ct.apply_dna_head_operator', text='Apply to Head')
            layout.operator('ct.apply_dna_suit_operator', text='Apply to Suit')
        else:
            layout.operator('ct.apply_facial_feature_operator', text='Apply Facial Feature')
            layout.operator('ct.remove_facial_feature_operator', text='Remove Facial Feature')

    layout.separator()

    if is_style_asset_view():
        layout.operator("asset.open_containing_blend_file")

classes = (
    CT_UL_TraitList,
    CT_UL_LightList,
    CT_UL_CharacterSheetShots,
    CT_PT_AssemblePanel,
    CT_PT_StylePanel,
    CT_PT_TroubleshootingPanel,
    CT_PT_PoseAndAnimatePanel,
    # CT_PT_PoseSubPanel,
    # CT_PT_AnimateSubPanel,
    CT_PT_CameraPanel,
    CT_PT_EnvPanel,
    CT_PT_LightingPanel,
    CT_PT_StagingPanel,
    CT_PT_RenderPanel,
    CT_PT_ExportPanel,
    CT_PT_PackPanel,
    CT_PT_FileBrowserToolsPanel
)

def register():
    for cls in classes:
        register_class(cls)

    bpy.types.WindowManager.content_pack_poses = EnumProperty(
        items=ctutils.get_pose_content_packs,
        update=ctutils.update_pose_content_pack
    )

    bpy.types.WindowManager.content_pack_anims = EnumProperty(
        items=ctutils.get_anim_content_packs,
        update=ctutils.update_anim_content_pack
    )

    bpy.types.WindowManager.selected_pose_action = EnumProperty(
        items=ctutils.get_pose_action_items,
        update=ctutils.update_selected_pose_action
    )

    if hasattr(bpy.types, "UI_MT_list_item_context_menu"):
        bpy.types.UI_MT_list_item_context_menu.prepend(style_library_list_item_context_menu)
    if hasattr(bpy.types, "ASSETBROWSER_MT_context_menu"):
        bpy.types.ASSETBROWSER_MT_context_menu.prepend(style_library_list_item_context_menu)

def unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    wm = bpy.context.window_manager

    if hasattr(bpy.types, "ASSETBROWSER_MT_context_menu"):
        bpy.types.ASSETBROWSER_MT_context_menu.remove(style_library_list_item_context_menu)
    if hasattr(bpy.types, "UI_MT_list_item_context_menu"):
        bpy.types.UI_MT_list_item_context_menu.remove(style_library_list_item_context_menu)

    if hasattr(bpy.types.WindowManager, "content_pack_poses"):
        del bpy.types.WindowManager.content_pack_poses
    if hasattr(bpy.types.WindowManager, "content_pack_anims"):
        del bpy.types.WindowManager.content_pack_anims
    if hasattr(bpy.types.WindowManager, "selected_pose_action"):
        del bpy.types.WindowManager.selected_pose_action
