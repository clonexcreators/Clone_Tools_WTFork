from pathlib import Path


def get_context_asset(context):
    """Return the active asset from context in Blender 5.0+."""
    return getattr(context, "asset", None)

def get_asset_name(asset):
    return getattr(asset, "name", "")


def get_asset_id_type(asset):
    return getattr(asset, "id_type", None)


def is_local_asset(asset):
    local_id = getattr(asset, "local_id", None)
    return local_id is not None


def get_asset_full_library_path(context, asset=None):
    """Resolve full .blend path for an external asset in Blender 5.0+."""
    asset = asset or get_context_asset(context)
    if asset is None:
        return None

    full_library_path = getattr(asset, "full_library_path", None)
    if full_library_path:
        return Path(full_library_path)

    return None


def set_space_asset_library(space, library_name):
    """Set an Asset Browser space library field in Blender 5.0+."""
    if hasattr(space, "asset_library_reference"):
        try:
            setattr(space, "asset_library_reference", library_name)
            return True
        except Exception:
            return False
    return False
