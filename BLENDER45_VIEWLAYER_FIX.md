# Blender 4.5 ViewLayer Selection Fix

## Issue Description
The addon was experiencing `RuntimeError: Error: Object 'Genesis8_1MaleRig' can't be selected because it is not in View Layer 'ViewLayer'!` errors when trying to select objects that were not in the current view layer.

## Root Cause
In Blender 4.5+, objects must be accessible in the current view layer to be selected. The original `select_object()` and related functions in `lib/easybpy.py` didn't check for view layer accessibility before attempting selection.

## Implemented Fixes

### 1. Enhanced Object Selection Functions
- **Updated `select_object()`**: Now checks if object is in view layer before selection
- **Updated `select_objects()`**: Uses improved selection logic for multiple objects  
- **Updated `select_only()`**: Properly handles exclusive selection with view layer checks

### 2. New Utility Functions
- **`is_object_in_view_layer(obj)`**: Checks if an object is accessible in current view layer
- **`ensure_object_in_view_layer(obj)`**: Attempts to make object accessible by linking collections

### 3. Improved Error Handling
- Added try/catch blocks for selection operations
- Informative warning messages when objects can't be selected
- Graceful fallback behavior instead of hard crashes

### 4. Collection Linking Strategy
When objects are not in view layer, the fix attempts to:
1. Check if object's collections are linked to the scene
2. Link collections to scene hierarchy if needed
3. Verify object accessibility after collection linking

## Code Changes

### Before (Problematic):
```python
def select_object(ref, make_active=True):
    objref = get_object(ref)
    objref.select_set(True)  # Could fail with RuntimeError
    if make_active:
        bpy.context.view_layer.objects.active = objref
```

### After (Fixed):
```python
def select_object(ref, make_active=True):
    objref = get_object(ref)
    
    # Ensure object is accessible in view layer
    if not ensure_object_in_view_layer(objref):
        print(f"Warning: Object '{objref.name}' could not be made accessible")
        return False
    
    try:
        objref.select_set(True)
        if make_active:
            bpy.context.view_layer.objects.active = objref
    except RuntimeError as e:
        print(f"Warning: Could not select object '{objref.name}': {e}")
        return False
    
    return True
```

## Testing
- Build and install the updated addon
- Test object selection operations that previously failed
- Verify graceful handling of inaccessible objects

## Compatibility
- ✅ Blender 4.5.0+
- ✅ Backwards compatible with existing workflows
- ✅ Non-breaking changes (functions return boolean success status)

## Installation
Use the provided `build_addon.ps1` script to create the updated package:
```powershell
.\build_addon.ps1 -Verbose
```

The fix is automatically included in the built addon package.
