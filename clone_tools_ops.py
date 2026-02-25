import bpy, addon_utils, os, zipfile, webbrowser, shutil, json, time, csv, tempfile, uuid, hashlib, math
import mathutils

from pathlib import Path
from bpy.types import Operator, Action, Object, FCurve, UIList, Context
from bpy.props import StringProperty, BoolProperty, EnumProperty, IntProperty
from bpy.utils import register_class, unregister_class
from bpy_extras.io_utils import ImportHelper

from . import clone_tools_utils as ctutils
from .clone_tools_compat import (
    get_asset_full_library_path,
    get_asset_id_type,
    get_asset_name,
    get_context_asset,
    is_local_asset,
)
from .lib.easybpy import *
from . import blendshape_renamer

# === Windows Long Path Support Functions ===

def get_short_path_name(long_path):
    """
    Get Windows short path name (8.3 format) to work around MAX_PATH limitations.
    Falls back to original path if conversion fails.
    """
    if os.name != 'nt':  # Only needed on Windows
        return long_path
        
    try:
        import ctypes
        from ctypes import wintypes
        
        # Get required buffer size
        buffer_size = ctypes.windll.kernel32.GetShortPathNameW(long_path, None, 0)
        if buffer_size:
            short_path_buffer = ctypes.create_unicode_buffer(buffer_size)
            ctypes.windll.kernel32.GetShortPathNameW(long_path, short_path_buffer, buffer_size)
            return short_path_buffer.value
    except:
        pass
    
    return long_path

def create_safe_temp_dir(base_name="clonex_extract"):
    """
    Create a temporary directory with a very short path to avoid Windows path length issues.
    Uses the shortest possible path combinations.
    """
    # Use system temp directory which is typically shorter
    temp_base = tempfile.gettempdir()
    
    # Create very short unique identifier using hash
    hash_obj = hashlib.md5(base_name.encode())
    short_id = hash_obj.hexdigest()[:4]  # Reduced from 8 to 4 characters
    
    # Create temp directory with very short name
    temp_dir = os.path.join(temp_base, f"c{short_id}")  # Even shorter prefix
    
    # Ensure directory exists
    try:
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir
    except:
        # Fallback to ultra-short path directly in temp root
        fallback_dir = os.path.join(temp_base, short_id)
        try:
            os.makedirs(fallback_dir, exist_ok=True)
            return fallback_dir
        except:
            # Last resort: use just numbers
            import random
            numeric_id = str(random.randint(1000, 9999))
            final_dir = os.path.join(temp_base, numeric_id)
            os.makedirs(final_dir, exist_ok=True)
            return final_dir

def safe_extractall(zip_ref, extract_path, max_path_length=200):
    """
    Safely extract ZIP files with Windows long path handling.
    Uses even more aggressive path length limits and temporary short paths.
    """
    import platform
    
    # Check if we're on Windows and path might be too long
    is_windows = platform.system() == 'Windows'
    needs_short_path = is_windows and len(extract_path) > max_path_length
    
    # Also check if any files in the ZIP would create long paths
    if not needs_short_path and is_windows:
        try:
            for zip_info in zip_ref.infolist():
                potential_path = os.path.join(extract_path, zip_info.filename)
                if len(potential_path) > max_path_length:
                    needs_short_path = True
                    print(f"CloneX: Detected potential long path in ZIP: {len(potential_path)} chars")
                    break
        except:
            pass
    
    if needs_short_path:
        print(f"CloneX: Long path detected ({len(extract_path)} chars), using temp extraction...")
        
        # Create temporary extraction directory with very short path
        temp_extract_dir = create_safe_temp_dir(os.path.basename(extract_path))
        
        try:
            # Extract to temporary directory first
            zip_ref.extractall(temp_extract_dir)
            
            # Create final destination directory
            os.makedirs(extract_path, exist_ok=True)
            
            # Move files from temp to final destination with progress
            file_count = 0
            for root, dirs, files in os.walk(temp_extract_dir):
                # Calculate relative path from temp directory
                rel_path = os.path.relpath(root, temp_extract_dir)
                if rel_path == '.':
                    dest_root = extract_path
                else:
                    dest_root = os.path.join(extract_path, rel_path)
                
                # Create destination directories
                if not os.path.exists(dest_root):
                    try:
                        os.makedirs(dest_root, exist_ok=True)
                    except Exception as e:
                        print(f"CloneX: Warning - Could not create directory {dest_root}: {e}")
                        continue
                
                # Move files
                for file in files:
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(dest_root, file)
                    
                    try:
                        shutil.move(src_file, dest_file)
                        file_count += 1
                    except Exception as e:
                        print(f"CloneX: Warning - Could not move {file}: {e}")
                        # Try copying instead
                        try:
                            shutil.copy2(src_file, dest_file)
                            file_count += 1
                        except Exception as e2:
                            print(f"CloneX: Error - Could not copy {file}: {e2}")
            
            print(f"CloneX: Successfully moved {file_count} files to {extract_path}")
            
        except Exception as e:
            print(f"CloneX: Extraction error: {e}")
            raise
        finally:
            # Clean up temporary directory
            try:
                shutil.rmtree(temp_extract_dir, ignore_errors=True)
            except:
                pass
    else:
        # Standard extraction for normal length paths
        zip_ref.extractall(extract_path)

def get_safe_folder_name(zip_path, base_directory=None, max_length=80, max_windows_path=200):
    """
    Return extraction folder name derived from the ZIP filename.
    Keep original naming on non-Windows; shorten only on Windows when needed.
    """
    base_name = os.path.splitext(os.path.basename(zip_path))[0]

    # Preserve naming convention outside Windows.
    if os.name != 'nt':
        return base_name

    # If caller provided target directory, only shorten when full path is at risk.
    if base_directory:
        candidate = os.path.join(base_directory, base_name)
        if len(candidate) < max_windows_path and len(base_name) <= max_length:
            return base_name
    elif len(base_name) <= max_length:
        return base_name

    hash_obj = hashlib.md5(base_name.encode())
    short_hash = hash_obj.hexdigest()[:6]
    short_part_length = max(max_length - 8, 10)
    safe_name = f"{base_name[:short_part_length]}_{short_hash}"

    if len(safe_name) > max_length:
        safe_name = f"cx_{short_hash}"

    print(f"CloneX: Shortened folder name from '{base_name}' to '{safe_name}'")
    return safe_name

# === End Long Path Support Functions ===

def _dir_has_gender_base_blend(dir_path: Path, gender: str) -> bool:
    marker = os.path.join(f"_{gender}", "_blender")
    try:
        for root, _, files in os.walk(str(dir_path)):
            normalized_root = root.replace("\\", "/")
            if marker not in normalized_root:
                continue
            for file in files:
                if file.startswith("."):
                    continue
                if file.lower().endswith(".blend"):
                    return True
    except Exception:
        return False
    return False

def _is_character_blend_name(path_str: str) -> bool:
    filename = os.path.basename(path_str).lower()
    # Base character packs consistently include "character" in blend filename.
    return "character" in filename and filename.endswith(".blend")


def _dir_has_gender_character_blend(dir_path: Path, gender: str) -> bool:
    marker = os.path.join(f"_{gender}", "_blender")
    try:
        for root, _, files in os.walk(str(dir_path)):
            normalized_root = root.replace("\\", "/")
            if marker not in normalized_root:
                continue
            for file in files:
                if file.startswith("."):
                    continue
                rel = f"{normalized_root}/{file}"
                if _is_character_blend_name(rel):
                    return True
    except Exception:
        return False
    return False


def _zip_has_gender_base_blend(zip_path: Path, gender: str) -> bool:
    marker = f"_{gender}/_blender/".lower()
    try:
        with zipfile.ZipFile(str(zip_path)) as zf:
            for name in zf.namelist():
                normalized = name.replace("\\", "/").lower()
                if marker in normalized and normalized.lower().endswith(".blend"):
                    return True
    except Exception:
        return False
    return False

def _zip_has_gender_character_blend(zip_path: Path, gender: str) -> bool:
    marker = f"_{gender}/_blender/".lower()
    try:
        with zipfile.ZipFile(str(zip_path)) as zf:
            for name in zf.namelist():
                normalized = name.replace("\\", "/").lower()
                if marker in normalized and _is_character_blend_name(normalized):
                    return True
    except Exception:
        return False
    return False


def _detect_base_gender_availability(root_dir: Path):
    availability = {"male": False, "female": False, "found_base": False}
    entries = list(root_dir.iterdir())
    zip_entries = [p for p in entries if p.suffix.lower() == ".zip"]
    # Prefer zip packages when present to avoid expensive recursive scans over
    # previously extracted directories in cloud-synced folders.
    candidates = zip_entries if zip_entries else entries

    for path in candidates:
        if path.is_dir():
            has_m = _dir_has_gender_character_blend(path, "male")
            has_f = _dir_has_gender_character_blend(path, "female")
        elif path.suffix.lower() == ".zip":
            has_m = _zip_has_gender_character_blend(path, "male")
            has_f = _zip_has_gender_character_blend(path, "female")
        else:
            continue

        if has_m or has_f:
            availability["found_base"] = True
            availability["male"] = availability["male"] or has_m
            availability["female"] = availability["female"] or has_f
    return availability

def _zip_relevant_for_gender(zip_path: Path, gender: str, is_base_pack: bool) -> bool:
    """Fast zip prefilter to avoid extracting irrelevant packs."""
    selected_blender_marker = f"_{gender}/_blender/".lower()
    texture_markers = ("_texture/", "_textures/")
    opposite_gender = "female" if gender == "male" else "male"
    opposite_blender_marker = f"_{opposite_gender}/_blender/".lower()

    try:
        with zipfile.ZipFile(str(zip_path)) as zf:
            names = [n.replace("\\", "/").lower() for n in zf.namelist()]
    except Exception:
        return True

    has_selected_blend = any(
        selected_blender_marker in n and n.lower().endswith(".blend")
        for n in names
    )
    has_opposite_blend = any(
        opposite_blender_marker in n and n.lower().endswith(".blend")
        for n in names
    )
    has_any_blend_payload = any("_blender/" in n and n.endswith(".blend") for n in names)
    has_textures = any(
        any(marker in n for marker in texture_markers)
        for n in names
    )

    if is_base_pack:
        # Base packs must contain selected gender blend data.
        return has_selected_blend

    # Trait packs are relevant when they contain selected gender blend payloads.
    if has_selected_blend:
        return True

    # If pack has blend payloads but none for selected gender, skip to avoid
    # wrong-gender trait loading.
    if has_any_blend_payload and not has_selected_blend:
        return False

    # Texture-only packs may still be relevant.
    if has_textures:
        return True

    # Explicitly reject opposite-gender-only payloads.
    if has_opposite_blend and not has_selected_blend:
        return False

    # Unknown structure: keep to avoid false negatives that skip valid packs.
    return True


class CT_OT_CloneSelectOperator(Operator):
    """Use the file browser to select the folder containing your 3D files"""
    
    bl_idname = "ct.clone_select_operator"
    bl_label = "Select Location"

    directory: StringProperty(options={'HIDDEN'})
    filter_folder: BoolProperty(default=False, options={'HIDDEN'})
    
    def execute(self, context):
        clone_props = get_scene().clone_props
        # Auto-positioning rigged traits can break assembly in Blender 5.0 workflows.
        # Force-disable it at import time for stable rig binding.
        clone_props.auto_position_traits = False
        clone_props.trait_collection.clear()
        clone_props.home_dir = self.directory

        # Fast preflight: if a base pack exists but doesn't contain the selected
        # gender payload, fail early instead of entering a long import/extract path.
        availability = _detect_base_gender_availability(Path(self.directory))
        if availability["found_base"]:
            selected_gender = clone_props.gender.lower()
            opposite_gender = "female" if selected_gender == "male" else "male"
            if not availability.get(selected_gender, False) and availability.get(opposite_gender, False):
                self.report(
                    {'ERROR'},
                    f"Selected gender '{selected_gender}' but only '{opposite_gender}' base assets were found in this folder."
                )
                print(
                    "CloneX: Preflight failed - selected gender assets are missing. "
                    f"selected={selected_gender}, available={availability}"
                )
                return {'CANCELLED'}
        
        # If CloneX Style Library doesn't exist yet, setup the asset catalog
        # for the current file
        library_exists = False

        for al in bpy.context.preferences.filepaths.asset_libraries:
            if al.name == 'CloneX Style Library':
                library_exists = True
        
        if not library_exists:
            src_path = os.path.join(Path(__file__).resolve().parent, 'assets', 'blender_assets.cats.txt')
            dest_path = os.path.join(clone_props.home_dir, 'blender_assets.cats.txt')
            shutil.copy(src_path, dest_path)
            # Avoid blocking saves into cloud-synced import folders during import.
            # Users can save manually after import if needed.
        else:
            # If the asset library already exists, copy the catalog so it can be used in
            # the local file and load the existing assets into the working file
            style_lib_path = ''

            for al in bpy.context.preferences.filepaths.asset_libraries:
                if al.name == 'CloneX Style Library':
                    style_lib_path = al.path

            if style_lib_path != '':
                src_path = os.path.join(style_lib_path, 'blender_assets.cats.txt')
                dest_path = os.path.join(clone_props.home_dir, 'blender_assets.cats.txt')
                shutil.copy(src_path, dest_path)

                with bpy.data.libraries.load(
                        os.path.join(style_lib_path, 'clonex_style_library.blend'),
                        assets_only=True) as (data_from, data_to):
                    data_to.collections = data_from.collections
                    data_to.materials = data_from.materials

        trait_dir_paths = []

        entries = list(Path(self.directory).iterdir())
        zip_entries = [p for p in entries if p.suffix.lower() == '.zip']
        # If zip packs exist, process only zips to avoid rescanning extracted
        # directories from previous runs (major source of perceived hangs).
        input_entries = zip_entries if zip_entries else entries

        # Load the base clone objects
        for path in input_entries:
            # Do not rely on pack filename conventions (e.g. generic Combined.zip).
            if path.is_dir():
                is_base_path = _dir_has_gender_character_blend(path, clone_props.gender.lower())
            elif path.suffix.lower() == '.zip':
                is_base_path = _zip_has_gender_character_blend(path, clone_props.gender.lower())
            else:
                is_base_path = False
            trait_dir_path = ''
            
            if path.suffix == '.zip':
                if not _zip_relevant_for_gender(path, clone_props.gender.lower(), is_base_path):
                    print(
                        f"CloneX: Skipping zip '{path.name}' - "
                        f"no selected gender ('{clone_props.gender}') payload found."
                    )
                    continue

                # Generate safe folder name to avoid Windows path length issues
                folder_name = get_safe_folder_name(str(path), base_directory=self.directory)
                trait_dir_path = os.path.join(self.directory, folder_name)

                # Unzip if zip file and directory doesn't already exist
                if not Path(trait_dir_path).is_dir():             
                    try:
                        print(f"CloneX: Extracting {path.name}...")
                        print(f"CloneX: Target path length: {len(trait_dir_path)} characters")
                        
                        # Use safe extraction method for Windows long path support
                        with zipfile.ZipFile(path) as zip_ref:
                            safe_extractall(zip_ref, trait_dir_path)
                        
                        print(f"CloneX: Successfully extracted {path.name}")
                        
                    except Exception as e:
                        print(f"CloneX: Error extracting {path.name}: {str(e)}")
                        # Try multiple fallback approaches for extremely long paths
                        success = False
                        
                        # Fallback 1: Ultra-short folder name with hash
                        if not success:
                            try:
                                hash_obj = hashlib.md5(str(path).encode())
                                ultra_short_name = f"cx_{hash_obj.hexdigest()[:6]}"
                                fallback_path1 = os.path.join(self.directory, ultra_short_name)
                                
                                print(f"CloneX: Trying ultra-short extraction to {ultra_short_name}...")
                                
                                with zipfile.ZipFile(path) as zip_ref:
                                    safe_extractall(zip_ref, fallback_path1)
                                
                                trait_dir_path = fallback_path1
                                success = True
                                print(f"CloneX: Ultra-short extraction successful")
                                
                            except Exception as e2:
                                print(f"CloneX: Ultra-short extraction failed: {str(e2)}")
                        
                        # Fallback 2: Use Windows temp directory for even shorter paths
                        if not success:
                            try:
                                import tempfile
                                temp_base = tempfile.gettempdir()  # Usually C:\Users\USER\AppData\Local\Temp
                                hash_obj = hashlib.md5(str(path).encode())
                                temp_name = f"cx{hash_obj.hexdigest()[:4]}"  # Very short: cx1a2b
                                fallback_path2 = os.path.join(temp_base, temp_name)
                                
                                print(f"CloneX: Trying temp directory extraction to {temp_name}...")
                                
                                with zipfile.ZipFile(path) as zip_ref:
                                    safe_extractall(zip_ref, fallback_path2)
                                
                                # Create a symlink or copy to the intended location if possible
                                try:
                                    # Try to create a junction/symlink
                                    import subprocess
                                    result = subprocess.run([
                                        'mklink', '/J', trait_dir_path, fallback_path2
                                    ], shell=True, capture_output=True, text=True)
                                    
                                    if result.returncode == 0:
                                        print(f"CloneX: Created junction link to temp extraction")
                                    else:
                                        # If junction fails, just use the temp path directly
                                        trait_dir_path = fallback_path2
                                        print(f"CloneX: Using temp directory directly")
                                    
                                except Exception:
                                    # If junction fails, just use the temp path
                                    trait_dir_path = fallback_path2
                                    print(f"CloneX: Using temp directory fallback")
                                
                                success = True
                                print(f"CloneX: Temp directory extraction successful")
                                
                            except Exception as e3:
                                print(f"CloneX: Temp directory extraction failed: {str(e3)}")
                        
                        # Fallback 3: Try direct to C:\ root for absolute shortest paths
                        if not success:
                            try:
                                hash_obj = hashlib.md5(str(path).encode())
                                root_name = f"c{hash_obj.hexdigest()[:3]}"  # Ultra short: c1a2
                                fallback_path3 = os.path.join("C:\\", root_name)
                                
                                print(f"CloneX: Trying root directory extraction to {root_name}...")
                                
                                with zipfile.ZipFile(path) as zip_ref:
                                    safe_extractall(zip_ref, fallback_path3)
                                
                                trait_dir_path = fallback_path3
                                success = True
                                print(f"CloneX: Root directory extraction successful")
                                print(f"CloneX: WARNING - Files extracted to {fallback_path3} due to path limits")
                                
                            except Exception as e4:
                                print(f"CloneX: Root directory extraction failed: {str(e4)}")
                        
                        if not success:
                            self.report({'ERROR'}, f"Could not extract {path.name}: All extraction methods failed")
                            print(f"CloneX: CRITICAL - All extraction attempts failed for {path.name}")
                            continue  # Skip this file and continue with others

                # Always resolve to the extracted folder path, whether it was
                # created in this run or already existed from prior imports.
                path = Path(trait_dir_path)
            else:
                trait_dir_path = Path(os.path.join(self.directory, path.name))  

            if path.is_dir():
                # Some extraction paths use shortened folder names that do not end with
                # "Combined". Detect trait/base packages by expected internal structure.
                nested_combined = [p for p in path.iterdir() if p.is_dir() and p.name.endswith('Combined')]
                if path.name.endswith('Combined'):
                    normalized_path = path
                elif len(nested_combined) == 1:
                    normalized_path = nested_combined[0]
                else:
                    has_gender_blender = (path / f"_{clone_props.gender}" / "_blender").is_dir()
                    has_texture_dir = (path / "_texture").is_dir() or (path / "_textures").is_dir()
                    if has_gender_blender or has_texture_dir:
                        normalized_path = path
                    else:
                        continue

                path = normalized_path
                trait_dir_path = str(path)
                if not is_base_path:
                    is_base_path = _dir_has_gender_character_blend(path, clone_props.gender.lower())

                if is_base_path:
                    armature = get_object('Genesis8_1' + clone_props.gender.capitalize())
                    
                    # If the armature already exists delete it to avoid duplicate issues
                    if armature:
                        delete_object(armature)

                    try:
                        full_path = os.path.join(trait_dir_path, '_' + clone_props.gender, '_blender')
                        blend_file = ctutils.alistdir(full_path)[0]
                        base_clone_filepath = os.path.join(full_path, blend_file) 

                        if not collection_exists('Character'):
                            create_collection('Character')

                        # Always load base objects when missing, even if Character collection already exists.
                        if get_object('Genesis8_1' + clone_props.gender.capitalize()) is None:
                            with bpy.data.libraries.load(base_clone_filepath) as (data_from, data_to):
                                data_to.objects = data_from.objects

                            link_objects_to_collection(data_to.objects, get_collection('Character'))

                            # Mark the base head and suit materials as assets
                            # :TODO: Refactor this logic
                            head_mat = get_material('Head')
                            head_mat_name = 'dna_head_human'
                            
                            if not ctutils.is_material_asset(head_mat_name):
                                head_mat.name = head_mat_name
                                head_mat.asset_mark()
                                head_mat.asset_generate_preview()
                            else:
                                ctutils.get_head_geo().material_slots[0].material = get_material(head_mat_name)

                            suit_mat = get_material('Suit')
                            suit_mat_name = f"{'f_' if clone_props.gender.lower() == 'female' else 'm_'}suit"
                            
                            if not ctutils.is_material_asset(suit_mat_name):
                                suit_mat.name = suit_mat_name
                                suit_mat.asset_mark()
                                suit_mat.asset_generate_preview()
                            else:
                                ctutils.get_suit_geo().material_slots[0].material = get_material(suit_mat_name)
                    except Exception as ex:
                        self.report({'ERROR'}, f"Invalid path to blend file for selected gender '{clone_props.gender}': {ex}")
                        print(
                            "CloneX: Base character load failed; aborting import. "
                            f"gender={clone_props.gender}, path={trait_dir_path}, error={ex}"
                        )
                        return {'CANCELLED'}

                else:
                    trait_dir_paths.append(path)  

        # All directories should be extracted now so we can load traits and update armature mods
        for trait_dir_path in trait_dir_paths:
            trait_dir_name = trait_dir_path.name.lower()
            trait_display_name = ctutils.format_trait_display_name(trait_dir_path.name, clone_props.gender)
            
            if 'dna' in trait_dir_name:
                # This is a texture for the head
                head_geo = ctutils.get_head_geo()
                filepath = os.path.join(trait_dir_path, '_texture')

                if not os.path.exists(filepath):
                    filepath = os.path.join(trait_dir_path, '_textures')
                
                if head_geo:
                    # Strip off gender prefix for DNA trait names
                    ctutils.apply_dna_textures_to_object(filepath, trait_display_name[2:], head_geo)

                continue

            if 'suit' in trait_dir_name:
                # This is a texture for the suit
                suit_geo = ctutils.get_suit_geo()
                filepath = os.path.join(trait_dir_path, '_textures', 'suit_' + get_scene().clone_props.gender)

                if not os.path.exists(filepath):
                    filepath = os.path.join(trait_dir_path, '_texture', 'suit_' + get_scene().clone_props.gender)
                
                if suit_geo:
                    print('Applying DNA texture to suit')
                    ctutils.apply_dna_textures_to_object(filepath, trait_display_name, suit_geo)

                continue

            if 'facial' in trait_dir_name:
                # Two of the Facial Features are more than textures so skip them
                # here and treat them like all other mesh traits
                if not 'angry' in trait_dir_name.lower() and not 'band' in trait_dir_name.lower():
                    filepath = os.path.join(trait_dir_path, '_texture')

                    if not os.path.exists(filepath):
                        filepath = os.path.join(trait_dir_path, '_textures')

                    # Strip of gender prefix for facial feature trait names
                    ctutils.apply_facial_feature(filepath, 'ff_' + trait_display_name[2:])

                    continue

            # Verify the extraction was successful and directory structure exists
            full_path = os.path.join(trait_dir_path, '_' + clone_props.gender, '_blender')
            
            try:
                blend_files = ctutils.alistdir(full_path)
                if not blend_files:
                    print(f"CloneX: Warning - No blend files found in {full_path}")
                    print(
                        f"CloneX: Skipping trait '{trait_dir_path.name}' - "
                        f"no selected gender ('{clone_props.gender}') blend payload."
                    )
                    continue
                
                if not blend_files:
                    print(f"CloneX: Skipping {trait_dir_path} - no .blend files found")
                    continue
                
                blend_file = blend_files[0]
                trait_display_name = Path(blend_file).stem.replace('rigged_', '')
                
                item = clone_props.trait_collection.add()
                item.trait_dir = str(trait_dir_path.resolve()) if hasattr(trait_dir_path, 'resolve') else str(trait_dir_path)
                item.name = trait_display_name
                item.trait_selected = True
                
                print(f"CloneX: Successfully added trait: {trait_display_name}")
                
            except Exception as e:
                print(f"CloneX: Error processing {trait_dir_path}: {str(e)}")
                print(f"CloneX: Skipping this asset and continuing...")
                continue   

        print(self.directory)
        # clone_props.home_dir = self.directory
        clone_props.files_loaded = True

        ctutils.load_poses_from_blendfile(context)
        ctutils.load_env_from_blendfile(context)
        ctutils.setup(context)

        # Path to the blendshape_renamer.py script
        script_file = os.path.join(os.path.dirname(__file__), "blendshape_renamer.py")

        with open(script_file, 'r') as file:
            exec(file.read())
        
        # === ENHANCED CLONE TOOLS AUTO-FIXES ===
        clone_props = get_scene().clone_props
        
        # Only apply automatic fixes if at least one is enabled
        if (clone_props.auto_fix_scale or 
            clone_props.auto_position_traits or 
            clone_props.auto_register_traits):
            
            print("CloneX: 🚀 Applying automatic import enhancements...")
            
            # Apply all automatic fixes after import completes
            try:
                validation_results = ctutils.enhanced_clone_import()
                
                if validation_results['all_checks_passed']:
                    print("CloneX: ✅ All automatic fixes applied successfully")
                    self.report({'INFO'}, "Clone import completed with automatic fixes applied")
                elif validation_results.get('character_found') and validation_results.get('traits_found', 0) > 0:
                    # Import is operational; some validation checks are best-effort and
                    # should not alarm users when character assembly succeeded.
                    print("CloneX: ✅ Clone import completed (non-critical auto-fix checks reported issues)")
                    self.report({'INFO'}, "Clone import completed")
                else:
                    print("CloneX: ⚠️  Some automatic fixes had issues, but import completed")
                    self.report({'WARNING'}, "Clone import completed, but some automatic fixes had issues")
                    
            except Exception as e:
                print(f"CloneX: ❌ Error during automatic fixes: {str(e)}")
                self.report({'WARNING'}, f"Clone import completed, but automatic fixes failed: {str(e)}")
        else:
            print("CloneX: All automatic fixes disabled in preferences")
            self.report({'INFO'}, "Clone import completed (automatic fixes disabled)")
        
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

class CT_OT_LoadPosesOperator(Operator):
    """Load the pose library"""

    bl_idname = 'ct.load_poses_operator'
    bl_label = 'Load Poses'

    def execute(self, context):
        ctglobals = context.window_manager.ctglobals

        ctutils.load_poses_from_blendfile(context)
        ctutils.setup(context)

        return {'FINISHED'}

class CT_OT_UnequipWearableOperator(Operator):
    """Unequip the specified wearable or trait"""

    bl_idname = 'ct.unequip_wearable_operator'
    bl_label = 'Unequip Wearable'
    # :TODO: Figure out why UNDO isn't working
    bl_options = {'REGISTER', 'UNDO'}

    wearable_name: StringProperty()

    def execute(self, context):
        clone_props = context.scene.clone_props
        char_collection = get_collection('Character')
        asset_collection = get_collection(self.wearable_name)

        if char_collection and asset_collection:
            char_collection.children.unlink(asset_collection)

            # Remove from the collection of active (equipped) traits
            trait_coll = clone_props.trait_collection
            trait_index = trait_coll.find(asset_collection.name)
            trait_coll.remove(trait_index)
        else:
            asset_mat = get_material(self.wearable_name)

            if asset_mat:
                trait_coll = clone_props.trait_collection
                trait_index = trait_coll.find(asset_mat.name)
                trait_coll.remove(trait_index)
                
                # Remove the material (swap back to base mat)
                if 'dna' in asset_mat.name:
                    geo_obj = ctutils.get_head_geo()
                    ctutils.remove_dna_textures_from_object(geo_obj)
                else:
                    geo_obj = ctutils.get_suit_geo()
                    ctutils.remove_dna_textures_from_object(geo_obj)
        
        return {'FINISHED'}


class CT_OT_EquipWearableOperator(Operator):
    """Equip a wearable from the asset library"""

    bl_idname = 'ct.equip_wearable_operator'
    bl_label = 'Equip Wearable'

    def execute(self, context):
        asset = get_context_asset(context)
        asset_name = get_asset_name(asset)
        if not asset_name:
            self.report({'ERROR'}, 'No active asset selected')
            return {'CANCELLED'}

        asset_collection = get_collection(asset_name)
        char_collection = get_collection('Character')

        if char_collection and asset_collection:
            try:
                char_collection.children.link(asset_collection)
                ctutils.unpack_asset_collection(asset_collection)

                trait = context.scene.clone_props.trait_collection.add()
                trait.name = asset_collection.name
            except:
                char_collection.children.unlink(asset_collection)
        else:
            # The user has clicked on a material
            if 'Head' in asset_name:
                head_mat = get_material_from_object(ctutils.get_head_geo())

                if head_mat.name != 'Dna_Head':
                    ctutils.apply_dna_textures_to_object(None, ctutils.get_head_geo())
                else:
                    ctutils.remove_dna_textures_from_object(ctutils.get_head_geo())
            elif 'Suit' in asset_name:
                suit_mat = get_material_from_object(ctutils.get_suit_geo())

                if suit_mat.name != 'Dna_Suit':
                    ctutils.apply_dna_textures_to_object(None, ctutils.get_suit_geo())
                else:
                    ctutils.remove_dna_textures_from_object(ctutils.get_suit_geo())
            else:
                self.report({'ERROR'}, 'Unable to apply non-DNA materials from this interface')   

        return {'FINISHED'}

class CT_OT_ApplyFacialFeatureOperator(Operator):
    """Applies a facial feature to the active material on the head geo"""

    bl_idname = 'ct.apply_facial_feature_operator'
    bl_label = 'Apply Facial Feature'

    @classmethod
    def poll(self, context):
        asset = get_context_asset(context)
        asset_name = get_asset_name(asset)
        if not asset_name:
            return False

        mat_nodes = get_material_nodes(asset_name)
        image_name = get_node(mat_nodes, 'Image Texture').image.name
        geo_nodes = get_nodes(get_material_from_object(ctutils.get_head_geo()))
        mix_shader_node = get_node(geo_nodes, 'Mix Shader')

        if mix_shader_node:
            geo_image_name = mix_shader_node.inputs[0].links[0].from_node.image.name

            # Deactive option to apply facial feature if it is
            # already applied to the head geo
            if (image_name == geo_image_name 
                    and mix_shader_node.outputs[0].links):
                return False

        return True

    def execute(self, context):
        asset = get_context_asset(context)
        asset_name = get_asset_name(asset)
        if not asset_name:
            self.report({'ERROR'}, 'No active asset selected')
            return {'CANCELLED'}

        mat = get_material(asset_name)

        if mat:
            # Set the image of the current tex node on the material
            geo_obj = ctutils.get_head_geo()
            geo_mat = get_material_from_object(geo_obj)
            geo_mat_nodes = get_nodes(geo_mat)
            mix_shader_node = get_node(geo_mat_nodes, 'Mix Shader')

            if not mix_shader_node:
                # No Mix Shader node means we need to apply the facial feature
                # for the first time
                ctutils.apply_facial_feature(None, asset_name)
            else:
                # Get the image object from the texture node
                mat_nodes = get_nodes(mat)
                tex_node = get_node(mat_nodes, 'Image Texture')
                new_image = tex_node.image

                mat_output_node = get_node(geo_mat_nodes, 'Material Output')
                geo_ff_tex_node = mix_shader_node.inputs[0].links[0].from_node
                geo_ff_tex_node.image = new_image  
                create_node_link(mix_shader_node.outputs[0], mat_output_node.inputs[0])

        return {'FINISHED'}


def _get_collection_bounds(coll_name):
    coll = bpy.data.collections.get(coll_name)
    if not coll:
        return None, None

    min_vec = mathutils.Vector((1e10, 1e10, 1e10))
    max_vec = mathutils.Vector((-1e10, -1e10, -1e10))
    found_any = False

    for obj in coll.all_objects:
        if obj.type != 'MESH':
            continue
        found_any = True
        bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box]
        for corner in bbox:
            min_vec.x = min(min_vec.x, corner.x)
            min_vec.y = min(min_vec.y, corner.y)
            min_vec.z = min(min_vec.z, corner.z)
            max_vec.x = max(max_vec.x, corner.x)
            max_vec.y = max(max_vec.y, corner.y)
            max_vec.z = max(max_vec.z, corner.z)

    if not found_any:
        return None, None
    return min_vec, max_vec


def _get_head_bounds():
    head_obj = ctutils.get_head_geo()
    if head_obj is None:
        return None, None

    min_vec = mathutils.Vector((1e10, 1e10, 1e10))
    max_vec = mathutils.Vector((-1e10, -1e10, -1e10))
    for corner in head_obj.bound_box:
        world_corner = head_obj.matrix_world @ mathutils.Vector(corner)
        min_vec.x = min(min_vec.x, world_corner.x)
        min_vec.y = min(min_vec.y, world_corner.y)
        min_vec.z = min(min_vec.z, world_corner.z)
        max_vec.x = max(max_vec.x, world_corner.x)
        max_vec.y = max(max_vec.y, world_corner.y)
        max_vec.z = max(max_vec.z, world_corner.z)

    return min_vec, max_vec


def _compute_distance_for_fill(bbox_height, fill_percent=0.8, lens_mm=50.0, sensor_height_mm=24.0):
    vertical_fov = 2.0 * math.atan((sensor_height_mm * 0.5) / lens_mm)
    denom = fill_percent * 2.0 * math.tan(vertical_fov * 0.5)
    if abs(denom) < 1e-9:
        return 0.0
    return bbox_height / denom


def _create_character_sheet_cameras(preset_name, body_count=10, include_closeups=True):
    cameras = []
    body_min, body_max = _get_collection_bounds("Character")

    if body_min and body_max:
        center_body = (body_min + body_max) * 0.5
        height_body = max(0.001, body_max.z - body_min.z)
        dist_body = _compute_distance_for_fill(height_body, fill_percent=0.8, lens_mm=50.0)
        step_deg = 360.0 / float(max(1, body_count))

        directional_labels = [
            "Front",
            "Left Front",
            "Left Side",
            "Left Back",
            "Back",
            "Right Back",
            "Right Side",
            "Right Front",
        ]

        for i in range(body_count):
            angle_deg = i * step_deg
            angle_rad = math.radians(angle_deg)
            loc_x = center_body.x + dist_body * math.sin(angle_rad)
            loc_y = center_body.y - dist_body * math.cos(angle_rad)
            loc_z = center_body.z
            direction = (center_body - mathutils.Vector((loc_x, loc_y, loc_z))).normalized()
            rot_eul = direction.to_track_quat('-Z', 'Y').to_euler()

            if body_count == 8:
                shot_label = directional_labels[i]
            else:
                shot_label = f"{i+1:02}"

            cameras.append({
                "name": f"Body_{shot_label}",
                "location": (loc_x, loc_y, loc_z),
                "rotation": (rot_eul.x, rot_eul.y, rot_eul.z),
                "lens": 50.0,
            })

    if include_closeups:
        head_min, head_max = _get_head_bounds()
        if head_min and head_max:
            center_head = (head_min + head_max) * 0.5
            height_head = max(0.001, head_max.z - head_min.z)
            dist_head = _compute_distance_for_fill(height_head, fill_percent=0.6, lens_mm=60.0)

            closeup_angles = [(0, "CloseFront"), (45, "Close3Q"), (90, "CloseSide")]
            for angle_deg, label in closeup_angles:
                angle_rad = math.radians(angle_deg)
                loc_x = center_head.x + dist_head * math.sin(angle_rad)
                loc_y = center_head.y - dist_head * math.cos(angle_rad)
                loc_z = center_head.z
                direction = (center_head - mathutils.Vector((loc_x, loc_y, loc_z))).normalized()
                rot_eul = direction.to_track_quat('-Z', 'Y').to_euler()

                cameras.append({
                    "name": label,
                    "location": (loc_x, loc_y, loc_z),
                    "rotation": (rot_eul.x, rot_eul.y, rot_eul.z),
                    "lens": 60.0,
                })

    return cameras


def _build_contact_sheet(shot_items, output_path, sheet_name, columns, transparent):
    if not shot_items:
        return None

    # Prefer the default A4 landscape composition when the named body shots exist.
    a4_sheet = _build_a4_default_sheet(
        shot_items=shot_items,
        output_path=output_path,
        sheet_name=sheet_name,
        transparent=transparent
    )
    if a4_sheet:
        return a4_sheet

    loaded_images = []
    processed_images = []
    try:
        for item in shot_items:
            path = item.get("path", "")
            if not path or not os.path.exists(path):
                continue
            scale = float(item.get("scale", 1.0))
            if scale <= 0:
                continue

            image = bpy.data.images.load(path, check_existing=False)
            loaded_images.append(image)

            base_w = max(1, int(image.size[0]))
            base_h = max(1, int(image.size[1]))
            scaled_w = max(1, int(base_w * scale))
            scaled_h = max(1, int(base_h * scale))
            if scaled_w != base_w or scaled_h != base_h:
                image.scale(scaled_w, scaled_h)

            processed_images.append({
                "name": item.get("name", os.path.basename(path)),
                "width": int(image.size[0]),
                "height": int(image.size[1]),
                "pixels": list(image.pixels[:]),
            })

        if not processed_images:
            return None

        cell_w = max(img["width"] for img in processed_images)
        cell_h = max(img["height"] for img in processed_images)

        cols = max(1, columns)
        rows = (len(processed_images) + cols - 1) // cols
        sheet_w = cell_w * cols
        sheet_h = cell_h * rows

        bg_alpha = 0.0 if transparent else 1.0
        sheet_pixels = [0.0, 0.0, 0.0, bg_alpha] * (sheet_w * sheet_h)

        for index, image_data in enumerate(processed_images):
            src_w = image_data["width"]
            src_h = image_data["height"]
            src_pixels = image_data["pixels"]
            col = index % cols
            row = index // cols
            cell_x = col * cell_w
            cell_y = (rows - 1 - row) * cell_h
            dest_x = cell_x + max(0, (cell_w - src_w) // 2)
            dest_y = cell_y + max(0, (cell_h - src_h) // 2)

            for y in range(src_h):
                src_row_start = y * src_w * 4
                src_row_end = src_row_start + (src_w * 4)
                dest_row = dest_y + y
                dest_start = (dest_row * sheet_w + dest_x) * 4
                dest_end = dest_start + (src_w * 4)
                sheet_pixels[dest_start:dest_end] = src_pixels[src_row_start:src_row_end]

        sheet_image = bpy.data.images.new(
            name=f"CT_CharacterSheet_{sheet_name}",
            width=sheet_w,
            height=sheet_h,
            alpha=transparent
        )
        sheet_image.pixels = sheet_pixels
        sheet_image.filepath_raw = os.path.join(output_path, f"{sheet_name}_sheet.png")
        sheet_image.file_format = 'PNG'
        sheet_image.save()
        return sheet_image.filepath_raw
    finally:
        for image in loaded_images:
            try:
                image.user_clear()
            except Exception:
                pass
            try:
                bpy.data.images.remove(image)
            except Exception:
                pass


def _selected_sheet_items(ctglobals):
    items = []
    for shot in ctglobals.charsheet_shots:
        if not shot.include_in_sheet:
            continue
        items.append({
            "name": shot.name,
            "path": shot.file_path,
            "scale": shot.scale,
        })
    return items


def _normalize_shot_name(value):
    base = os.path.splitext(os.path.basename(value))[0]
    return ''.join(ch for ch in base.lower() if ch.isalnum())


def _shot_slot_key(value):
    key = _normalize_shot_name(value)
    # closeups
    if 'close3q' in key:
        return 'close_3q'
    if 'closefront' in key:
        return 'close_front'
    if 'closeside' in key:
        return 'close_side'
    # body views
    if 'bodyleftfront' in key:
        return 'left_front'
    if 'bodyleftside' in key:
        return 'left_side'
    if 'bodyleftback' in key:
        return 'left_back'
    if 'bodyrightfront' in key:
        return 'right_front'
    if 'bodyrightside' in key:
        return 'right_side'
    if 'bodyrightback' in key:
        return 'right_back'
    if 'bodyback' in key:
        return 'back'
    if 'bodyfront' in key:
        return 'front'
    return None


def _alpha_crop_bounds(image_pixels, src_w, src_h, alpha_threshold=0.01):
    min_x = src_w
    min_y = src_h
    max_x = -1
    max_y = -1

    for y in range(src_h):
        row = y * src_w * 4
        for x in range(src_w):
            alpha = image_pixels[row + (x * 4) + 3]
            if alpha > alpha_threshold:
                if x < min_x:
                    min_x = x
                if y < min_y:
                    min_y = y
                if x > max_x:
                    max_x = x
                if y > max_y:
                    max_y = y

    if max_x < min_x or max_y < min_y:
        return None
    return (min_x, min_y, (max_x - min_x + 1), (max_y - min_y + 1))


def _copy_image_into_region(sheet_pixels, sheet_w, sheet_h, image_pixels, src_w, src_h, x0, y0, w, h, scale=1.0, crop_alpha=True):
    if src_w <= 0 or src_h <= 0 or w <= 0 or h <= 0:
        return

    crop_x = 0
    crop_y = 0
    crop_w = src_w
    crop_h = src_h
    source_pixels = image_pixels

    if crop_alpha:
        bounds = _alpha_crop_bounds(image_pixels, src_w, src_h)
        if bounds is not None:
            crop_x, crop_y, crop_w, crop_h = bounds
            if crop_w > 0 and crop_h > 0 and (crop_w != src_w or crop_h != src_h):
                cropped = [0.0, 0.0, 0.0, 0.0] * (crop_w * crop_h)
                for y in range(crop_h):
                    src_row_start = ((crop_y + y) * src_w + crop_x) * 4
                    src_row_end = src_row_start + (crop_w * 4)
                    dst_row_start = y * crop_w * 4
                    cropped[dst_row_start:dst_row_start + (crop_w * 4)] = image_pixels[src_row_start:src_row_end]
                source_pixels = cropped

    fit = min(float(w) / float(crop_w), float(h) / float(crop_h))
    fit *= max(0.1, scale)
    dst_w = max(1, int(crop_w * fit))
    dst_h = max(1, int(crop_h * fit))

    # center in region
    dst_x = x0 + max(0, (w - dst_w) // 2)
    dst_y = y0 + max(0, (h - dst_h) // 2)

    # temporary image for scaling
    temp_img = bpy.data.images.new(name="CT_TempSheetScale", width=crop_w, height=crop_h, alpha=True)
    try:
        temp_img.pixels = source_pixels
        temp_img.scale(dst_w, dst_h)
        scaled = list(temp_img.pixels[:])
    finally:
        bpy.data.images.remove(temp_img)

    # write into destination, clipping to canvas bounds
    for y in range(dst_h):
        src_row_start = y * dst_w * 4
        src_row_end = src_row_start + (dst_w * 4)
        dest_row = dst_y + y
        if dest_row < 0 or dest_row >= sheet_h:
            continue
        dest_start = (dest_row * sheet_w + dst_x) * 4
        dest_end = dest_start + (dst_w * 4)
        # clip horizontal bounds
        if dst_x < 0 or dst_x + dst_w > sheet_w:
            for x in range(dst_w):
                target_x = dst_x + x
                if target_x < 0 or target_x >= sheet_w:
                    continue
                s = src_row_start + x * 4
                d = (dest_row * sheet_w + target_x) * 4
                sheet_pixels[d:d+4] = scaled[s:s+4]
        else:
            sheet_pixels[dest_start:dest_end] = scaled[src_row_start:src_row_end]


def _build_a4_default_sheet(shot_items, output_path, sheet_name, transparent):
    # Map selected shots into named slots.
    slot_items = {}
    for item in shot_items:
        slot = _shot_slot_key(item.get("name", ""))
        if slot is None:
            slot = _shot_slot_key(item.get("path", ""))
        if slot is None:
            continue
        if slot not in slot_items:
            slot_items[slot] = item

    # Require the core slots to use the fixed A4 layout.
    required = {
        'front', 'left_front', 'left_side', 'left_back',
        'right_front', 'right_side', 'right_back', 'back',
        'close_front', 'close_side', 'close_3q'
    }
    if not required.issubset(set(slot_items.keys())):
        return None

    # A4 landscape at 300 DPI.
    sheet_w = 3508
    sheet_h = 2480
    margin = 56
    gutter = 24
    content_w = sheet_w - (margin * 2)
    content_h = sheet_h - (margin * 2)

    # Revised preset:
    # Top row: Front, Left Front, Left Side, Left Back, Close 3Q, Close Side
    # Bottom row: Back, Right Front, Right Side, Right Back, (Close Front spans last 2 columns)
    col_w = (content_w - (gutter * 5)) // 6
    row_h = (content_h - gutter) // 2

    x_left = margin
    y_bottom = margin
    y_top = margin + row_h + gutter

    regions = {
        'front': (x_left + (col_w + gutter) * 0, y_top, col_w, row_h),
        'left_front': (x_left + (col_w + gutter) * 1, y_top, col_w, row_h),
        'left_side': (x_left + (col_w + gutter) * 2, y_top, col_w, row_h),
        'left_back': (x_left + (col_w + gutter) * 3, y_top, col_w, row_h),
        'close_3q': (x_left + (col_w + gutter) * 4, y_top, col_w, row_h),
        'close_side': (x_left + (col_w + gutter) * 5, y_top, col_w, row_h),
        'back': (x_left + (col_w + gutter) * 0, y_bottom, col_w, row_h),
        'right_front': (x_left + (col_w + gutter) * 1, y_bottom, col_w, row_h),
        'right_side': (x_left + (col_w + gutter) * 2, y_bottom, col_w, row_h),
        'right_back': (x_left + (col_w + gutter) * 3, y_bottom, col_w, row_h),
        'close_front': (
            x_left + (col_w + gutter) * 4,
            y_bottom,
            (col_w * 2) + gutter,
            row_h
        ),
    }

    bg_alpha = 0.0 if transparent else 1.0
    sheet_pixels = [0.0, 0.0, 0.0, bg_alpha] * (sheet_w * sheet_h)
    loaded = []
    try:
        for slot, region in regions.items():
            shot = slot_items.get(slot)
            if not shot:
                continue
            shot_path = shot.get("path", "")
            if not shot_path or not os.path.exists(shot_path):
                continue

            image = bpy.data.images.load(shot_path, check_existing=False)
            loaded.append(image)
            src_w = int(image.size[0])
            src_h = int(image.size[1])
            pixels = list(image.pixels[:])
            x0, y0, w, h = region
            _copy_image_into_region(
                sheet_pixels=sheet_pixels,
                sheet_w=sheet_w,
                sheet_h=sheet_h,
                image_pixels=pixels,
                src_w=src_w,
                src_h=src_h,
                x0=x0,
                y0=y0,
                w=w,
                h=h,
                scale=float(shot.get("scale", 1.0)),
            )

        sheet_image = bpy.data.images.new(
            name=f"CT_CharacterSheetA4_{sheet_name}",
            width=sheet_w,
            height=sheet_h,
            alpha=transparent
        )
        sheet_image.pixels = sheet_pixels
        sheet_path = os.path.join(output_path, f"{sheet_name}_sheet_a4.png")
        sheet_image.filepath_raw = sheet_path
        sheet_image.file_format = 'PNG'
        sheet_image.save()
        return sheet_path
    finally:
        for image in loaded:
            try:
                bpy.data.images.remove(image)
            except Exception:
                pass

class CT_OT_RemoveFacialFeatureOperator(Operator):
    """Removes a facial feature from the active material on the head geo"""

    bl_idname = 'ct.remove_facial_feature_operator'
    bl_label = 'Apply Facial Feature'

    @classmethod
    def poll(self, context):
        asset = get_context_asset(context)
        asset_name = get_asset_name(asset)
        if not asset_name:
            return False

        mat_nodes = get_material_nodes(asset_name)
        image_name = get_node(mat_nodes, 'Image Texture').image.name
        geo_nodes = get_nodes(get_material_from_object(ctutils.get_head_geo()))
        mix_shader_node = get_node(geo_nodes, 'Mix Shader')

        if mix_shader_node:
            geo_image_name = mix_shader_node.inputs[0].links[0].from_node.image.name    

            if (image_name != geo_image_name
                    or not mix_shader_node.outputs[0].links):
                return False

            return True

    def execute(self, context):
        ctutils.remove_facial_feature()

        return {'FINISHED'}

class CT_OT_LoadEnvOperator(Operator):
    """Load the lighting and staging presets"""

    bl_idname = 'ct.load_env_operator'
    bl_label = 'Load Lights and Staging'

    def execute(self, context):
        ctutils.load_env_from_blendfile(context)
        ctutils.setup(context)

        return {'FINISHED'} 

class CT_OT_ExportOperator(Operator):
    """Export file in the format specified"""
    
    bl_idname = 'ct.export_operator'
    bl_label = 'Export File'

    export_type: StringProperty()

    filepath: StringProperty(
        name="File Path",
        description="Filepath used for exporting the file",
        maxlen=1024,
        subtype='FILE_PATH'
    )

    check_existing: BoolProperty(
        name="Check Existing",
        description="Check and warn on overwriting existing files",
        default=True,
        options={'HIDDEN'},
    )

    def execute(self, context):
        ctglobals = context.window_manager.ctglobals

        # Remove the Skybox and LightCatcher objects before export as it's only meant
        # to be used for renders
        skybox = get_object('Skybox')
        lc = get_object('LightCatcher')

        if skybox:
            hide(skybox)

        if lc:
            hide(lc)

        original_mode = get_mode()

        # Can't switch directly to a mode like EDIT_MESH from OBJECT mode
        if original_mode.startswith('EDIT'):
            original_mode = 'EDIT'

        # Export only meshes or both meshes and armatures. If
        # user wants to export other types of objects they should
        # do so manually.
        if ctglobals.export_mesh_only is True:
            if original_mode != 'OBJECT':
                set_object_mode()
            
            select_all_meshes()
        else:
            ctutils.select_all_mesh_and_armature(context)

        if self.export_type == 'fbx':
            bpy.ops.export_scene.fbx(
                filepath=self.filepath, 
                axis_forward='-Z', 
                axis_up='Y', 
                path_mode='COPY', 
                embed_textures=True,
                use_selection=True
            )
        elif self.export_type == 'obj':
            bpy.ops.export_scene.obj(
                filepath=self.filepath, 
                axis_forward='-Z', 
                axis_up='Y',
                use_selection=True
            )
        elif self.export_type == 'glb':
            bpy.ops.export_scene.gltf(
                filepath=self.filepath,
                use_selection=True,
                export_animations=False
            )
        else:
            print('Unsupported export type!')

        if get_mode() != original_mode:
            set_mode(ao(), original_mode)

        deselect_all_objects()
        
        if skybox:
            unhide(skybox) 

        return {'FINISHED'}

    def invoke(self, context, event):
        self.filename_ext = '.' + self.export_type
        blend_filepath = context.blend_data.filepath
        
        if not blend_filepath:
            blend_filepath = "clone_export"
        else:
            blend_filepath = os.path.splitext(blend_filepath)[0]

        self.filepath = blend_filepath + self.filename_ext

        context.window_manager.fileselect_add(self)
        
        return {'RUNNING_MODAL'}


class CT_OT_RenderCharacterSheet(Operator):
    """Render a multi-view character sheet from generated body and closeup cameras."""

    bl_idname = 'ct.render_character_sheet'
    bl_label = 'Render Character Sheet'
    bl_options = {'REGISTER'}

    def execute(self, context):
        ctglobals = context.window_manager.ctglobals
        preset_name = ctglobals.charsheet_preset
        cameras = _create_character_sheet_cameras(
            preset_name=preset_name,
            body_count=ctglobals.charsheet_body_views,
            include_closeups=ctglobals.charsheet_include_closeups
        )

        if not cameras:
            self.report({'ERROR'}, "No valid character bounds found for Character Sheet render")
            return {'CANCELLED'}

        output_path = bpy.path.abspath(ctglobals.charsheet_output_path)
        os.makedirs(output_path, exist_ok=True)

        scene = context.scene
        original_camera = scene.camera
        original_filepath = scene.render.filepath
        original_transparent = scene.render.film_transparent
        original_format = scene.render.image_settings.file_format
        original_color_mode = scene.render.image_settings.color_mode

        scene.render.image_settings.file_format = 'PNG'
        scene.render.film_transparent = ctglobals.charsheet_transparent_bg
        scene.render.image_settings.color_mode = 'RGBA' if ctglobals.charsheet_transparent_bg else 'RGB'
        ctglobals.charsheet_shots.clear()

        rendered_count = 0
        rendered_paths = []
        try:
            for index, cam in enumerate(cameras):
                cam_data = bpy.data.cameras.new(name=f"CT_CharSheetCamData_{index:02}")
                cam_obj = bpy.data.objects.new(name=f"CT_CharSheetCam_{index:02}", object_data=cam_data)
                scene.collection.objects.link(cam_obj)

                cam_obj.location = cam["location"]
                cam_obj.rotation_euler = cam["rotation"]
                cam_obj.data.lens = cam["lens"]
                cam_obj.data.dof.use_dof = False

                scene.camera = cam_obj
                filename = f"{preset_name}_{cam['name']}.png"
                render_filepath = os.path.join(output_path, filename)
                scene.render.filepath = render_filepath
                bpy.ops.render.render(write_still=True)
                rendered_count += 1
                rendered_paths.append(render_filepath)

                shot = ctglobals.charsheet_shots.add()
                shot.name = filename
                shot.file_path = render_filepath
                shot.include_in_sheet = True
                shot.scale = 1.0

                bpy.data.objects.remove(cam_obj, do_unlink=True)
                bpy.data.cameras.remove(cam_data, do_unlink=True)
        finally:
            scene.camera = original_camera
            scene.render.filepath = original_filepath
            scene.render.film_transparent = original_transparent
            scene.render.image_settings.file_format = original_format
            scene.render.image_settings.color_mode = original_color_mode

        sheet_path = None
        if ctglobals.charsheet_build_page and rendered_paths:
            try:
                sheet_path = _build_contact_sheet(
                    shot_items=_selected_sheet_items(ctglobals),
                    output_path=output_path,
                    sheet_name=preset_name,
                    columns=ctglobals.charsheet_page_columns,
                    transparent=ctglobals.charsheet_transparent_bg
                )
            except Exception as ex:
                self.report({'WARNING'}, f"Rendered views, but failed to assemble one-page sheet: {ex}")

        if sheet_path:
            self.report({'INFO'}, f"Rendered {rendered_count} views + sheet: {sheet_path}")
        else:
            self.report({'INFO'}, f"Rendered {rendered_count} character-sheet images to {output_path}")
        return {'FINISHED'}


class CT_OT_RebuildCharacterSheet(Operator):
    """Rebuild stitched character sheet from selected shots and per-shot scales."""

    bl_idname = 'ct.rebuild_character_sheet'
    bl_label = 'Rebuild Stitched Sheet'
    bl_options = {'REGISTER'}

    def execute(self, context):
        ctglobals = context.window_manager.ctglobals
        selected_items = _selected_sheet_items(ctglobals)
        if not selected_items:
            self.report({'ERROR'}, "No selected shots to stitch")
            return {'CANCELLED'}

        output_path = bpy.path.abspath(ctglobals.charsheet_output_path)
        os.makedirs(output_path, exist_ok=True)
        preset_name = ctglobals.charsheet_preset

        try:
            sheet_path = _build_contact_sheet(
                shot_items=selected_items,
                output_path=output_path,
                sheet_name=preset_name,
                columns=ctglobals.charsheet_page_columns,
                transparent=ctglobals.charsheet_transparent_bg
            )
        except Exception as ex:
            self.report({'ERROR'}, f"Failed to stitch sheet: {ex}")
            return {'CANCELLED'}

        if not sheet_path:
            self.report({'ERROR'}, "No valid rendered shots found on disk")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Rebuilt stitched sheet: {sheet_path}")
        return {'FINISHED'}

class CT_OT_MixamoButton(Operator):
    """Launch Mixamo.com in your web browser"""

    bl_idname = 'ct.mixamo_button'
    bl_label = 'Launch Mixamo'

    def execute(self, context):
        webbrowser.open('https://www.mixamo.com')

        return {'FINISHED'}

class CT_OT_PoseModeButton(Operator):
    """Easily switch back to Pose mode"""

    bl_idname = 'ct.pose_mode_button'
    bl_label = 'Switch to Pose Mode'

    def execute(self, context):
        ctutils.easy_pose_mode_switch()

        return {'FINISHED'}

class CT_OT_InitStyleLibraryButton(Operator):
    """Creates a new Asset Library for CloneX styles"""

    bl_idname = 'ct.init_style_library_button'
    bl_label = 'Create Style Library'        

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        style_lib_init = context.window_manager.ctglobals.style_lib_initialized

        if prefs:
            path = prefs.style_library_path
            
            if path != '' and not style_lib_init:
                ctutils.initialize_clonex_asset_library(
                    'CloneX Style Library', 
                    os.path.join(path, 'clonex_style_library')
                )

                context.window_manager.ctglobals.style_lib_initialized = True

        return {'FINISHED'}

class CT_OT_SyncStyleLibraryButton(Operator):
    """Persists all assets and asset catalog entries back to the CloneX Style Library"""

    bl_idname = 'ct.sync_style_library_button'
    bl_label = 'Sync Style Library'        

    def execute(self, context):
        path = ''

        for al in bpy.context.preferences.filepaths.asset_libraries:
            if al.name == 'CloneX Style Library':
                path = al.path

        ctutils.sync_assets_to_style_library(path)

        return {'FINISHED'}

class StyleLibraryDrawingHandler:
    def __init__(self, context):
        self.handle = bpy.types.SpaceFileBrowser.draw_handler_add(
            self.style_library_open_handler, 
            (context,), 'WINDOW', 'POST_PIXEL')

    def style_library_open_handler(self, context):
        filter_asset_id = context.area.spaces.active.params.filter_asset_id
        filter_asset_id.filter_action = False
        filter_asset_id.filter_node_tree = False
        filter_asset_id.filter_object = False
        filter_asset_id.filter_world = False

        self.remove_handle()

    def remove_handle(self):
        bpy.types.SpaceFileBrowser.draw_handler_remove(self.handle, 'WINDOW')

class CT_OT_BlenderStyleSelectOperator(Operator, ImportHelper):
    """
    Use the file browser to select the .blend file
    for the style you wish to import
    """
    
    bl_idname = "ct.blender_style_select_operator"
    bl_label = "Select Blender File"

    filename_ext = '.blend'
    asset_catalog_id: StringProperty()

    filter_glob: StringProperty(
        default="*.blend",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    filter_folder: BoolProperty(default=False, options={'HIDDEN'})
    
    def execute(self, context):
        formatted_filename = \
            ctutils.format_imported_style_name(Path(self.filepath).stem, 
                context.scene.clone_props.gender)

        ctutils.load_clone_trait_assets(formatted_filename, None, self.filepath, False, False)
        
        bpy.ops.ct.finalize_import_operator(
            'INVOKE_DEFAULT', 
            asset_name=formatted_filename,
            asset_gender=context.scene.clone_props.gender)

        return {'RUNNING_MODAL'}

class CT_OT_GlbStyleSelectOperator(Operator, ImportHelper):
    """
    Use the file browser to select the GLB file
    for the style you wish to import
    """
    
    bl_idname = "ct.glb_style_select_operator"
    bl_label = "Select GLB File"

    filename_ext = '.glb'
    asset_catalog_id: StringProperty()

    filter_glob: StringProperty(
        default="*.glb",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    filter_folder: BoolProperty(default=False, options={'HIDDEN'})
    
    def execute(self, context):
        formatted_filename = \
            ctutils.format_imported_style_name(Path(self.filepath).stem, 
                context.scene.clone_props.gender)

        ctutils.load_glb_trait_asset(formatted_filename, self.filepath, False)
        
        bpy.ops.ct.finalize_import_operator(
            'INVOKE_DEFAULT', 
            asset_name=formatted_filename,
            asset_gender=context.scene.clone_props.gender)

        return {'RUNNING_MODAL'}

class CT_OT_OpenStyleLibraryButton(Operator):
    """Opens the Asset Browser with some default settings"""

    bl_idname = 'ct.open_style_library_button'
    bl_label = 'Open Style Library'

    def execute(self, context):
        already_open = False

        # Create a handler that sets the initial filter state of the
        # AssetBrowser when opened as the Style Library
        StyleLibraryDrawingHandler(context)

        # Check to see if an asset browser is already open
        for window in bpy.context.window_manager.windows:
            screen = window.screen
            
            for area in screen.areas:
                if area.ui_type == "ASSETS":
                    already_open = True

        if not already_open:
            areas = []

            for window in bpy.context.window_manager.windows:
                screen = window.screen
                
                for area in screen.areas:
                    areas.append(area)

            bpy.ops.screen.area_split(direction='VERTICAL', factor=0.25)
            
            for window in bpy.context.window_manager.windows:
                screen = window.screen
                
                for area in screen.areas:
                    if area not in areas:
                        area.ui_type = 'ASSETS'
                        
                        # Don't show poses when opening style library
                        #area.spaces[0].params.filter_asset_id.filter_action = False 

        return {'FINISHED'}

class CT_OT_FinalizeImportOperator(Operator):
    """
    Opens a props dialog showing a preview of the imported style
    and providing options for cataloging and tagging the asset
    """

    bl_idname = 'ct.finalize_import_operator'
    bl_label = 'Categorize & Tag Your Style'

    asset_name: StringProperty()
    asset_gender: StringProperty()
    asset_tags: StringProperty()
    asset_equip: BoolProperty(default=True)

    def invoke(self, context, event):
        # Shift cursor to a better location before opening the follow-up dialog
        context.window.cursor_warp(int(context.window.width/2), int(context.window.height/1.3))
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        trait_coll = get_collection(self.asset_name)

        if trait_coll and trait_coll.asset_data:
            # Assign the asset to the selected asset category
            trait_coll.asset_data.catalog_id = \
                context.scene.clone_props.asset_catalog_names
            
            # Assign the specified gender as a tag and then loop
            # through any additional tags specified by the user and 
            # assign them to the asset as well
            trait_coll.asset_data.tags.new(self.asset_gender, skip_if_exists=True)

            if self.asset_tags != '':
                for tag in [t.strip() for t in self.asset_tags.split(',')]:
                    trait_coll.asset_data.tags.new(tag, skip_if_exists=True)

            if self.asset_equip:
                char_collection = get_collection('Character')

                if char_collection:
                    char_collection.children.link(trait_coll)

                    ctutils.unpack_asset_collection(trait_coll)

                    trait = get_scene().clone_props.trait_collection.add()
                    trait.name = self.asset_name

        # Sync the asset to the style library after loading
        style_lib_path = ''

        for al in bpy.context.preferences.filepaths.asset_libraries:         
            if al.name == 'CloneX Style Library':
                style_lib_path = al.path

        if style_lib_path != '':
            ctutils.sync_assets_to_style_library(style_lib_path)

        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout

        col = layout.column().box()
        col.template_icon(get_collection(self.asset_name).preview.icon_id, scale=10)
        row = col.row()
        row.alignment = 'CENTER'
        row.label(text=self.asset_name)

        col = layout.column()
        col.label(text='Select Asset Category:')
        col.prop(context.scene.clone_props, 'asset_catalog_names', text='')
        col.label(text='Add tags (separate with commas):')
        col.prop(self, 'asset_tags', text='')
        col.prop(self, 'asset_equip', text='Equip Immediately?')

class CT_OT_ImportStyleButton(Operator):
    """Button to open dialog for importing styles"""

    bl_idname = 'ct.import_style_button'
    bl_label = 'Custom Style Importer'

    filepath: StringProperty(subtype='FILE_PATH')

    def invoke(self, context, event):
        context.window_manager.invoke_props_dialog(self)

        return {'RUNNING_MODAL'}

    def execute(self, context):
        if context.scene.clone_props.import_type == 'blend':
            bpy.ops.ct.blender_style_select_operator(
                'INVOKE_DEFAULT',
                asset_catalog_id=context.scene.clone_props.asset_catalog_names)
        else:
            bpy.ops.ct.glb_style_select_operator(
                'INVOKE_DEFAULT',
                asset_catalog_id=context.scene.clone_props.asset_catalog_names)

        return {'FINISHED'}

    def draw(self, context):
        scn = context.scene

        layout = self.layout

        row = layout.row()
        row.label(text='Gender of imported style:')
        row = layout.row()
        row.prop(scn.clone_props, 'gender', expand=True)
        
        row = layout.row()
        row.label(text='Import filetype:')
        row = layout.row()
        row.prop(scn.clone_props, 'import_type', expand=True)

        row = layout.row()
        row.label(text='Click OK to select the file')

class CT_OT_ObjectZoomOperator(Operator):
    """Frames the selected object in the viewport"""

    bl_idname = 'ct.object_zoom_operator'
    bl_label = 'Zoom In'

    wearable_name: StringProperty()

    def execute(self, context):
        trait_coll = get_collection(self.wearable_name)

        if trait_coll:
            trait_obj = get_objects_from_collection(trait_coll)[0]

            if trait_obj:
                select_only(trait_obj)
                bpy.ops.view3d.view_selected(use_all_regions=False)

        return {'FINISHED'}

class CT_OT_FilterStylesByGender(Operator):
    """Shortcut buttons for filtering style library by gender"""

    bl_idname = 'ct.filter_styles_by_gender'
    bl_label = 'Filter Styles By Gender'

    filter_gender: StringProperty(default='both')

    def execute(self, context):
        for farea in context.screen.areas:
            if farea.ui_type == 'ASSETS':
                farea.spaces.active.params.filter_search = self.filter_gender

        return {'FINISHED'}

class CT_OT_ApplyDnaHeadOperator(Operator):
    """Applies DNA material to head"""

    bl_idname = 'ct.apply_dna_head_operator'
    bl_label = 'Apply Head DNA'

    @classmethod
    def poll(self, context):
        geo_obj = ctutils.get_head_geo()
        asset_name = get_asset_name(get_context_asset(context))
        if not asset_name:
            return False

        # Make sure this DNA isn't already applied 
        if geo_obj.material_slots[0].material.name == asset_name:
            return False

        return True

    def execute(self, context):
        geo_obj = ctutils.get_head_geo()
        base_mat = get_material_from_object(geo_obj)
        mat_name = get_asset_name(get_context_asset(context))
        if not mat_name:
            self.report({'ERROR'}, 'No active asset selected')
            return {'CANCELLED'}

        dna_mat = get_material(mat_name)

        if len(geo_obj.material_slots) < 2:
            add_material_to_object(geo_obj, dna_mat)
        
        if dna_mat:
            geo_obj.material_slots[0].material = dna_mat
            geo_obj.material_slots[len(geo_obj.material_slots)-1].material = base_mat

        return {'FINISHED'}

class CT_OT_ApplyDnaSuitOperator(Operator):
    """Applies DNA material to body"""

    bl_idname = 'ct.apply_dna_suit_operator'
    bl_label = 'Apply Suit DNA'

    @classmethod
    def poll(self, context):
        geo_obj = ctutils.get_suit_geo()
        asset_name = get_asset_name(get_context_asset(context))
        if not asset_name:
            return False

        # Make sure this DNA isn't already applied 
        if geo_obj.material_slots[0].material.name == asset_name:
            return False

        return True

    def execute(self, context):
        geo_obj = ctutils.get_suit_geo()
        base_mat = get_material_from_object(geo_obj)
        mat_name = get_asset_name(get_context_asset(context))
        if not mat_name:
            self.report({'ERROR'}, 'No active asset selected')
            return {'CANCELLED'}

        dna_mat = get_material(mat_name)

        if len(geo_obj.material_slots) < 2:
            add_material_to_object(geo_obj, dna_mat)
        
        if dna_mat:
            geo_obj.material_slots[0].material = dna_mat
            geo_obj.material_slots[len(geo_obj.material_slots)-1].material = base_mat

        return {'FINISHED'}

class CT_OT_InstallContentPackOperator(Operator, ImportHelper):
    """Installs a CloneTools Content Pack"""

    bl_idname = 'ct.install_content_pack_operator'
    bl_label = 'Install Content Pack'

    filename_ext = '.zip'
    formatted_filename: StringProperty()

    filter_glob: StringProperty(
        default="*.zip",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    filter_folder: BoolProperty(default=False, options={'HIDDEN'})

    def execute(self, context):
        cpdir = ctutils.get_content_packs_dir(context)

        library_exists = False

        # Unzip selected file and look for packinfo.json
        with zipfile.ZipFile(self.filepath) as zip_ref:
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
                try:
                    print(f"CloneX: Extracting content pack to {extract_dir}...")  
                    safe_extractall(zip_ref, extract_dir)
                    print(f"CloneX: Content pack extracted successfully")
                except Exception as e:
                    print(f"CloneX: Error extracting content pack: {str(e)}")
                    # Try with shorter path name
                    hash_obj = hashlib.md5(extract_dir.encode())  
                    short_name = f"cp_{hash_obj.hexdigest()[:8]}"
                    fallback_dir = os.path.join(os.path.dirname(extract_dir), short_name)
                    try:
                        safe_extractall(zip_ref, fallback_dir)
                        extract_dir = fallback_dir  # Update extract_dir for later use
                        print(f"CloneX: Extracted to fallback location: {short_name}")
                    except Exception as e2:
                        print(f"CloneX: Fallback extraction failed: {str(e2)}")
                        raise       

        if not library_exists:
            # Create a new Asset Library for the pack
            bpy.ops.preferences.asset_library_add(directory=extract_dir)

            for al in bpy.context.preferences.filepaths.asset_libraries:
                if al.path == extract_dir:
                    al.name = '['+ pack_creator + '] ' + pack_name

        # Refresh the content pack lists
        bpy.ops.animation.refresh_content_packs(sync_type=pack_type)
        bpy.ops.wm.save_mainfile(filepath=os.path.join(context.scene.clone_props.home_dir, 'clonetools.blend'))

        return context.window_manager.invoke_popup(self)

    def draw(self, context):
        layout = self.layout
        layout.label(text='Content Pack Loaded!')

class CT_OT_ApplyAnimationAsset(Operator):
    bl_idname = "animation.apply_animation_asset"
    bl_label = "Apply Animation"
    bl_description = ("Applies the animation to the clone armature")
    bl_options = {"REGISTER", "UNDO"}

    operation: StringProperty()

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.active_object is not None

    def execute(self, context):
        props = context.scene.clone_props

        asset_file = get_context_asset(context)
        if asset_file is None:
            self.report({'ERROR'}, 'No active asset selected')
            return {'CANCELLED'}

        selected_pack = bpy.context.window_manager.content_pack_anims
        source_armature = selected_pack + '_armature'

        # Only support applying animations from external asset libraries for now
        if not is_local_asset(asset_file):
            if get_object(source_armature) is None:
                asset_fullpath = get_asset_full_library_path(context, asset_file)
                if asset_fullpath is None:
                    self.report({'ERROR'}, 'Could not resolve external asset path')
                    return {'CANCELLED'}

                # Load the armature holding the NLA tracks for this content pack
                with bpy.data.libraries.load(str(asset_fullpath)) as (data_from, data_to):
                    data_to.objects = ['Animation Armature']

                # Rename the armature to keep separate references for each animation pack
                get_object('Animation Armature').name = source_armature

            source_arm = get_object(source_armature)
            target_arm = get_object('Genesis8_1' + props.gender.capitalize())

            if target_arm.animation_data is None:
                target_arm.animation_data_create()

            source_anim_data = source_arm.animation_data
            target_anim_data = target_arm.animation_data

            # Iterate over NLA tracks and strips from the source armature
            # to find the strip that matches the selected animation asset
            if source_anim_data:
                for source_nla_track in source_anim_data.nla_tracks:
                    for source_action_strip in source_nla_track.strips:
                        if source_action_strip.name == get_asset_name(asset_file):
                            frame_start = 1
                            
                            if self.operation == 'apply':
                                # If this is the first animation being applied assume a new
                                # track needs to be created. Otherwise target the first track.
                                if len(target_anim_data.nla_tracks) == 0:
                                    target_nla_track = target_anim_data.nla_tracks.new()
                                    target_nla_track.name = 'Main NLA Track'
                                else:
                                    target_nla_track = target_anim_data.nla_tracks[0]

                                    # Clear any existing action strips when applying an animation
                                    for strip in target_nla_track.strips:
                                        target_nla_track.strips.remove(strip)
                            elif self.operation == 'append':
                                target_nla_track = target_anim_data.nla_tracks[0]

                                # If the NLA track already has action strips, set frame_start
                                # to 1 frame beyond the last frame of the last strip
                                if len(target_nla_track.strips) > 0:
                                    frame_start = int(target_nla_track.strips[-1].frame_end + 1)
                                
                            # Create a new strip on the NLA track at the appropriate 
                            # frame_start value
                            target_nla_track.strips.new(
                                source_action_strip.action.name,
                                frame_start,
                                source_action_strip.action
                            )

                            break

            if hasattr(target_anim_data, 'action_suitable_slots') and len(target_anim_data.action_suitable_slots) > 0:
                try:
                    target_anim_data.action_slot = target_anim_data.action_suitable_slots[0]
                except Exception as ex:
                    print(f"CloneX: Warning - Could not set animation action slot: {ex}")

            context.scene.frame_set(1)  

        return {'FINISHED'}

class CT_OT_ApplyPoseFromDropdown(Operator):
    bl_idname = "animation.apply_pose_from_dropdown"
    bl_label = "Apply Pose"
    bl_description = "Applies the selected pose action to the active Clone character"
    bl_options = {"REGISTER", "UNDO"}

    @staticmethod
    def _get_target_armature(props):
        primary_name = 'Genesis8_1' + props.gender.capitalize()
        arm = get_object(primary_name)
        if arm and arm.type == 'ARMATURE':
            return arm

        # Fallback for suffixed duplicate names or renamed rigs.
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE' and primary_name in obj.name:
                return obj

        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                return obj

        return None

    @staticmethod
    def _assign_action_slot(target_arm):
        anim_data = target_arm.animation_data
        if anim_data is None or anim_data.action is None:
            return

        # Blender 5 action layers require assigning a suitable slot.
        if hasattr(anim_data, 'action_suitable_slots') and len(anim_data.action_suitable_slots) > 0:
            try:
                anim_data.action_slot = anim_data.action_suitable_slots[0]
            except Exception as ex:
                print(f"CloneX: Warning - Could not set action slot: {ex}")

    def execute(self, context):
        props = context.scene.clone_props
        wm = context.window_manager

        selected_pose = getattr(wm, 'selected_pose_action', '')
        if not selected_pose or selected_pose == 'NONE':
            self.report({'ERROR'}, 'No pose selected')
            return {'CANCELLED'}

        target_arm = self._get_target_armature(props)
        if target_arm is None:
            self.report({'ERROR'}, 'Could not find target Clone armature')
            return {'CANCELLED'}

        action = bpy.data.actions.get(selected_pose)
        selected_pack = getattr(wm, 'content_pack_poses', 'Current File')

        if action is None and selected_pack != 'Current File':
            blend_path = ctutils.get_pose_pack_blend_path(context, selected_pack)
            if not blend_path:
                self.report({'ERROR'}, 'Could not resolve selected pose content pack')
                return {'CANCELLED'}

            try:
                with bpy.data.libraries.load(blend_path, link=False) as (data_from, data_to):
                    if selected_pose not in data_from.actions:
                        self.report({'ERROR'}, f"Pose '{selected_pose}' not found in pack")
                        return {'CANCELLED'}
                    data_to.actions = [selected_pose]
                action = bpy.data.actions.get(selected_pose)
            except Exception as ex:
                self.report({'ERROR'}, f'Could not load pose action: {ex}')
                return {'CANCELLED'}

        if action is None:
            self.report({'ERROR'}, 'Selected pose action is unavailable')
            return {'CANCELLED'}

        if target_arm.animation_data is None:
            target_arm.animation_data_create()

        target_arm.animation_data.action = action
        self._assign_action_slot(target_arm)
        context.scene.frame_set(1)
        self.report({'INFO'}, f"Applied pose: {selected_pose}")
        return {'FINISHED'}

class CT_OT_RefreshContentPacks(Operator):
    bl_idname = "animation.refresh_content_packs"
    bl_label = "Refresh Content Packs"
    bl_description = ("Refreshes list of available content packs and syncs pose assets to selection")
    bl_options = {"REGISTER", "UNDO"}

    sync_type: StringProperty()

    def execute(self, context):
        wm = context.window_manager
        ctutils.ensure_content_pack_asset_libraries()

        if self.sync_type == 'pose':
            ctutils.update_pose_content_pack(wm, context)
        else:
            ctutils.update_anim_content_pack(wm, context)

        return {'FINISHED'} 

# class CT_OT_ApplyKeyframesToBones(Operator):
#     bl_idname = "animation.apply_keyframes_to_bones"
#     bl_label = "Apply Keyframes to Bones"
#     bl_description = ("Applies keyframes from an animation asset to selected bones")
#     bl_options = {"REGISTER", "UNDO"}

#     def insert_keyframes(from_fcurve: FCurve, to_fcurve: FCurve, frame_current: float, smallest_x: float, apply: bool):
#         # now = time.time()

#         for keyframe in from_fcurve.keyframe_points:
            
#             if not apply:
#                 if keyframe.select_control_point:
#                     to_fcurve.keyframe_points.insert(frame=keyframe.co.x, value=keyframe.co.y, keyframe_type='JITTER')
#                     to_fcurve.keyframe_points.update()
#             else:
#                 to_fcurve.keyframe_points.insert(frame=(keyframe.co.x + frame_current) - smallest_x, value=keyframe.co.y, keyframe_type='JITTER')
#                 to_fcurve.keyframe_points.update()

#         # time_taken = time.time() - now
#         # print('insert_keyframes time: ' + str(time_taken))
                
#     def copy_location_to_action(from_action: Action, to_action: Action, frame_current: float, smallest_x: float, bone_names, apply: bool):
#         now = time.time()

#         # bone_names = {bone.name for bone in bpy.context.selected_pose_bones_from_active_object}
#         for bone_name in bone_names:
#             for location_index in range(3):
#                 bone = bpy.context.object.pose.bones[bone_name]
#                 print(bone)
#                 rna_path = bone.path_from_id("location")
#                 from_fcurve = from_action.fcurves.find(rna_path, index=location_index)
#                 if from_fcurve is None:
#                     break

#                 to_fcurve = to_action.fcurves.find(rna_path, index=location_index)
#                 if to_fcurve is None:
#                     to_fcurve = to_action.fcurves.new(rna_path, index=location_index, action_group=bone_name)
                
#                 self.insert_keyframes(from_fcurve, to_fcurve, frame_current, smallest_x, apply)

#         time_taken = time.time() - now
#         print('copy_location_to_action time: ' + str(time_taken))
                    
#     def copy_rotation_to_action(from_action: Action, to_action: Action, frame_current: float, smallest_x: float, bone_names, apply: bool):
#         now = time.time()

#         # bone_names = {bone.name for bone in bpy.context.selected_pose_bones_from_active_object}
#         for bone_name in bone_names:
#             bone = bpy.context.object.pose.bones[bone_name]
#             if bone.rotation_mode == "QUATERNION":
#                 for rotation_index in range(4):
#                     rna_path = bone.path_from_id("rotation_quaternion")
#                     from_fcurve = from_action.fcurves.find(rna_path, index=rotation_index)
#                     if from_fcurve is None:
#                         break

#                     to_fcurve = to_action.fcurves.find(rna_path, index=rotation_index)
#                     if to_fcurve is None:
#                         to_fcurve = to_action.fcurves.new(rna_path, index=rotation_index, action_group=bone_name)

#                     insert_keyframes(from_fcurve, to_fcurve, frame_current, smallest_x, apply)

#             elif bone.rotation_mode == "AXIS_ANGLE":
#                 for rotation_index in range(4):
#                     rna_path = bone.path_from_id("rotation_axis_angle")
#                     from_fcurve = from_action.fcurves.find(rna_path, index=rotation_index)
#                     if from_fcurve is None:
#                         break

#                     to_fcurve = to_action.fcurves.find(rna_path, index=rotation_index)
#                     if to_fcurve is None:
#                         to_fcurve = to_action.fcurves.new(rna_path, index=rotation_index, action_group=bone_name)
                        
#                     insert_keyframes(from_fcurve, to_fcurve, frame_current, smallest_x, apply)
                    
#             else:
#                 for rotation_index in range(3):
#                     rna_path = bone.path_from_id("rotation_euler")
#                     from_fcurve = from_action.fcurves.find(rna_path, index=rotation_index)
#                     if from_fcurve is None:
#                         break

#                     to_fcurve = to_action.fcurves.find(rna_path, index=rotation_index)
#                     if to_fcurve is None:
#                         to_fcurve = to_action.fcurves.new(rna_path, index=rotation_index, action_group=bone_name)
                        
#                     insert_keyframes(from_fcurve, to_fcurve, frame_current, smallest_x, apply)

#         time_taken = time.time() - now
#         print('copy_rotation_to_action time: ' + str(time_taken))
                    
#     def copy_scale_to_action(from_action: Action, to_action: Action, frame_current: float, smallest_x: float, bone_names, apply: bool):
#         now = time.time()

#         # bone_names = {bone.name for bone in bpy.context.selected_pose_bones_from_active_object}
#         for bone_name in bone_names:
#             for scale_index in range(3):
#                 bone = bpy.context.object.pose.bones[bone_name]
#                 rna_path = bone.path_from_id("scale")
#                 from_fcurve = from_action.fcurves.find(rna_path, index=scale_index)
#                 if from_fcurve is None:
#                     break

#                 to_fcurve = to_action.fcurves.find(rna_path, index=scale_index)
#                 if to_fcurve is None:
#                     to_fcurve = to_action.fcurves.new(rna_path, index=scale_index, action_group=bone_name)
                    
#                 for keyframe in from_fcurve.keyframe_points:
                    
#                     if not apply:
#                         if keyframe.select_control_point:
#                             to_fcurve.keyframe_points.insert(frame=keyframe.co.x, value=keyframe.co.y)
#                     else:
#                         to_fcurve.keyframe_points.insert(frame=(keyframe.co.x + frame_current) - smallest_x, value=keyframe.co.y)

#         time_taken = time.time() - now
#         print('copy_scale_to_action time: ' + str(time_taken))
    
#     @classmethod
#     def poll(cls, context: bpy.types.Context) -> bool:
#         return context.active_object is not None

#     def execute(self, context: bpy.types.Context):
#         bpy.ops.poselib.pose_asset_select_bones(select=True)
        
#         current_library = getattr(context, "asset_library_ref", None)
#         asset_file = getattr(context, "asset_file_handle", None)

#         if not asset_file.local_id:  # NOT Current file
#             asset_fullpath = Path(bpy.types.AssetHandle.get_full_library_path(asset_file, current_library))
#             print('Asset name: ' + asset_file.name)
#             print('Asset full path: ' + str(asset_fullpath))
            
#             with bpy.data.libraries.load(str(asset_fullpath), assets_only = True) as (data_from, data_to):
#                 data_to.actions = [asset_file.name]
            
#         from_action = bpy.data.actions.get(asset_file.name)
#         to_action = None

#         try:
#             to_action = context.object.animation_data.action
#         except:
#             context.object.animation_data_create()
#             to_action = bpy.data.actions.new(context.object.name_full)
#             context.object.animation_data.action = to_action
            
#         frame_current = context.scene.frame_current

#         smallest_x = from_action.fcurves[0].keyframe_points[0].co.x
        
#         for fcurves in from_action.fcurves:
#             keyframe = fcurves.keyframe_points[0]
#             if keyframe.co.x < smallest_x:
#                 smallest_x = keyframe.co.x
                
#         bone_names = {bone.name for bone in bpy.context.selected_pose_bones_from_active_object}

#         self.copy_location_to_action(from_action, to_action, frame_current, smallest_x, bone_names, True)
#         self.copy_rotation_to_action(from_action, to_action, frame_current, smallest_x, bone_names, True)
#         self.copy_scale_to_action(from_action, to_action, frame_current, smallest_x, bone_names, True)

#         bpy.ops.poselib.pose_asset_select_bones(select=False)

#         if not asset_file.local_id:
#             bpy.data.actions.remove(from_action)
        
#         return {'FINISHED'}

def animation_menu_func(self: UIList, context: Context) -> None:
    props = context.scene.clone_props

    asset_file = get_context_asset(context)
    asset_fullpath = get_asset_full_library_path(context, asset_file)
    if asset_file is None or asset_fullpath is None:
        return

    pack_type = asset_fullpath.parent.parent.name

    if pack_type == 'animations':
        layout = self.layout
        layout.separator()

        has_nla_track = False
        main_arm = get_object('Genesis8_1' + props.gender.capitalize())

        if main_arm.animation_data is not None:
            nla_tracks = main_arm.animation_data.nla_tracks

            if len(nla_tracks) > 0:
                has_nla_track = True

        layout.operator(CT_OT_ApplyAnimationAsset.bl_idname, text='Apply Animation').operation = 'apply'

        if has_nla_track:
            layout.operator(CT_OT_ApplyAnimationAsset.bl_idname, text='Append Animation').operation = 'append'

        layout.separator()

def filter_style_gender_func(self, context):
    layout = self.layout

    row = layout.row(align=True)
    row.label(text='Gender:')
    row.operator(CT_OT_FilterStylesByGender.bl_idname, text='both').filter_gender = ''
    row.operator(CT_OT_FilterStylesByGender.bl_idname, text='male').filter_gender = 'm_'
    row.operator(CT_OT_FilterStylesByGender.bl_idname, text='female').filter_gender = 'f_'   

# def wearable_equip_handler(dummy):
#     # Check to see if the active object is an asset
#     # and has a 'wearable' tag
#     is_wearable = False
#     obj = ao()

#     if obj.asset_data:
#         tags = obj.asset_data.tags
        
#         if 'wearable' in tags:
#             # Set the location to (0,0,0) and add it to the trait collection
#             obj.location = (0,0,0)
#             trait_coll = bpy.context.scene.clone_props.trait_collection

#             if trait_coll:
#                 trait = trait_coll.add()
#                 trait.name = obj.name

# === ENHANCED CLONE TOOLS OPERATORS ===

class CT_OT_FixScaleMismatch(Operator):
    """Fix scale mismatch between character and traits"""
    
    bl_idname = "ct.fix_scale_mismatch"
    bl_label = "Fix Scale Mismatch"
    bl_description = "Automatically detect and fix scale inconsistencies between character and traits"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("CloneX: 🔧 Manual scale fix requested...")
        
        if ctutils.detect_scale_mismatch():
            if ctutils.normalize_clone_scales():
                self.report({'INFO'}, "Scale mismatch fixed successfully")
                print("CloneX: ✅ Scale mismatch fixed successfully")
            else:
                self.report({'WARNING'}, "Scale normalization failed")
                print("CloneX: ❌ Scale normalization failed")
        else:
            self.report({'INFO'}, "No scale mismatch detected")
            print("CloneX: ✅ No scale issues found")
        
        return {'FINISHED'}

class CT_OT_AutoPositionTraits(Operator):
    """Automatically position traits on character"""
    
    bl_idname = "ct.auto_position_traits"
    bl_label = "Auto-Position Traits"
    bl_description = "Automatically position all traits on the character based on trait type"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("CloneX: 🎯 Manual trait positioning requested...")
        
        if ctutils.auto_position_traits():
            self.report({'INFO'}, "Traits positioned successfully")
            print("CloneX: ✅ Traits positioned successfully")
        else:
            self.report({'WARNING'}, "No traits found to position")
            print("CloneX: ⚠️  No traits found to position")
        
        return {'FINISHED'}

class CT_OT_ForceRegisterTraits(Operator):
    """Force register all traits in Style panel"""
    
    bl_idname = "ct.force_register_traits"
    bl_label = "Force Register Traits"
    bl_description = "Force register all loaded trait collections in the Style panel"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("CloneX: 📋 Manual trait registration requested...")
        
        registered_count = ctutils.force_register_all_traits()
        
        if registered_count > 0:
            self.report({'INFO'}, f"Registered {registered_count} new traits")
            print(f"CloneX: ✅ Registered {registered_count} new traits")
        else:
            self.report({'INFO'}, "All traits already registered")
            print("CloneX: ✅ All traits already registered")
        
        return {'FINISHED'}

class CT_OT_EnhancedCloneImport(Operator):
    """Complete enhanced Clone import with all automatic fixes"""
    
    bl_idname = "ct.enhanced_clone_import"
    bl_label = "Enhanced Clone Import"
    bl_description = "Apply all automatic fixes to the current Clone import"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        print("CloneX: 🚀 Enhanced Clone Import requested...")
        
        validation_results = ctutils.enhanced_clone_import()
        
        if validation_results['all_checks_passed']:
            self.report({'INFO'}, "Enhanced Clone import completed successfully")
            print("CloneX: ✅ Enhanced Clone import completed successfully")
        else:
            failed_checks = []
            if not validation_results['character_found']:
                failed_checks.append("character not found")
            if validation_results['traits_found'] == 0:
                failed_checks.append("no traits found")
            if not validation_results['scale_consistent']:
                failed_checks.append("scale issues")
            if not validation_results['traits_positioned']:
                failed_checks.append("positioning issues")
            if not validation_results['traits_registered']:
                failed_checks.append("registration issues")
            
            failure_msg = f"Enhanced import completed with issues: {', '.join(failed_checks)}"
            self.report({'WARNING'}, failure_msg)
            print(f"CloneX: ⚠️  {failure_msg}")
        
        return {'FINISHED'}

class CT_OT_AnalyzeCloneState(Operator):
    """Analyze current Clone state for debugging"""
    
    bl_idname = "ct.analyze_clone_state" 
    bl_label = "Analyze Clone State"
    bl_description = "Debug tool to analyze current Clone state (scale, positioning, registration)"
    bl_options = {'REGISTER'}

    def execute(self, context):
        print("CloneX: 🔍 Starting Clone state analysis...")
        
        # Run all analysis functions
        scale_ok = ctutils.analyze_clone_scales()
        position_ok = ctutils.analyze_trait_positions()
        registration_ok = ctutils.debug_trait_registration()
        
        if scale_ok and position_ok and registration_ok:
            self.report({'INFO'}, "Clone state analysis: All systems normal")
            print("CloneX: ✅ Clone state analysis: All systems normal")
        else:
            issues = []
            if not scale_ok:
                issues.append("scale issues")
            if not position_ok:
                issues.append("positioning issues")
            if not registration_ok:
                issues.append("registration issues")
            
            issue_msg = f"Clone state issues detected: {', '.join(issues)}"
            self.report({'WARNING'}, issue_msg)
            print(f"CloneX: ⚠️  {issue_msg}")
        
        return {'FINISHED'}

classes = (
    CT_OT_CloneSelectOperator,
    CT_OT_LoadPosesOperator,
    CT_OT_EquipWearableOperator,
    CT_OT_UnequipWearableOperator,
    CT_OT_LoadEnvOperator,
    CT_OT_ExportOperator,
    CT_OT_RenderCharacterSheet,
    CT_OT_RebuildCharacterSheet,
    CT_OT_MixamoButton,
    CT_OT_PoseModeButton,
    CT_OT_InitStyleLibraryButton,
    CT_OT_SyncStyleLibraryButton,
    CT_OT_OpenStyleLibraryButton,
    CT_OT_BlenderStyleSelectOperator,
    CT_OT_GlbStyleSelectOperator,
    CT_OT_FinalizeImportOperator,
    CT_OT_ImportStyleButton,
    CT_OT_ObjectZoomOperator,
    CT_OT_FilterStylesByGender,
    CT_OT_ApplyDnaHeadOperator,
    CT_OT_ApplyDnaSuitOperator,
    CT_OT_InstallContentPackOperator,
    CT_OT_ApplyAnimationAsset,
    CT_OT_ApplyPoseFromDropdown,
    CT_OT_RefreshContentPacks,
    CT_OT_ApplyFacialFeatureOperator,
    CT_OT_RemoveFacialFeatureOperator,
    # Enhanced Clone Tools operators
    CT_OT_FixScaleMismatch,
    CT_OT_AutoPositionTraits,
    CT_OT_ForceRegisterTraits,
    CT_OT_EnhancedCloneImport,
    CT_OT_AnalyzeCloneState
)

def register():
    for cls in classes:
        register_class(cls)

    for al in bpy.context.preferences.filepaths.asset_libraries:
        print('Checking library ' + al.name)
        if al.name == 'CloneX Style Library':
            print('Found CloneX Style Library')
            bpy.context.window_manager.ctglobals.style_lib_initialized = True

            break

    if hasattr(bpy.types, "UI_MT_list_item_context_menu"):
        bpy.types.UI_MT_list_item_context_menu.prepend(animation_menu_func)
    if hasattr(bpy.types, "FILEBROWSER_HT_header"):
        bpy.types.FILEBROWSER_HT_header.append(filter_style_gender_func)
    # bpy.app.handlers.depsgraph_update_post.append(wearable_equip_handler)   

def unregister():
    for cls in reversed(classes):
        unregister_class(cls)

    if hasattr(bpy.types, "FILEBROWSER_HT_header"):
        bpy.types.FILEBROWSER_HT_header.remove(filter_style_gender_func)
    if hasattr(bpy.types, "UI_MT_list_item_context_menu"):
        bpy.types.UI_MT_list_item_context_menu.remove(animation_menu_func)
