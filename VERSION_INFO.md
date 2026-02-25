# Clonex.WTFork Version Information

## Current Version: 2.5.0
**Release Date**: January 28, 2025  
**Compatibility**: Blender 4.5.0+  
**Fork**: Community-enhanced version of Clone Tools

---

## Version History

### 🎯 Version 2.5.0 (Current - WTFork Community Release)
- **Target Blender**: 4.5.0 and higher
- **Python Version**: 3.11.x (Blender bundled)
- **Release Type**: Community Fork with Enhancements
- **Status**: ✅ Stable - Community Maintained

**Key Updates:**
- Community fork with enhanced development model
- Updated branding to "Clonex.WTFork"
- Enhanced UI panel organization
- All Clone Tools 2.1.0 features preserved
- Prepared for community-driven improvements

### 📋 Version 2.1.0 (Clone Tools Legacy)
- **Target Blender**: 4.5.0 and higher
- **Status**: 🔄 Legacy (superseded by WTFork)
- **Original**: RTFKT Clone Tools final release

---

## Blender Compatibility Matrix

| Blender Version | Clonex.WTFork Version | Support Status | Notes |
|----------------|-------------------|---------------|--------|
| 4.5.0+ | 2.5.0 | ✅ **Current** | Community fork with enhancements |
| 4.5.0+ | 2.1.0 | ⚠️ Legacy | Original Clone Tools (use 2.5.0) |
| 4.0.0 - 4.4.x | 2.0.0 | ❌ Deprecated | Upgrade to 2.5.0 recommended |
| 3.6.0 - 3.6.x | 2.0.0 | ❌ Deprecated | Legacy support only |
| 3.2.0 - 3.5.x | 2.0.0 | ❌ Deprecated | Original target version |
| < 3.2.0 | ❌ Not Supported | ❌ Incompatible | Upgrade required |

## API Compatibility Status

### ✅ Fully Compatible APIs
- **Core Blender APIs**: `bpy.types`, `bpy.utils`, `bpy.props`
- **Preview System**: `bpy.utils.previews`
- **Asset System**: `bpy.types.AssetHandle`, asset libraries
- **UI Framework**: Panels, operators, properties, UILists
- **Handler System**: `bpy.app.handlers.persistent`
- **File I/O**: Import/export operations
- **Material System**: Node-based materials and textures

### 🔧 Dependencies Status
- **EasyBPY Library**: v0.1.9 - ✅ Compatible
- **Addon Updater**: ✅ Compatible
- **Python Standard Library**: ✅ Compatible

## Installation Requirements

### System Requirements
- **Operating System**: Windows 10+, macOS 10.15+, Linux (Ubuntu 18.04+)
- **Architecture**: 64-bit systems only
- **Memory**: 8GB RAM minimum (16GB recommended for large CloneX files)
- **Storage**: 500MB free space for addon and content packs

### Blender Requirements
- **Version**: Blender 4.5.0 or higher
- **Python**: Uses Blender's bundled Python (no external installation needed)
- **Features**: Asset Browser, Collections, Node Editor

## Feature Compatibility

### ✅ Verified Working Features
| Feature | Status | Notes |
|---------|---------|--------|
| CloneX File Import | ✅ Working | .blend and .glb formats |
| Style Library | ✅ Working | Asset catalogs and collections |
| Pose System | ✅ Working | Pose library and application |
| Animation System | ✅ Working | NLA tracks and blending |
| Material Management | ✅ Working | DNA textures and materials |
| Export Tools | ✅ Working | FBX, OBJ, GLB formats |
| Environment Controls | ✅ Working | Lighting and staging |
| Content Packs | ✅ Working | Pose and animation packs |
| UI Panels | ✅ Working | All panels and controls |
| Addon Updater | ✅ Working | Automatic update system |

### 🔄 Recently Updated Features
- Version checking system with improved error messages
- Enhanced bl_info metadata with support links
- Future-proof API usage patterns

## Known Issues & Limitations

### Current Known Issues
- **None reported** for Blender 4.5 compatibility

### Limitations
- **CloneX File Formats**: Only supports official CloneX .blend and .glb files
- **Memory Usage**: Large CloneX files may require significant RAM
- **Operating System**: Some features may behave differently across platforms

## Performance Notes

### Optimized For
- **File Loading**: Efficient handling of large CloneX assets
- **UI Responsiveness**: Non-blocking operations where possible
- **Memory Management**: Proper cleanup of temporary data

### Performance Tips
- Close unnecessary applications when working with large CloneX files
- Use SSD storage for better file loading performance
- Enable GPU acceleration in Blender preferences for better viewport performance

## Migration Guide

### From Version 2.0.0 to 2.1.0
1. **Backup**: Save your current work and preferences
2. **Uninstall**: Remove the old version from Blender
3. **Install**: Install version 2.1.0
4. **Verify**: Test basic functionality with a simple CloneX file
5. **Restore**: Your existing CloneX files and workflows will work unchanged

### From Blender 3.2 to 4.5
- All CloneX files remain compatible
- No changes to user workflow required
- Style libraries and content packs will work as before
- Export settings and preferences are preserved

## Support Information

### Getting Help
- **Documentation**: [GitHub Repository](https://github.com/rtfkt-inc/CloneTools)
- **Issues**: Report bugs via [GitHub Issues](https://github.com/rtfkt-inc/CloneTools/issues)
- **Community**: RTFKT Discord server for community support

### Reporting Issues
When reporting issues, please include:
- Clone Tools version (2.1.0)
- Blender version and build info
- Operating system and version
- Steps to reproduce the issue
- Error messages from Blender console

---

**Last Updated**: January 28, 2025  
**Maintained By**: RTFKT Development Team
