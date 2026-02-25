import bpy, addon_utils, os, shutil, time, re, json, zipfile, tempfile, hashlib

from math import radians
from mathutils import Matrix
from pathlib import Path
import numpy as np

from .lib.easybpy import *
from .clone_tools_compat import set_space_asset_library

# Guard and queue style-library syncs so we avoid heavy file writes directly
# inside depsgraph callbacks.
_style_sync_in_progress = False
_style_sync_pending = False
_style_sync_path = ""
_pose_action_cache = {}

def get_content_packs_dir(context=None):
    """
    Resolve content-pack root directory.
    Priority:
    1) Addon Preferences `content_packs_path` when set
    2) Bundled addon folder `<addon>/content_packs`
    """
    default_dir = os.path.join(os.path.dirname(__file__), 'content_packs')

    try:
        ctx = context if context is not None else bpy.context
        addon = ctx.preferences.addons.get(__package__)
        if addon is not None:
            configured = bpy.path.abspath(addon.preferences.content_packs_path).strip()
            if configured:
                return configured
    except Exception:
        pass

    return default_dir

def safe_extract_to_dir(zip_ref, extract_dir):
    """
    Safely extract ZIP files with Windows long path handling.
    Simplified version for clone_tools_utils.py
    """
    try:
        # Check path length (Windows MAX_PATH limit)
        if len(extract_dir) > 240:  # Leave some buffer
            print(f"CloneX Utils: Long path detected ({len(extract_dir)} chars), using temp extraction...")
            
            # Create shorter temp directory
            temp_base = tempfile.gettempdir()
            hash_obj = hashlib.md5(extract_dir.encode())
            short_name = f"cx_{hash_obj.hexdigest()[:8]}"
            temp_dir = os.path.join(temp_base, short_name)
            
            # Extract to temp directory first
            zip_ref.extractall(temp_dir)
            
            # Create final destination and move files
            os.makedirs(extract_dir, exist_ok=True)
            
            # Move contents from temp to final location
            for item in os.listdir(temp_dir):
                src = os.path.join(temp_dir, item)
                dst = os.path.join(extract_dir, item)
                shutil.move(src, dst)
            
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"CloneX Utils: Successfully extracted to {extract_dir}")
        else:
            # Normal extraction for shorter paths
            zip_ref.extractall(extract_dir)
            
    except Exception as e:
        print(f"CloneX Utils: Extraction error: {e}")
        raise

def set_asset_library_ref(library_name):
    """
    Set the active Asset Browser library in Blender 5.0+.
    """
    found_browser = False
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'FILE_BROWSER':
                continue
            for space in area.spaces:
                if space.type != 'FILE_BROWSER':
                    continue
                if hasattr(space, 'browse_mode'):
                    space.browse_mode = 'ASSETS'
                if set_space_asset_library(space, library_name):
                    found_browser = True

    if not found_browser:
        print(
            f"CloneX: Info - No open Asset Browser found to set library '{library_name}'. "
            "Open an Asset Browser area to switch libraries from the addon."
        )
    return True

def get_asset_library_ref():
    """
    Get the current Asset Browser library in Blender 5.0+.
    """
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != 'FILE_BROWSER':
                continue
            for space in area.spaces:
                if space.type != 'FILE_BROWSER':
                    continue
                if hasattr(space, 'browse_mode') and space.browse_mode != 'ASSETS':
                    continue
                if hasattr(space, 'asset_library_reference'):
                    return space.asset_library_reference

    return 'LOCAL'  # Default fallback

BSDF_NODE_INDEX_DICT = {
    'BASE_COLOR_INDEX': 0,
    'SS_INDEX': 1,
    'SS_COLOR_INDEX': 3,
    'METALLIC_INDEX': 6,
    'ROUGHNESS_INDEX': 9,
    'EMISSION_INDEX': 19,
    'NORMAL_INDEX': 22
}

def alistdir(directory):
    """
    List directory contents, filtering out hidden files (starting with .).
    Returns empty list if directory doesn't exist or is inaccessible.
    """
    try:
        if not os.path.exists(directory):
            print(f"CloneX: Warning - Directory does not exist: {directory}")
            return []
        
        filelist = os.listdir(directory)
        result = [x for x in filelist if not (x.startswith('.'))]
        
        if not result:
            print(f"CloneX: Warning - No valid files found in directory: {directory}")
        
        return result
        
    except PermissionError:
        print(f"CloneX: Error - Permission denied accessing directory: {directory}")
        return []
    except Exception as e:
        print(f"CloneX: Error - Could not list directory {directory}: {str(e)}")
        return []

def easy_pose_mode_switch():
    # Select all armatures manually since select_all_armatures() doesn't exist
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            obj.select_set(True)
        
    try:
        set_pose_mode(so()[0])
    except:
        print('Unable to switch to Pose mode')
        
    deselect_all_objects()

def get_head_geo():
    head_geo = None
    head_geos = get_objects_including('HeadGeo')

    try:
        head_geo = head_geos[0]
    except:
        pass

    return head_geo

def get_suit_geo():
    suit_geo = None
    suit_geos = get_objects_including('SuitGeo')

    try:
        suit_geo = suit_geos[0]
    except:
        pass

    return suit_geo

def is_collection_asset(coll):
    asset_colls = [a for a in get_all_collections() if a.asset_data]

    for asset_coll in asset_colls:
        if asset_coll.name == coll.name:
            return True

    return False

def is_material_asset(mat_name):
    asset_mats = [m for m in get_all_materials() if m.asset_data]

    for asset_mat in asset_mats:
        if asset_mat.name == mat_name:
            return True

    return False


def ensure_child_collection(parent_collection, child_collection):
    """Link child collection to parent if it is not already linked."""
    if not parent_collection or not child_collection:
        return False

    for existing in parent_collection.children:
        if existing == child_collection or existing.name == child_collection.name:
            return True

    parent_collection.children.link(child_collection)
    return True

def unpack_asset_collection(coll):
    # Get all mesh objects from the collection and update their Armature modifiers
    objects = get_objects_from_collection(coll)
    gender = get_scene().clone_props.gender
    target_armature = get_object('Genesis8_1' + gender.capitalize())

    if target_armature is None:
        # Fallback: pick first armature in scene to avoid silent partial assembly
        for scene_obj in bpy.data.objects:
            if scene_obj.type == 'ARMATURE':
                target_armature = scene_obj
                break

    if target_armature is None:
        print(f"CloneX: Warning - No armature found while unpacking '{coll.name}'")
        return
    
    for obj in objects:
        if obj.type == 'MESH':
            # Clear the parent, then update the armature modifier
            try:
                select_only(obj)
                bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
            except Exception as ex:
                print(f"CloneX: Warning - Could not clear parent on '{obj.name}': {ex}")

            # Prefer any existing ARMATURE modifier, regardless of name.
            armature_mod = None
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE':
                    armature_mod = mod
                    break

            if armature_mod is None:
                # Fallback to legacy name lookups
                armature_mod = get_modifier(obj, 'Armature')
                if not armature_mod:
                    armature_mod = get_modifier(obj, 'Genesis8_1' + gender.capitalize())
                if not armature_mod:
                    if gender == 'female':
                        armature_mod = get_modifier(obj, 'Genesis8_1Male')
                    else:
                        armature_mod = get_modifier(obj, 'Genesis8_1Female')

            if armature_mod is None:
                armature_mod = obj.modifiers.new(name='Armature', type='ARMATURE')

            armature_mod.object = target_armature
            print(f"CloneX: Bound '{obj.name}' to armature '{target_armature.name}'")

    # Clean up unused objects          
    for obj in objects:
        if obj.type != 'MESH':
            delete_object(obj)

def fix_shapekey_names():
    chars = '-._,'

    # loop through shapekeys and replace the names
    for ob in bpy.data.objects:
        #check if object is armature
        if (hasattr(ob.data, 'shape_keys') and hasattr(ob.data.shape_keys, 'key_blocks')):
            for key in ob.data.shape_keys.key_blocks:
                # Do not change basis
                if not key.name == "Basis":
                    # Get last occurrence of any of these chars 
                    n = max(key.name.rfind(i) for i in chars) + 1

                    # Slice all chars up to n 
                    key.name = key.name[n:]

def copy_shapekey_drivers(head_object):
    source = bpy.context.object

    #hacky way of excluding the armature even if weird name
    if (            
        hasattr(source.data, 'shape_keys') and 
        hasattr(source.data.shape_keys, 'key_blocks') and
        hasattr(head_object.data, 'shape_keys') and 
        hasattr(head_object.data.shape_keys, 'key_blocks')
    ): 
            
        shape_keys = head_object.data.shape_keys
        fcurve_dict = {}
        
        rna = source.get('_RNA_UI', {})
        
        for key, keyblock in shape_keys.key_blocks.items():
            if keyblock == shape_keys.key_blocks[0]:
                print("keyblock %s assumed Basis and ignored" % key)
                continue
            
            rna[key] =  {
                "name": key,
                "min": keyblock.slider_min,
                "max": keyblock.slider_max,
                "description": "Shape Key %s" % key,
                "soft_min": keyblock.slider_min,
                "soft_max": keyblock.slider_max,
            }

            source[key] = keyblock.value
            source["_RNA_UI"] = rna
            
            # driver_add(path to property to drive), then get reference to driver object
            fcurve = shape_keys.driver_add('key_blocks["%s"].value' % key)
            driver = fcurve.driver
            driver.type = 'AVERAGE'         # driver type = averaged value 
            var = driver.variables.new()
            # add a single property called value (aka the value of each shape key)
            var.name = "value" 
            var.type = 'SINGLE_PROP'
            target = var.targets[0]         # adds a new target I guess
            target.id_type = "KEY"          # this is where the Prop: thing comes from in driver editor panels
            target.id = source.data.shape_keys  # target is the source shape_keys, type is Key: not surprising
            target.data_path = 'key_blocks["%s"].value' % key # this is the relative data path from the shape keys object

def initialize_clonex_asset_library(name, library_path):
    if not os.path.exists(library_path):
        os.mkdir(library_path)

    bpy.ops.preferences.asset_library_add(directory=library_path)

    for al in bpy.context.preferences.filepaths.asset_libraries:
        if al.path == library_path:
            al.name = name

    sync_assets_to_style_library(library_path)

    # Clear the assets from the local file now that they
    # have been moved to the style library
    # for asset in assets:
    #     asset.asset_clear()

def sync_assets_to_style_library(library_path):
    if not library_path:
        print("CloneX: Warning - Style library path is empty, skipping sync")
        return False
    if not os.path.isdir(library_path):
        print(f"CloneX: Warning - Style library path does not exist: {library_path}")
        return False

    # Move the asset catalog to the location of the style library
    src_path = os.path.join(get_scene().clone_props.home_dir, 'blender_assets.cats.txt')
    dest_path = os.path.join(library_path, 'blender_assets.cats.txt')
    if os.path.exists(src_path):
        shutil.copy(src_path, dest_path)
    else:
        print(f"CloneX: Warning - Asset catalog missing, skipping copy: {src_path}")

    # Collect all of the assets and write them to a .blend file in the
    # location specified by the user
    assets = set([])

    colls = get_all_collections()
    mats = get_all_materials()
    
    for coll in colls:
        if coll.asset_data:
            assets.add(coll)

    for mat in mats:
        if mat.asset_data:
            assets.add(mat)

    # print('Syncing assets...')
    # for asset in assets:
    #     print(asset.name)

    # This will overwrite the existing style library            
    if not assets:
        return True

    bpy.data.libraries.write(
        os.path.join(library_path, 'clonex_style_library.blend'),
        assets,
        fake_user=True
    )
    return True


def _style_library_sync_timer_callback():
    global _style_sync_in_progress, _style_sync_pending, _style_sync_path

    if _style_sync_in_progress:
        _style_sync_pending = True
        return 0.75

    path = _style_sync_path
    _style_sync_pending = False
    _style_sync_in_progress = True

    try:
        sync_assets_to_style_library(path)
    except Exception as ex:
        print(f"CloneX: Error - Deferred style library sync failed: {ex}")
    finally:
        _style_sync_in_progress = False

    if _style_sync_pending:
        return 0.75
    return None


def request_style_library_sync(library_path, delay=0.75):
    """Queue a style-library sync on the main thread timer."""
    global _style_sync_pending, _style_sync_path

    if not library_path:
        return False

    _style_sync_path = library_path
    _style_sync_pending = True

    if not bpy.app.timers.is_registered(_style_library_sync_timer_callback):
        bpy.app.timers.register(
            _style_library_sync_timer_callback,
            first_interval=max(0.1, delay)
        )

    return True

def select_all_mesh_and_armature(context):
    objects = context.scene.objects

    for obj in objects:
        obj.select_set(obj.type == 'ARMATURE' or obj.type == 'MESH')

def setup(context):
    ctglobals = context.window_manager.ctglobals

    if not ctglobals.setup_finished:
        # Remove default objects
        if get_object("Cube") is not None:
                delete_object("Cube")

        if get_object("Light") is not None:
            delete_object("Light")

        # Make the background dark
        get_world_nodes()["Background"].inputs[0].default_value = (0, 0, 0, 1)

        # Move the camera into a better starting position
        # if the default camera exists
        cam = get_object('Camera')

        if cam is not None:
            con = None
            try:
                # easybpy.add_constraint can assume a full UI screen context.
                # Use direct API fallback for scripted/headless-safe execution.
                if getattr(bpy.context, "screen", None) is not None:
                    con = add_constraint('TRACK_TO', cam, 'Track to head')
                else:
                    con = cam.constraints.new('TRACK_TO')
                    con.name = 'Track to head'
            except Exception as ex:
                print(f"CloneX: add_constraint fallback due to context limitations: {ex}")
                try:
                    con = cam.constraints.new('TRACK_TO')
                    con.name = 'Track to head'
                except Exception as ex2:
                    print(f"CloneX: Unable to create camera TRACK_TO constraint: {ex2}")
                    con = None
            objs = []

            for o in bpy.data.objects:
                if 'HeadGeo' in o.name:
                    objs.append(o)

            if len(objs) > 0:
                head_geo = objs[0]
                try:
                    select_object(head_geo)
                except Exception as ex:
                    print(f"CloneX: select_object skipped due to context limitations: {ex}")
                try:
                    if bpy.ops.object.origin_set.poll():
                        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
                except Exception as ex:
                    print(f"CloneX: origin_set skipped due to context limitations: {ex}")
                if con:
                    con.target = objs[0]

            mat_loc = Matrix.Translation((0, -10, 2))
            mat_sca = Matrix.Scale(1, 4, (1, 1, 1))
            mat_rot = Matrix.Rotation(radians(83), 4, 'X')
            mat_comb = mat_loc @ mat_rot @ mat_sca

            cam.data.lens = 112
            cam.data.shift_y = -0.2
            cam.matrix_world = mat_comb

        screen = getattr(context, "screen", None)
        window = getattr(context, "window", None)
        if screen and window:
            for area in screen.areas:
                if area.type != 'VIEW_3D':
                    continue

                region = next((r for r in area.regions if r.type == 'WINDOW'), None)
                if region is None:
                    continue

                select_all_meshes()
                # view_camera is optional and frequently fails during scripted operator
                # execution in Blender 5 due to strict UI context requirements.

                space = area.spaces.active
                if space and space.type == 'VIEW_3D':
                    space.shading.type = 'RENDERED'
                    space.overlay.show_overlays = False

        cycles = get_scene().cycles

        # Enable preview denoising by default for cycles
        cycles.use_preview_denoising = True

        # Set lower defaults for cycles max samples
        cycles.preview_samples = 64
        cycles.samples = 64

        cpdir = get_content_packs_dir(context)

        for pack in ['clonetools_male_pose_pack.zip', 'clonetools_female_pose_pack.zip']:
            # Unzip selected file and look for packinfo.json
            pack_filename = os.path.abspath(os.path.join(cpdir, pack))
            library_exists = False

            if os.path.exists(pack_filename):
                with zipfile.ZipFile(pack_filename) as zip_ref:
                    with zip_ref.open('packinfo.json') as packinfo:
                        data = json.loads(packinfo.read())
                        pack_name = data['pack_name']
                        pack_subdir = data['pack_subdir']
                        pack_type = data['pack_type']
                        pack_creator = data['pack_creator']

                    library_name = '[' + pack_creator + '] ' + pack_name

                    for al in bpy.context.preferences.filepaths.asset_libraries:
                        if al.name == library_name:
                            library_exists = True
                            break

                    extract_dir = os.path.join(cpdir, pack_type, pack_subdir)

                    if not os.path.exists(extract_dir):
                        safe_extract_to_dir(zip_ref, extract_dir)      

                print('Checking if library exists: ' + str(library_exists))

                if not library_exists:
                    # Create a new Asset Library for the pack
                    bpy.ops.preferences.asset_library_add(directory=str(extract_dir))

                    for al in bpy.context.preferences.filepaths.asset_libraries:
                        if al.path == extract_dir:
                            al.name = '['+ pack_creator + '] ' + pack_name
        
        refresh_content_packs(None, context)
        
        # In Blender 5.0, selecting objects not present in the active View Layer
        # throws RuntimeError. Use safe selection helpers that ensure visibility.
        gender = context.scene.clone_props.gender
        target_armature = get_object('Genesis8_1' + gender.capitalize())

        if target_armature:
            select_only(target_armature)
            set_pose_mode(target_armature)
        else:
            for obj in bpy.data.objects:
                if obj.type == 'ARMATURE' and select_object(obj, make_active=True):
                    set_pose_mode(obj)
                    break

        # gender = context.scene.clone_props.gender

        # # Set the initial pose
        # initial_pose = None

        # try:
        #     if gender == 'male':
        #         initial_pose = bpy.data.actions['Male Default Pose']
        #     else:
        #         initial_pose = bpy.data.actions['Female Default Pose']
        # except:
        #     print('Could not find default pose action')

        # if initial_pose:
        #     armature = get_object('Genesis8_1' + context.scene.clone_props.gender.capitalize())

        #     if armature:
        #         if not armature.animation_data:
        #             armature.animation_data_create()

        #         armature.animation_data.action = initial_pose
        
        try:
            deselect_all_objects()
        except Exception as ex:
            print(f"CloneX: deselect_all_objects skipped due to context limitations: {ex}")

        # fix_shapekey_names()
        # copy_shapekey_drivers(get_head_geo())

        ctglobals.setup_finished = True

def load_content_pack(pack_filename, cpdir):
    library_exists = False

    if os.path.exists(pack_filename):
        with zipfile.ZipFile(pack_filename) as zip_ref:
            with zip_ref.open('packinfo.json') as packinfo:
                data = json.loads(packinfo.read())
                pack_name = data['pack_name']
                pack_subdir = data['pack_subdir']
                pack_type = data['pack_type']
                pack_creator = data['pack_creator']

            library_name = '[' + pack_creator + '] ' + pack_name

            for al in bpy.context.preferences.filepaths.asset_libraries:
                if al.name == library_name:
                    library_exists = True
                    break

            extract_dir = os.path.join(cpdir, pack_type, pack_subdir)

            if not os.path.exists(extract_dir):
                safe_extract_to_dir(zip_ref, extract_dir)      

        print('Checking if library exists: ' + str(library_exists))

        if not library_exists:
            # Create a new Asset Library for the pack
            bpy.ops.preferences.asset_library_add(directory=str(extract_dir))

            for al in bpy.context.preferences.filepaths.asset_libraries:
                if al.path == extract_dir:
                    al.name = '['+ pack_creator + '] ' + pack_name

def load_poses_from_blendfile(context):
    ctglobals = context.window_manager.ctglobals
    data_path = os.path.join(Path(__file__).resolve().parent, 'assets', 'database.blend')
    
    try:
        with bpy.data.libraries.load(data_path) as (data_from, data_to):
            if not ctglobals.poses_loaded:
                data_to.actions = data_from.actions
    except Exception as ex:
        print(ex)

    ctglobals.poses_loaded = True

def load_env_from_blendfile(context):
    ctglobals = context.window_manager.ctglobals
    data_path = os.path.join(Path(__file__).resolve().parent, 'assets', 'database.blend')
    
    if (collection_exists('Lighting') and collection_exists('Staging')):
        setup_lighting_collection(context)
        setup_staging_collection(context)
    else:
        try:
            with bpy.data.libraries.load(data_path) as (data_from, data_to):
                if not ctglobals.env_loaded:
                    print('env_loaded is false')
                    data_to.collections = data_from.collections
        except Exception as ex:
            print(ex)
            ctglobals.env_loaded = False
            return

        # Link all lighting collections to scene and
        # add their names to the lighting property group
        for coll in data_to.collections:
            if coll is None:
                continue
            if coll.name == 'Lighting':
                print('Found collection: Lighting')
                try:
                    get_scene().collection.children.link(coll)
                except RuntimeError:
                    pass
                setup_lighting_collection(context)
            elif coll.name == 'Staging':
                try:
                    get_scene().collection.children.link(coll)
                except RuntimeError:
                    pass
                setup_staging_collection(context)
            else:
                continue

    ctglobals.env_loaded = True

def setup_lighting_collection(context):
    ctglobals = context.window_manager.ctglobals

    lighting_colls = [c for c in get_collection('Lighting').children]

    for lcoll in lighting_colls:
        item = ctglobals.lights_collection.add()
        item.name = lcoll.name

        if lcoll.name != 'Default Lighting':
            hide_collection_viewport(lcoll)
            hide_collection_render(lcoll)
        else:
            item.lighting_selected = True

def setup_staging_collection(context):
    ctglobals = context.window_manager.ctglobals

    staging_colls = [c for c in get_collection('Staging').children]

    for scoll in staging_colls:
        # Default to Light Catcher and hide everything else to start
        if scoll.name != 'LightCatcherPreset':
            hide_collection_viewport(scoll)
            hide_collection_render(scoll)

def apply_facial_feature(filepath, trait_name):
    wm = bpy.context.window_manager

    head_geos = get_objects_including('HeadGeo')
    head_mats = get_materials_containing('dna', head_geos[0])

    ff_mat = get_material(trait_name)
    ff_image = None

    if ff_mat:
        # The dummy material already exists so we can
        # pull the image reference from there
        ff_image = get_node(get_nodes(ff_mat), 'Image Texture').image
    else:
        # Create a dummy mat to generate an asset and asset preview
        image_exts = ['.png', '.jpg', '.jpeg']

        for path in [p for p in Path(filepath).rglob('*') if p.suffix in image_exts]:
            if get_image(path.name) is None:
                bpy.data.images.load(str(path.resolve()), check_existing=True)

            ff_image = get_image(path.name)

            continue

        ff_mat = create_material(trait_name)
        ff_mat.use_nodes = True

        ff_mat_nodes = get_nodes(ff_mat)
        ff_mat_bsdf = get_node(ff_mat_nodes, 'Principled BSDF')
        ff_mat_bsdf.subsurface_method = 'BURLEY'
        ff_mat_out_node = get_node(ff_mat_nodes, 'Material Output')
        ff_tex_node = create_node(ff_mat_nodes, 'ShaderNodeTexImage')
        ff_tex_node.image = ff_image
        ff_tex_node.image.colorspace_settings.name = 'sRGB'

        if ff_mat_bsdf is not None:
            create_node_link(ff_mat_bsdf.outputs[0], ff_mat_out_node.inputs[0])
            create_node_link(ff_tex_node.outputs[0], ff_mat_bsdf.inputs[0])

            ff_mat.asset_mark()
            ff_mat.asset_generate_preview()

            # Only auto-catalog assets that don't have a real UUID yet
            if ff_mat.asset_data.catalog_id == '00000000-0000-0000-0000-000000000000':
                try:
                    ff_mat.asset_data.catalog_id = wm.TRAIT_MAPPING[trait_name[3:].lower()]
                except:
                    print('No asset catalog mapping found for: ' + trait_name[3:].lower())

            ff_mat.asset_data.tags.new('rtfkt', skip_if_exists=True) 
    
    for head_mat in head_mats:
        head_nodes = get_nodes(head_mat)
        mix_shader_node = get_node(head_nodes, 'Mix Shader')
        bsdf_node = get_node(head_nodes, 'Principled BSDF')
        mat_out_node = get_node(head_nodes, 'Material Output')

        if not mix_shader_node:
            # Facial feature hasn't been applied yet so create nodes and links
            tex_node = create_node(head_nodes, 'ShaderNodeTexImage')
            tex_node.image = ff_image
            tex_node.image.colorspace_settings.name = 'sRGB'
            mix_shader_node = create_node(head_nodes, 'ShaderNodeMixShader')

            if bsdf_node is not None:
                # Connect output of BSDF to first shader iput of mix shader node
                create_node_link(bsdf_node.outputs[0], mix_shader_node.inputs[1])

                # Connect color output of texture image node to mix shader bottom input
                create_node_link(tex_node.outputs[0], mix_shader_node.inputs[2])

                # Connect alpha output of texture image node to mix shader fac input
                create_node_link(tex_node.outputs[1], mix_shader_node.inputs[0])

                # Connect output of mix shader node to surface input of matrial output node
                create_node_link(mix_shader_node.outputs[0], mat_out_node.inputs[0])
            else:
                print('Could not find required Principled BSDF node, unable to apply facial feature')
        else:
            # If mix shader node already exists, it either needs to be reconnected
            # or updated to use a new facial feature image
            current_image_name = mix_shader_node.inputs[0].links[0].from_node.image.name

            if current_image_name == ff_image.name:
                create_node_link(mix_shader_node.outputs[0], mat_out_node.inputs[0])
            else:
                mix_shader_node.inputs[0].links[0].from_node.image = ff_image
                create_node_link(mix_shader_node.outputs[0], mat_out_node.inputs[0])

def remove_facial_feature():
    head_geos = get_objects_including('HeadGeo')
    head_mats = get_materials_containing('dna', head_geos[0])

    for head_mat in head_mats:
        if head_mat:
            head_nodes = get_nodes(head_mat)
            bsdf_node = get_node(head_nodes, 'Principled BSDF')
            mat_out_node = get_node(head_nodes, 'Material Output')

            # This severs the mix shader node mapping
            create_node_link(bsdf_node.outputs[0], mat_out_node.inputs[0])

def apply_dna_textures_to_object(filepath, trait_name, geo_object):
    wm = bpy.context.window_manager

    base_mat = get_material_from_object(geo_object)  
    dna_mat_name = trait_name
    dna_mat = get_material(dna_mat_name)
    
    if dna_mat is None:
        dna_mat = create_material(dna_mat_name)
        dna_mat.use_nodes = True

        dna_nodes = get_nodes(dna_mat)
        dna_bsdf = get_node(dna_nodes, 'Principled BSDF')
        dna_bsdf.subsurface_method = 'BURLEY'
        
        # Load all of the image files
        image_exts = ['.png', '.jpg', '.jpeg']

        for path in [p for p in Path(filepath).rglob('*') if p.suffix in image_exts]:
            if get_image(path.name) is None:
                bpy.data.images.load(str(path.resolve()), check_existing=True)
                
                filename = path.stem
                
                tex_node = create_node(dna_nodes, "ShaderNodeTexImage")
                tex_node.image = get_image(path.name)
                
                tokens = filename.split('_')
                suffix = tokens[len(tokens)-1].lower()
                
                if suffix == 'd':
                    # This is a base color image
                    output_socket = tex_node.outputs[0]
                    input_socket = dna_bsdf.inputs[BSDF_NODE_INDEX_DICT['BASE_COLOR_INDEX']]

                    if not input_socket.is_linked:
                        create_node_link(output_socket, input_socket)
                elif suffix == 'm':
                    # This is a metallic image
                    output_socket = tex_node.outputs[0]
                    input_socket = dna_bsdf.inputs[BSDF_NODE_INDEX_DICT['METALLIC_INDEX']]

                    if not input_socket.is_linked:
                        create_node_link(output_socket, input_socket)

                    tex_node.image.colorspace_settings.name = 'Non-Color'
                elif suffix == 'r':
                    # This is a roughness image
                    output_socket = tex_node.outputs[0]
                    input_socket = dna_bsdf.inputs[BSDF_NODE_INDEX_DICT['ROUGHNESS_INDEX']]

                    if not input_socket.is_linked:
                        create_node_link(output_socket, input_socket)
                    
                    tex_node.image.colorspace_settings.name = 'Non-Color'
                elif suffix == 'e':
                    # This is an emission image 
                    output_socket = tex_node.outputs[0]
                    input_socket = dna_bsdf.inputs[BSDF_NODE_INDEX_DICT['EMISSION_INDEX']]

                    if not input_socket.is_linked:
                        create_node_link(output_socket, input_socket)
                    
                    tex_node.image.colorspace_settings.name = 'Non-Color'
                elif suffix == 'n':
                    # This is a normal mapping image
                    # Need to create a normal map node between the texture image and BSDF node
                    normal_node = create_node(dna_nodes, "ShaderNodeNormalMap")
                    
                    normal_output_socket = normal_node.outputs[0]
                    input_socket = dna_bsdf.inputs[BSDF_NODE_INDEX_DICT['NORMAL_INDEX']]

                    if not input_socket.is_linked:
                        create_node_link(normal_output_socket, input_socket)
                    
                    create_node_link(tex_node.outputs[0], normal_node.inputs[1])
                    
                    tex_node.image.colorspace_settings.name = 'Non-Color'
                else:
                    # Not a valid texture image, remove both the image and the node
                    delete_image(tex_node.image)
                    delete_node(dna_nodes, tex_node)   

        # Mark the material as an asset
        dna_mat.asset_mark()
        dna_mat.asset_generate_preview()

        # Only auto-catalog assets that don't have a real UUID yet
        if dna_mat.asset_data.catalog_id == '00000000-0000-0000-0000-000000000000':
            dna_mat.asset_data.catalog_id = '4a2f0655-0e5e-4ace-9ec6-8c5642e64917'

        dna_mat.asset_data.tags.new('rtfkt', skip_if_exists=True)

    # Add the new material to the geo_object       
    add_material_to_object(geo_object, dna_mat)
  
    # Swap the material_slots for the base and dna materials
    geo_object.material_slots[0].material = dna_mat
    geo_object.material_slots[len(geo_object.material_slots)-1].material = base_mat
    
def remove_dna_textures_from_object(geo_object):
    base_mat = geo_object.material_slots[len(geo_object.material_slots)-1].material
    #base_mat_name = 'Head' if base_mat.name == 'Head' else 'Suit'
    
    if geo_object.material_slots[0].material.name != base_mat.name:
        #base_mat = get_material(base_mat_name)
        dna_mat = geo_object.material_slots[0].material
        
        geo_object.material_slots[0].material = base_mat
        geo_object.material_slots[len(geo_object.material_slots)-1].material = dna_mat

def preview_finished(obj):
    arr = np.zeros((obj.preview.image_size[0] * obj.preview.image_size[1]) * 4, dtype=np.float32)
    obj.preview.image_pixels_float.foreach_get(arr)
    if np.all((arr == 0)):
        return False
    return True

def load_clone_trait_assets(trait_name, trait_dir, filepath, equip_now, auto_catalog):
    char_collection = get_collection('Character')
    trait_collection = get_collection(trait_name)

    if not trait_collection:
        with bpy.data.libraries.load(filepath) as (data_from, data_to):
            data_to.collections = data_from.collections

        for coll in data_to.collections:
            coll.name = trait_name

            # If the collection is not already an asset, mark it
            # and generate a preview  
            if not is_collection_asset(coll):
                # if trait_name == 'm_mouth' or trait_name == 'f_mouth':
                #     clone_props = get_scene().clone_props
                #     trait_index = clone_props.trait_collection.find(trait_name)
                #     clone_props.trait_collection.remove(trait_index)

                #     continue

                coll.asset_mark()
                coll.asset_generate_preview()

                if auto_catalog:
                    wm = bpy.context.window_manager
                    lookup_name = trait_name

                    if trait_name.startswith('f_') or trait_name.startswith('m_'):
                        lookup_name = trait_name[2:]

                    # Eyes are very inconsistent, try to deal with that
                    if 'eye_color' in trait_dir.lower():
                        lookup_name = 'eyes_' + lookup_name

                    # Only auto-catalog assets that don't have a real UUID yet
                    if coll.asset_data.catalog_id == '00000000-0000-0000-0000-000000000000':
                        try:
                            coll.asset_data.catalog_id = wm.TRAIT_MAPPING[lookup_name.lower()]
                        except:
                            # Try using the name of the trait directory
                            dir_name = Path(trait_dir).stem.lower()

                            if dir_name != '':
                                trait_name = dir_name.replace('-combined', '')
                                lookup_name = trait_name[(trait_name.find('-') + 1):]

                                try:
                                    coll.asset_data.catalog_id = wm.TRAIT_MAPPING[lookup_name.lower()]
                                except:  
                                    print('No asset catalog mapping found for: ' + lookup_name.lower())

                    coll.asset_data.tags.new(get_scene().clone_props.gender, skip_if_exists=True)
                    coll.asset_data.author = 'RTFKT'

            if equip_now:
                if char_collection:
                    ensure_child_collection(char_collection, coll)
                    unpack_asset_collection(coll)
    
    return None

def load_glb_trait_asset(trait_name, filepath, equip_now):
    char_collection = get_collection('Character')
    trait_collection = get_collection(trait_name)

    if not trait_collection:
        trait_collection = bpy.data.collections.new(trait_name)

        deselect_all_objects()
        bpy.ops.import_scene.gltf(filepath=filepath)

        objects = selected_objects()

        move_objects_to_collection(objects, trait_collection)

        if not is_collection_asset(trait_collection):
            trait_collection.asset_mark()
            trait_collection.asset_generate_preview()

            if equip_now:
                if char_collection:
                    char_collection.children.link(trait_collection)
                
                unpack_asset_collection(trait_collection)

                trait = get_scene().clone_props.trait_collection.add()
                trait.name = trait_name

def update_trait_selected(self, context):
    from_mode = context.mode

    # Store the base_mats for comparison checks
    base_mats = [get_material('Head'), get_material('Suit')]

    gender = get_scene().clone_props.gender
    
    if Path(os.path.join(self.trait_dir, '_' + gender)).is_dir():
        filepath = os.path.join(self.trait_dir, '_' + gender, '_blender')
    
        for file in alistdir(filepath):
            if file.endswith('.blend'):
                # Append the objects from blend file              
                if self.trait_selected:
                    if not collection_exists(self.name):
                        # This is the first time the trait is being selected so load the assets
                        load_clone_trait_assets(
                            self.name, self.trait_dir, os.path.join(filepath, file), True, True)

                        # Return to mode prior to checking the box in case it was different
                        if from_mode == 'POSE':
                            easy_pose_mode_switch()
                        else:
                            try:
                                set_mode(ao(), from_mode)
                            except:
                                print('Unable to return to previous mode')                                                              
                    else:
                        # If the collection already exists, it was loaded from the style library
                        # and we should use that
                        char_collection = get_collection('Character')

                        if char_collection:
                            existing_collection = get_collection(self.name)
                            if existing_collection:
                                ensure_child_collection(char_collection, existing_collection)
                                unpack_asset_collection(existing_collection)
                        # If the collection already exists just unhide it
                        # unhide_collection_viewport(self.name)
                        # unhide_collection_render(self.name)
                else:
                    if collection_exists(self.name):
                        hide_collection_viewport(self.name)
                        hide_collection_render(self.name)
                    
                break
    else:
        # These traits are textures that need to be applied
        filepath = ''
        geo_objects = []  
        geo_object = None
        
        # These head and suit objects can have varying names, so do some fuzzy matching
        if Path(self.trait_dir).name.startswith('Characters'):
            geo_objects = get_objects_including('SuitGeo')
            filepath = os.path.join(self.trait_dir, '_textures', 'suit_' + get_scene().clone_props.gender)

            if not os.path.exists(filepath):
                filepath = os.path.join(self.trait_dir, '_texture', 'suit_' + get_scene().clone_props.gender)              
        elif Path(self.trait_dir).name.startswith('DNA'):
            geo_objects = get_objects_including('HeadGeo')
            filepath = os.path.join(self.trait_dir, '_texture')

            if not os.path.exists(filepath):
                filepath = os.path.join(self.trait_dir, '_textures')
        elif Path(self.trait_dir).name.startswith('Facial_Feature'):
            geo_objects = get_objects_including('HeadGeo')
            filepath = os.path.join(self.trait_dir, '_texture')

            if not os.path.exists(filepath):
                filepath = os.path.join(self.trait_dir, '_textures') 

            # The geo object for head is already known - apply feature immediately
            if self.trait_selected:
                apply_facial_feature(filepath)
            else:
                remove_facial_feature()
            
            return 

        if len(geo_objects) > 0:
            geo_object = geo_objects[0]

        if geo_object is not None:
            geo_mat = get_material_from_object(geo_object)

            if self.trait_selected and geo_mat in base_mats:
                apply_dna_textures_to_object(filepath, geo_object)
            elif not self.trait_selected and geo_mat not in base_mats:       
                remove_dna_textures_from_object(geo_object)
            else:
                print('Material state is out of sync, no action taken')
        
        return

def update_lighting_selected(self, context):
    lighting_col = get_collection(self.name)
    
    if self.lighting_selected:
        show_collection_viewport(lighting_col)
        show_collection_render(lighting_col)
    else:
        hide_collection_viewport(lighting_col)
        hide_collection_render(lighting_col)

def update_facial_feature(self, context):
    clone_props = get_scene().clone_props

    if clone_props.show_facial_feature:
        apply_facial_feature(None)
    else:
        remove_facial_feature()

def update_realistic_skin(self, context):
    clone_props = get_scene().clone_props
    render_engine = context.scene.render.engine

    head_mat = None

    try:
        head_mat = get_material_from_object(get_head_geo())
    except Exception as ex:
        print(ex)

    if head_mat:
        nodes = get_nodes(head_mat)
        bsdf_node = get_node(nodes, 'Principled BSDF')

        base_color_link = bsdf_node.inputs[0].links[0]
        base_color_node = base_color_link.from_node

        if clone_props.use_realistic_skin:
            # Connect the base color texture to the subsurface color input
            create_node_link(
                base_color_node.outputs[0],
                bsdf_node.inputs[BSDF_NODE_INDEX_DICT['SS_COLOR_INDEX']]
            )

            # Set the subsurface to a default that looks nice
            bsdf_node.inputs[BSDF_NODE_INDEX_DICT['SS_INDEX']].default_value = 0.1
        else:
            # Disconnect the base color texture from the subsurface color input
            ss_color_link = bsdf_node.inputs[BSDF_NODE_INDEX_DICT['SS_COLOR_INDEX']].links[0]
            node_tree = get_node_tree(head_mat)
            node_tree.links.remove(ss_color_link)

            # Set subsurface back to 0
            bsdf_node.inputs[BSDF_NODE_INDEX_DICT['SS_INDEX']].default_value = 0

        # Sync the material property with the state of checkbox in panel
        if render_engine == 'BLENDER_EEVEE':
            head_mat.use_sss_translucency = clone_props.use_realistic_skin

def update_bloom(self, context):
    ctglobals = context.window_manager.ctglobals

    if context.scene.render.engine == 'BLENDER_EEVEE':
        context.scene.eevee.use_bloom = ctglobals.use_bloom

def update_transparent(self, context):
    ctglobals = context.window_manager.ctglobals
    staging_coll = get_collection('Staging')

    for coll in staging_coll.children:
        if ctglobals.use_transparent:
            # Hide the world background
            hide_collection_viewport(coll)
            hide_collection_render(coll)
        else:
            show_collection_viewport(coll)
            show_collection_render(coll)

    context.scene.render.film_transparent = ctglobals.use_transparent

def format_trait_display_name(folder_name, gender):
    folder_name_tokenized = folder_name.split('-')
    gender_prefix = 'm_' if gender.lower() == 'male' else 'f_'

    trait_name = gender_prefix
    
    for idx, token in enumerate(folder_name_tokenized):
        if idx == 0:
            continue
        
        if token.lower() != 'combined':
            if token.startswith('_'):
                trait_name += token[1:].lower()
            else:
                trait_name += token.lower()

    return trait_name

def format_imported_style_name(filename, gender):
    gender_prefix = 'm_' if gender.lower() == 'male' else 'f_'
    style_name = re.sub('[^0-9a-zA-Z]+', '_', filename)

    if style_name.startswith(gender_prefix):
        return style_name
    else:
        return gender_prefix + style_name


def _pack_matches_gender(pack_data, selected_gender):
    """Return True when pack metadata appears to target selected gender."""
    gender = (selected_gender or "").lower()
    subdir = str(pack_data.get('pack_subdir', '')).lower()
    pack_name = str(pack_data.get('pack_name', '')).lower()
    if not gender:
        return True

    if subdir in {'male', 'female'}:
        return subdir == gender

    tokens = [t for t in re.split(r'[^a-z0-9]+', pack_name) if t]
    return gender in tokens

def _iter_pose_pack_dirs(cpdir):
    pose_dir = Path(os.path.join(cpdir, 'poses'))
    if not os.path.exists(pose_dir):
        return []
    return [d for d in pose_dir.iterdir() if d.is_dir()]

def _read_packinfo(pack_dir: Path):
    packinfo = pack_dir / 'packinfo.json'
    if not packinfo.exists():
        return None
    try:
        with packinfo.open('r') as handle:
            return json.load(handle)
    except Exception as ex:
        print(f"CloneX: Invalid pose pack metadata at '{packinfo}': {ex}")
        return None

def _pack_display_name(pack_data):
    return '[' + pack_data.get('pack_creator', 'Unknown') + '] ' + pack_data.get('pack_name', 'Unnamed Pack')

def get_pose_pack_blend_path(context, selected_pack_name):
    """Resolve the selected pose content pack name to a concrete .blend path."""
    if selected_pack_name == 'Current File':
        return None

    cpdir = get_content_packs_dir(context)
    for pack_dir in _iter_pose_pack_dirs(cpdir):
        data = _read_packinfo(pack_dir)
        if data is None:
            continue
        if _pack_display_name(data) != selected_pack_name:
            continue

        candidates = sorted(pack_dir.glob("*.blend"))
        if candidates:
            return str(candidates[0])

    return None

def _get_actions_from_blend(blend_path):
    if not blend_path or not os.path.exists(blend_path):
        return []

    cache_key = (blend_path, os.path.getmtime(blend_path))
    cached = _pose_action_cache.get(cache_key)
    if cached is not None:
        return cached

    for key in list(_pose_action_cache.keys()):
        if key[0] == blend_path and key != cache_key:
            _pose_action_cache.pop(key, None)

    try:
        with bpy.data.libraries.load(blend_path, link=False) as (data_from, _):
            actions = [name for name in data_from.actions if name]
    except Exception as ex:
        print(f"CloneX: Could not inspect pose actions in '{blend_path}': {ex}")
        actions = []

    _pose_action_cache[cache_key] = actions
    return actions

def get_pose_action_items(self, context):
    """Dropdown items for pose actions based on selected pose content pack."""
    wm = getattr(context, 'window_manager', None)
    if wm is None:
        return [('NONE', 'No Poses Found', 'No pose actions available')]

    selected_pack = getattr(wm, 'content_pack_poses', 'Current File')
    selected_gender = ''
    if context and getattr(context, 'scene', None) and hasattr(context.scene, 'clone_props'):
        selected_gender = getattr(context.scene.clone_props, 'gender', '').lower()

    action_names = []
    if selected_pack == 'Current File':
        action_names = [a.name for a in bpy.data.actions]
    else:
        blend_path = get_pose_pack_blend_path(context, selected_pack)
        action_names = _get_actions_from_blend(blend_path)

    if selected_gender:
        prefix = selected_gender.capitalize() + ' '
        gender_actions = [name for name in action_names if name.startswith(prefix)]
        if gender_actions:
            action_names = gender_actions

    seen = set()
    enum_items = []
    for name in action_names:
        if name in seen:
            continue
        seen.add(name)
        enum_items.append((name, name, 'Pose Action'))

    if not enum_items:
        enum_items.append(('NONE', 'No Poses Found', 'No pose actions available in selected pack'))
    return enum_items

def update_selected_pose_action(self, context):
    selected = getattr(self, 'selected_pose_action', '')
    if selected in {'', 'NONE'}:
        return

def _sync_selected_pose_action(context):
    wm = getattr(context, 'window_manager', None)
    if wm is None or not hasattr(wm, 'selected_pose_action'):
        return

    try:
        items = get_pose_action_items(wm, context)
    except Exception:
        return

    valid_ids = [identifier for identifier, _, _ in items]
    current = getattr(wm, 'selected_pose_action', '')
    if current not in valid_ids:
        wm.selected_pose_action = valid_ids[0] if valid_ids else 'NONE'

def get_pose_content_packs(self, context):
    cpdir = get_content_packs_dir(context)
    enum_items = [('Current File', 'Current File', 'Poses from Current File')]
    selected_gender = ''
    if context and getattr(context, 'scene', None) and hasattr(context.scene, 'clone_props'):
        selected_gender = getattr(context.scene.clone_props, 'gender', '').lower()

    if os.path.exists(cpdir):
        pose_dir = Path(os.path.join(cpdir, 'poses'))

        if os.path.exists(pose_dir):
            pose_packs = [d for d in pose_dir.iterdir() if d.is_dir()]
        
            for p in pose_packs:
                packinfo = os.path.join(p, 'packinfo.json')
                if not os.path.exists(packinfo):
                    continue
                try:
                    with open(packinfo, 'r') as pack:
                        data = json.load(pack)
                        pack_creator = data['pack_creator']
                        pack_name = data['pack_name']
                except Exception as ex:
                    print(f"CloneX: Invalid pose pack metadata at '{packinfo}': {ex}")
                    continue

                if selected_gender and not _pack_matches_gender(data, selected_gender):
                    continue

                pack_display_name = '[' + pack_creator + '] ' + pack_name
                enum_items.append((pack_display_name, pack_display_name, 'Pose Content Pack'))

    return enum_items

def get_anim_content_packs(self, context):
    cpdir = get_content_packs_dir(context)
    enum_items = [('Current File', 'Current File', 'Animations from Current File')]
    selected_gender = ''
    if context and getattr(context, 'scene', None) and hasattr(context.scene, 'clone_props'):
        selected_gender = getattr(context.scene.clone_props, 'gender', '').lower()

    if os.path.exists(cpdir):
        anim_dir = Path(os.path.join(cpdir, 'animations'))

        if os.path.exists(anim_dir):
            anim_packs = [d for d in anim_dir.iterdir() if d.is_dir()]
            
            for p in anim_packs:
                packinfo = os.path.join(p, 'packinfo.json')
                if not os.path.exists(packinfo):
                    continue
                try:
                    with open(packinfo, 'r') as pack:
                        data = json.load(pack)
                        pack_creator = data['pack_creator']
                        pack_name = data['pack_name']
                except Exception as ex:
                    print(f"CloneX: Invalid animation pack metadata at '{packinfo}': {ex}")
                    continue

                if selected_gender and not _pack_matches_gender(data, selected_gender):
                    continue

                pack_display_name = '[' + pack_creator + '] ' + pack_name
                enum_items.append((pack_display_name, pack_display_name, 'Animation Content Pack'))

    return enum_items


def ensure_content_pack_asset_libraries():
    """Ensure on-disk content pack folders are registered as asset libraries."""
    cpdir = get_content_packs_dir(bpy.context)
    if not os.path.exists(cpdir):
        return

    for pack_type in ('poses', 'animations'):
        type_dir = Path(os.path.join(cpdir, pack_type))
        if not type_dir.exists():
            continue

        for pack_dir in [d for d in type_dir.iterdir() if d.is_dir()]:
            packinfo_path = pack_dir / 'packinfo.json'
            if not packinfo_path.exists():
                continue

            try:
                with packinfo_path.open('r') as pack:
                    data = json.load(pack)
            except Exception as ex:
                print(f"CloneX: Could not parse packinfo '{packinfo_path}': {ex}")
                continue

            pack_creator = data.get('pack_creator', 'Unknown')
            pack_name = data.get('pack_name', pack_dir.name)
            library_name = '[' + pack_creator + '] ' + pack_name
            pack_path = str(pack_dir.resolve())

            existing = None
            for al in bpy.context.preferences.filepaths.asset_libraries:
                if al.path == pack_path or al.name == library_name:
                    existing = al
                    break

            if existing is None:
                try:
                    bpy.ops.preferences.asset_library_add(directory=pack_path)
                    for al in bpy.context.preferences.filepaths.asset_libraries:
                        if al.path == pack_path:
                            al.name = library_name
                            break
                    print(f"CloneX: Registered content pack library: {library_name}")
                except Exception as ex:
                    print(f"CloneX: Could not register content pack library '{library_name}': {ex}")
            else:
                existing.name = library_name

def update_staging_options(self, context):
    selected_option = context.window_manager.ctglobals.staging_options
    staging_coll = get_collection('Staging')

    if staging_coll:
        # Hide everything but the selected staging option
        for coll in staging_coll.children:
            if coll.name == selected_option:
                show_collection_viewport(coll)
                show_collection_render(coll)
                continue

            hide_collection_viewport(coll)
            hide_collection_render(coll)

def get_asset_catalog_names(self, context):
    catalog_names = []

    for al in context.preferences.filepaths.asset_libraries:
        if al.name == 'CloneX Style Library':
            # Parse the blender_assets.cats.txt file to populate the list
            # of valid asset catalog choices
            style_lib_path = Path(al.path)

            with (style_lib_path / 'blender_assets.cats.txt').open() as f:
                for line in f.readlines():
                    if line.startswith(("#", "VERSION", "\n")):
                        continue

                    # Each line contains : 'uuid:catalog_tree:catalog_name' + eol ('\n')
                    # We want to find the simple catalog names and add them to the enum
                    uuid = line.split(':')[0]
                    tree = line.split(':')[1]
                    name = line.split(':')[2].split('\n')[0]

                    # Skip parent tree items and DNA/Facial Feature items 
                    # since the custom import doesn't currently support textures
                    if tree != name and (not 'DNA' in name) and (not 'Facial' in name):
                        catalog_names.append((uuid, name, 'Style Library Category'))

    return catalog_names
    
def update_pose_content_pack(self, context):
    selected = getattr(self, 'content_pack_poses', 'Current File')
    if selected == 'Current File':
        set_asset_library_ref('LOCAL')
    else:
        set_asset_library_ref(selected)
    _sync_selected_pose_action(context)

def update_anim_content_pack(self, context):
    selected = getattr(self, 'content_pack_anims', 'Current File')
    if selected == 'Current File':
        set_asset_library_ref('LOCAL')
    else:
        set_asset_library_ref(selected)

def refresh_pose_panel(self, context):
    sync_type = context.window_manager.ctglobals.pose_or_animate
    bpy.ops.animation.refresh_content_packs(sync_type=sync_type)


def update_gender_content_pack(self, context):
    """Auto-select content packs matching the chosen Clone gender."""
    wm = getattr(context, 'window_manager', None)
    if wm is None:
        return

    selected_gender = ''
    if context and getattr(context, 'scene', None) and hasattr(context.scene, 'clone_props'):
        selected_gender = getattr(context.scene.clone_props, 'gender', '').lower()

    def pick_match(items):
        for identifier, label, _ in items:
            text = f"{identifier} {label}".lower()
            if selected_gender and selected_gender in text:
                return identifier
        return 'Current File'

    try:
        pose_items = get_pose_content_packs(wm, context)
        wm.content_pack_poses = pick_match(pose_items)
        _sync_selected_pose_action(context)
    except Exception as ex:
        print(f"CloneX: Could not auto-select pose pack for gender '{selected_gender}': {ex}")

    try:
        anim_items = get_anim_content_packs(wm, context)
        wm.content_pack_anims = pick_match(anim_items)
    except Exception as ex:
        print(f"CloneX: Could not auto-select animation pack for gender '{selected_gender}': {ex}")

def refresh_content_packs(self, context):
    ensure_content_pack_asset_libraries()
    bpy.ops.animation.refresh_content_packs(sync_type='pose')
    bpy.ops.animation.refresh_content_packs(sync_type='animate')

# === ENHANCED CLONE TOOLS SCALE & POSITIONING FIXES ===

def get_character_objects():
    """Get all character-related objects (head, body, armature)"""
    character_objects = []
    
    # Get head geometry
    head_geos = get_objects_including('HeadGeo')
    character_objects.extend(head_geos)
    
    # Get suit/body geometry  
    suit_geos = get_objects_including('SuitGeo')
    character_objects.extend(suit_geos)
    
    # Get armatures - implement our own function since get_all_armatures doesn't exist
    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            character_objects.append(obj)
    
    return character_objects

def get_trait_objects():
    """Get all trait objects from all m_ collections"""
    trait_objects = []
    
    try:
        for collection in get_all_collections():
            if collection.name.startswith('m_') or collection.name.startswith('f_'):
                objects = get_objects_from_collection(collection)
                trait_objects.extend(objects)
    except Exception as e:
        print(f"CloneX: Error getting trait objects: {e}")
    
    return trait_objects

def detect_scale_mismatch():
    """
    Detect if there's a scale mismatch between character and traits.
    Returns True if character is at ~0.01 scale and traits are at ~1.0 scale
    """
    character_objects = get_character_objects()
    trait_objects = get_trait_objects()
    
    if not character_objects or not trait_objects:
        print("CloneX: No character or trait objects found for scale detection")
        return False
    
    # Check character scale (should be close to 0.01 if there's a problem)
    character_scales = [max(obj.scale) for obj in character_objects if obj.type == 'MESH']
    trait_scales = [max(obj.scale) for obj in trait_objects if obj.type == 'MESH']
    
    if not character_scales or not trait_scales:
        return False
    
    avg_character_scale = sum(character_scales) / len(character_scales)
    avg_trait_scale = sum(trait_scales) / len(trait_scales)
    
    # Detect if character is ~100x smaller than traits
    scale_ratio = avg_trait_scale / avg_character_scale if avg_character_scale > 0 else 1
    
    print(f"CloneX: Scale Analysis - Character avg: {avg_character_scale:.3f}, Trait avg: {avg_trait_scale:.3f}, Ratio: {scale_ratio:.1f}")
    
    # If ratio is greater than 50, we likely have a mismatch
    if scale_ratio > 50:
        print("CloneX: ⚠️  SCALE MISMATCH DETECTED!")
        return True
    
    return False

def normalize_clone_scales():
    """
    Automatically detect and fix scale mismatches between character and traits.
    Normalizes all objects to scale 1.0
    """
    print("CloneX: 🔧 Starting scale normalization...")
    
    character_objects = get_character_objects()
    trait_objects = get_trait_objects()
    all_objects = character_objects + trait_objects
    
    if not all_objects:
        print("CloneX: No objects found to normalize")
        return False
    
    # Target scale is 1.0 for consistency
    target_scale = 1.0
    normalized_count = 0
    
    for obj in all_objects:
        if obj.type in ['MESH', 'ARMATURE']:
            current_scale = max(obj.scale)
            
            # Only normalize if significantly different from target
            if abs(current_scale - target_scale) > 0.001:
                # Calculate scale factor needed
                scale_factor = target_scale / current_scale if current_scale > 0 else 1.0
                
                # Apply uniform scaling
                obj.scale = (target_scale, target_scale, target_scale)
                
                # Also scale the object's dimensions if it's very small
                if current_scale < 0.1:
                    # For very small objects, also apply transform to make them visible
                    bpy.context.view_layer.objects.active = obj
                    obj.select_set(True)
                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                    obj.select_set(False)
                
                normalized_count += 1
                print(f"CloneX: Normalized {obj.name} from scale {current_scale:.3f} to {target_scale}")
    
    if normalized_count > 0:
        print(f"CloneX: ✅ Normalized {normalized_count} objects to scale {target_scale}")
        return True
    else:
        print("CloneX: All objects already at correct scale")
        return False

def get_character_reference_points():
    """Get key reference points on the character for trait positioning"""
    reference_points = {}
    
    try:
        # Get head geometry for facial positioning
        head_geo = get_head_geo()
        if head_geo:
            head_center = head_geo.location
            
            # Calculate head reference points
            reference_points['head_center'] = head_center
            reference_points['head_top'] = (head_center[0], head_center[1], head_center[2] + 0.15)
            reference_points['forehead'] = (head_center[0], head_center[1] - 0.05, head_center[2] + 0.05)
            reference_points['eye_level'] = (head_center[0], head_center[1] - 0.05, head_center[2])
            reference_points['mouth_level'] = (head_center[0], head_center[1] - 0.05, head_center[2] - 0.05)
            reference_points['face_forward'] = (head_center[0], head_center[1] - 0.1, head_center[2])
        else:
            # Default head positions if no head geometry found
            print("CloneX: Warning - No head geometry found, using default positions")
            reference_points['head_center'] = (0, 0, 1.7)
            reference_points['head_top'] = (0, 0, 1.85)
            reference_points['forehead'] = (0, -0.05, 1.75)
            reference_points['eye_level'] = (0, -0.05, 1.7)
            reference_points['mouth_level'] = (0, -0.05, 1.65)
            reference_points['face_forward'] = (0, -0.1, 1.7)
        
        # Get body geometry for body positioning
        suit_geo = get_suit_geo()
        if suit_geo:
            suit_center = suit_geo.location
            
            # Calculate body reference points
            reference_points['body_center'] = suit_center
            reference_points['chest_level'] = (suit_center[0], suit_center[1], suit_center[2] + 0.2)
            reference_points['waist_level'] = (suit_center[0], suit_center[1], suit_center[2])
            reference_points['feet_level'] = (suit_center[0], suit_center[1], suit_center[2] - 0.9)
        else:
            # Default body positions if no suit geometry found
            print("CloneX: Warning - No suit geometry found, using default positions")
            reference_points['body_center'] = (0, 0, 0.9)
            reference_points['chest_level'] = (0, 0, 1.1)
            reference_points['waist_level'] = (0, 0, 0.9)
            reference_points['feet_level'] = (0, 0, 0)
            
    except Exception as e:
        print(f"CloneX: Error getting character reference points: {e}")
        # Return safe default positions
        reference_points = {
            'head_center': (0, 0, 1.7),
            'head_top': (0, 0, 1.85),
            'forehead': (0, -0.05, 1.75),
            'eye_level': (0, -0.05, 1.7),
            'mouth_level': (0, -0.05, 1.65),
            'face_forward': (0, -0.1, 1.7),
            'body_center': (0, 0, 0.9),
            'chest_level': (0, 0, 1.1),
            'waist_level': (0, 0, 0.9),
            'feet_level': (0, 0, 0)
        }
    
    return reference_points

def detect_trait_type(trait_name):
    """Detect trait type based on collection name"""
    trait_lower = trait_name.lower()
    
    # Hair detection
    if 'hair' in trait_lower:
        return 'hair'
    
    # Eyewear detection  
    if any(keyword in trait_lower for keyword in ['eyewear', 'glasses', 'goggles', 'sunglass']):
        return 'eyewear'
    
    # Facial features
    if any(keyword in trait_lower for keyword in ['eyebrow', 'brow']):
        return 'eyebrows'
    if any(keyword in trait_lower for keyword in ['eye', 'iris', 'pupil']) and 'eyewear' not in trait_lower:
        return 'eyes'
    if any(keyword in trait_lower for keyword in ['mouth', 'lip', 'teeth']):
        return 'mouth'
    
    # Clothing detection
    if any(keyword in trait_lower for keyword in ['clothing', 'shirt', 'jacket', 'coat', 'top', 'bottom', 'pants', 'dress']):
        return 'clothing'
    
    # Footwear detection
    if any(keyword in trait_lower for keyword in ['shoe', 'boot', 'footwear', 'sneaker', 'sandal']):
        return 'footwear'
    
    # Jewelry detection
    if any(keyword in trait_lower for keyword in ['jewelry', 'necklace', 'earring', 'ring', 'chain', 'pendant']):
        return 'jewelry'
    
    # Default to accessory
    return 'accessory'

def position_trait_on_character(trait_collection, target_position):
    """Position a trait collection at the specified target position"""
    if not trait_collection or not target_position:
        return False
    
    trait_objects = get_objects_from_collection(trait_collection)
    if not trait_objects:
        return False

    # Never move collections that contain rigged meshes. Their placement should
    # come from armature binding, not object-level offsets.
    for obj in trait_objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE':
                print(f"CloneX: Skipping auto-position for rigged collection '{trait_collection.name}'")
                return False
    
    print(f"CloneX: Positioning {trait_collection.name} at {target_position}")
    
    # Move all objects in the collection to the target position
    for obj in trait_objects:
        if obj.type == 'MESH':
            # Set object location to target position
            obj.location = target_position
            print(f"CloneX: Moved {obj.name} to {target_position}")
    
    return True

def auto_position_traits():
    """
    Automatically position all traits on character based on trait type.
    Returns True if any positioning was performed.
    """
    print("CloneX: 🎯 Starting automatic trait positioning...")
    
    character_head = get_head_geo()
    character_body = get_suit_geo()
    
    if not character_head and not character_body:
        print("CloneX: No character found for positioning")
        return False
    
    # Get reference points for positioning
    reference_points = get_character_reference_points()
    if not reference_points:
        print("CloneX: Could not determine character reference points")
        return False
    
    # Define positioning rules
    positioning_rules = {
        'hair': reference_points.get('head_top', (0, 0, 0.15)),
        'eyewear': reference_points.get('face_forward', (0, -0.1, 0)),
        'eyebrows': reference_points.get('forehead', (0, -0.05, 0.05)),
        'eyes': reference_points.get('eye_level', (0, -0.05, 0)),
        'mouth': reference_points.get('mouth_level', (0, -0.05, -0.05)),
        'jewelry': reference_points.get('chest_level', (0, 0, 0.2)),
        'clothing': reference_points.get('body_center', (0, 0, 0)),
        'footwear': reference_points.get('feet_level', (0, 0, -0.9)),
        'accessory': reference_points.get('chest_level', (0, 0, 0.2))
    }
    
    positioned_count = 0
    
    # Apply positions only to non-rigged accessory collections.
    for collection in get_all_collections():
        # Never reposition base character collections.
        if 'character' in collection.name.lower():
            continue

        if collection.name.startswith('m_') or collection.name.startswith('f_'):
            trait_type = detect_trait_type(collection.name)
            
            if trait_type in positioning_rules:
                target_position = positioning_rules[trait_type]
                if position_trait_on_character(collection, target_position):
                    positioned_count += 1
            else:
                print(f"CloneX: Unknown trait type for {collection.name}, using default positioning")
                if position_trait_on_character(collection, positioning_rules['accessory']):
                    positioned_count += 1
    
    if positioned_count > 0:
        print(f"CloneX: ✅ Positioned {positioned_count} trait collections")
        return True
    else:
        print("CloneX: No traits found to position")
        return False

def get_m_collections():
    """Get all collections that start with 'm_' or 'f_' (trait collections)"""
    m_collections = []
    
    for collection in get_all_collections():
        if collection.name.startswith('m_') or collection.name.startswith('f_'):
            m_collections.append(collection.name)
    
    return m_collections

def get_registered_traits():
    """Get list of traits currently registered in the Style panel"""
    clone_props = get_scene().clone_props
    registered_traits = []
    
    for trait in clone_props.trait_collection:
        registered_traits.append(trait.name)
    
    return registered_traits

def force_register_all_traits():
    """
    Force register all m_ collections in the Style panel that aren't already registered.
    Returns the number of newly registered traits.
    """
    print("CloneX: 📋 Force registering all traits...")
    
    scene_collections = get_m_collections()
    registered_traits = get_registered_traits()
    clone_props = get_scene().clone_props
    
    newly_registered = 0
    
    for collection_name in scene_collections:
        if collection_name not in registered_traits:
            # Add to trait collection
            trait = clone_props.trait_collection.add()
            trait.name = collection_name
            trait.trait_selected = True  # Mark as equipped since it's loaded
            
            newly_registered += 1
            print(f"CloneX: Registered trait: {collection_name}")
    
    if newly_registered > 0:
        print(f"CloneX: ✅ Registered {newly_registered} new traits in Style panel")
    else:
        print("CloneX: All traits already registered")
    
    return newly_registered

def validate_import_success():
    """
    Validate that the Clone import was successful.
    Returns a dict with validation results.
    """
    print("CloneX: 🔍 Validating import success...")
    
    validation_results = {
        'character_found': False,
        'traits_found': 0,
        'scale_consistent': True,
        'traits_positioned': True,
        'traits_registered': True,
        'all_checks_passed': False
    }
    
    # Check 1: Character objects exist
    character_objects = get_character_objects()
    validation_results['character_found'] = len(character_objects) > 0
    
    # Check 2: Trait objects exist
    trait_objects = get_trait_objects()
    validation_results['traits_found'] = len(trait_objects)
    
    # Check 3: Scale consistency
    if character_objects and trait_objects:
        validation_results['scale_consistent'] = not detect_scale_mismatch()
    
    # Check 4: Traits positioned (not all at origin)
    if trait_objects:
        at_origin_count = 0
        for obj in trait_objects:
            if obj.type == 'MESH':
                location = obj.location
                if abs(location[0]) < 0.001 and abs(location[1]) < 0.001 and abs(location[2]) < 0.001:
                    at_origin_count += 1
        
        # If more than 50% of traits are at origin, positioning likely failed
        validation_results['traits_positioned'] = (at_origin_count / len(trait_objects)) < 0.5
    
    # Check 5: All traits registered in Style panel
    scene_collections = get_m_collections()
    registered_traits = get_registered_traits()
    missing_count = len(scene_collections) - len(registered_traits)
    validation_results['traits_registered'] = missing_count == 0
    
    # Overall validation
    validation_results['all_checks_passed'] = (
        validation_results['character_found'] and
        validation_results['traits_found'] > 0 and
        validation_results['scale_consistent'] and
        validation_results['traits_positioned'] and
        validation_results['traits_registered']
    )
    
    # Print validation summary
    print("CloneX: === Import Validation Results ===")
    print(f"Character found: {'✅' if validation_results['character_found'] else '❌'}")
    print(f"Traits found: {validation_results['traits_found']}")
    print(f"Scale consistent: {'✅' if validation_results['scale_consistent'] else '❌'}")
    print(f"Traits positioned: {'✅' if validation_results['traits_positioned'] else '❌'}")
    print(f"Traits registered: {'✅' if validation_results['traits_registered'] else '❌'}")
    print(f"Overall success: {'✅' if validation_results['all_checks_passed'] else '❌'}")
    
    return validation_results

def enhanced_clone_import():
    """
    Complete automatic Clone import with all fixes applied.
    This function should be called after the basic import is complete.
    Respects user preferences for which fixes to apply.
    """
    print("CloneX: 🚀 Starting Enhanced Clone Import fixes...")
    
    try:
        clone_props = get_scene().clone_props
        success_steps = []
        
        # Step 1: Auto-detect and fix scales (if enabled)
        if clone_props.auto_fix_scale:
            try:
                if detect_scale_mismatch():
                    if normalize_clone_scales():
                        success_steps.append("Scale normalization")
                else:
                    print("CloneX: No scale issues detected")
                    success_steps.append("Scale verification")
            except Exception as e:
                print(f"CloneX: Error during scale fixing: {e}")
        else:
            print("CloneX: Scale fixing disabled in preferences")
        
        # Step 2: Auto-position traits (disabled for rigged import stability)
        if clone_props.auto_position_traits:
            try:
                print("CloneX: Auto-positioning is disabled for rigged Blender 5.0 imports")
            except Exception as e:
                print(f"CloneX: Error during trait positioning: {e}")
        else:
            print("CloneX: Auto-positioning disabled in preferences")
        
        # Step 3: Force register all traits in Style panel (if enabled)
        if clone_props.auto_register_traits:
            try:
                registered_count = force_register_all_traits()
                if registered_count >= 0:  # Even 0 is success (all already registered)
                    success_steps.append("Trait registration")
            except Exception as e:
                print(f"CloneX: Error during trait registration: {e}")
        else:
            print("CloneX: Auto-registration disabled in preferences")
        
        # Step 4: Validate import completeness (if enabled)
        validation = {'all_checks_passed': True}  # Default fallback
        if clone_props.show_import_validation:
            try:
                validation = validate_import_success()
                success_steps.append("Validation")
                if validation['all_checks_passed']:
                    print("CloneX: ✅ Enhanced Clone Import Complete - All checks passed!")
                else:
                    print("CloneX: ⚠️  Enhanced Clone Import completed with some issues")
            except Exception as e:
                print(f"CloneX: Error during validation: {e}")
        
        return validation
        
    except Exception as e:
        print(f"CloneX: Critical error in enhanced_clone_import: {e}")
        # Return a safe default validation result
        return {
            'character_found': False,
            'traits_found': 0,
            'scale_consistent': False,
            'traits_positioned': False,
            'traits_registered': False,
            'all_checks_passed': False
        }

# === DEBUGGING AND ANALYSIS FUNCTIONS ===

def analyze_clone_scales():
    """Debug function to analyze current scale state"""
    print("CloneX: === Clone Scale Analysis ===")
    
    character_objects = get_character_objects()
    trait_objects = get_trait_objects()
    
    print(f"Character objects: {len(character_objects)}")
    for obj in character_objects:
        if obj.type in ['MESH', 'ARMATURE']:
            print(f"  {obj.name}: scale {obj.scale}, dims {obj.dimensions}")
    
    print(f"Trait objects: {len(trait_objects)}")
    for obj in trait_objects:
        if obj.type == 'MESH':
            print(f"  {obj.name}: scale {obj.scale}, dims {obj.dimensions}")
    
    # Detect mismatches
    all_objects = character_objects + trait_objects
    mesh_objects = [obj for obj in all_objects if obj.type == 'MESH']
    
    if mesh_objects:
        scales = [max(obj.scale) for obj in mesh_objects]
        scale_ratio = max(scales) / min(scales) if min(scales) > 0 else 1
        
        print(f"Scale range: {min(scales):.3f} to {max(scales):.3f}")
        print(f"Scale ratio: {scale_ratio:.1f}")
        
        if scale_ratio > 10:
            print("⚠️  SCALE MISMATCH DETECTED!")
            return False
    
    print("✅ Scale analysis complete")
    return True

def analyze_trait_positions():
    """Debug function to analyze trait positioning"""
    print("CloneX: === Trait Position Analysis ===")
    
    trait_objects = get_trait_objects()
    reference_points = get_character_reference_points()
    
    print(f"Reference points available: {list(reference_points.keys())}")
    print(f"Trait objects found: {len(trait_objects)}")
    
    at_origin_count = 0
    for obj in trait_objects:
        if obj.type == 'MESH':
            loc = obj.location
            print(f"  {obj.name}: location {loc}")
            
            if abs(loc[0]) < 0.001 and abs(loc[1]) < 0.001 and abs(loc[2]) < 0.001:
                at_origin_count += 1
    
    if at_origin_count > 0:
        print(f"⚠️  {at_origin_count} objects at world origin (may need positioning)")
    else:
        print("✅ All traits positioned away from origin")
    
    return at_origin_count == 0

def debug_trait_registration():
    """Debug function to check trait registration status"""
    print("CloneX: === Trait Registration Debug ===")
    
    scene_collections = get_m_collections()
    registered_traits = get_registered_traits()
    
    print(f"Scene collections with m_/f_ prefix: {len(scene_collections)}")
    for collection_name in scene_collections:
        print(f"  Collection: {collection_name}")
    
    print(f"Registered in Style panel: {len(registered_traits)}")
    for trait_name in registered_traits:
        print(f"  Registered: {trait_name}")
    
    missing_traits = [name for name in scene_collections if name not in registered_traits]
    if missing_traits:
        print(f"⚠️  Missing from Style panel: {missing_traits}")
        return False
    else:
        print("✅ All traits registered in Style panel")
        return True
