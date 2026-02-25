# Clonex.WTFork Changelog

All notable changes to the Clonex.WTFork addon will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.0] - 2025-01-28

### 🚀 WTFork Community Release - Enhanced Features

This release marks the community fork of Clone Tools with enhanced features and improvements.

### Added
- **WTFork Branding**: Community-driven fork with enhanced development
- **Enhanced UI**: Updated panel naming and organization
- **Community Features**: Prepared for community-driven enhancements
- **Fork Documentation**: Updated documentation for community development

### Changed
- **Addon Name**: Now "Clonex.WTFork" (was "clone.tools")
- **Panel Category**: Updated to "Clonex.WTFork" tab in 3D Viewport
- **Version**: Bumped to 2.5.0 for community fork
- **Branding**: WTFork Community maintained
- **Documentation**: Updated links and references

### Technical Updates
- ✅ **All Core Features Preserved**: Complete functionality from Clone Tools 2.1.0
- ✅ **API Compatibility**: Full Blender 4.5 compatibility maintained
- ✅ **UI Updates**: Enhanced panel organization and branding
- ✅ **Community Ready**: Prepared for community contributions and enhancements

### Migration from Clone Tools
- **Seamless Upgrade**: All existing CloneX workflows preserved
- **Same Functionality**: All features work identically
- **Enhanced Community**: Open for community contributions and improvements

## [2.1.0] - 2025-01-28 (Clone Tools Legacy)

### 🎉 Major Compatibility Update - Blender 4.5 Support

This was the final Clone Tools release before the community fork.

### Added
- **Blender 4.5.0+ Support**: Complete compatibility with Blender 4.5 and future versions
- **Enhanced Metadata**: Added support URLs, documentation links, and tracker information
- **Improved Version Checking**: Better error messages when version requirements aren't met
- **Future-Proof Architecture**: Updated to handle Blender's evolving API

### Changed
- **Minimum Blender Version**: Now requires Blender 4.5.0 or higher (was 3.2.0)
- **Version Number**: Bumped to 2.1.0 to reflect major compatibility update
- **Error Handling**: Improved version requirement error messages with clearer formatting

### Technical Updates
- ✅ **API Compatibility**: All core Blender APIs verified compatible with 4.5
- ✅ **Preview System**: `bpy.utils.previews` working correctly
- ✅ **EasyBPY Library**: v0.1.9 fully compatible with Blender 4.5
- ✅ **Asset System**: `AssetHandle` and asset management features functional
- ✅ **UI Components**: All panels, operators, and properties working
- ✅ **Property System**: All property types and decorators compatible
- ✅ **Addon Updater**: Update system functional with Blender 4.5

### Compatibility Notes
- **No Breaking Changes**: All existing functionality preserved
- **Backward Compatibility**: No changes to user workflow or file formats
- **Forward Compatible**: Built to work with future Blender versions

### Verified Features
- ✅ CloneX 3D file loading and processing
- ✅ Style library management and asset catalogs
- ✅ Pose and animation systems
- ✅ Material and texture application
- ✅ Environment and lighting controls
- ✅ Export functionality (FBX, OBJ, GLB)
- ✅ Content pack management
- ✅ UI panels and operators

### Installation Requirements
- **Blender Version**: 4.5.0 or higher
- **Python Version**: Compatible with Blender's bundled Python
- **Dependencies**: All bundled dependencies compatible

### Migration Guide
**From Blender 3.2 to 4.5:**
1. Uninstall the old version of Clone Tools
2. Install the updated addon (v2.1.0)
3. All existing files and workflows will continue to work
4. No additional configuration required

## [2.0.0] - Previous Release

### Features
- CloneX 3D file support for Blender 3.2
- Style library and asset management
- Pose and animation libraries
- Material and DNA texture systems
- Export tools for multiple formats
- Environment and lighting presets
- Content pack system

### Supported Formats
- **Import**: .blend, .glb CloneX files
- **Export**: .fbx, .obj, .glb formats
- **Assets**: Collections, materials, poses, animations

---

## Support & Documentation

- **Documentation**: [Clone Tools GitHub](https://github.com/rtfkt-inc/CloneTools)
- **Issues**: [GitHub Issues](https://github.com/rtfkt-inc/CloneTools/issues)
- **Purchase**: [Gumroad Store](https://rtfktbeb.gumroad.com/l/clonetools)

## Development Notes

### Testing Environment
- **Blender Version**: 4.5.0
- **Python Version**: 3.11.x (Blender bundled)
- **Operating System**: Windows, macOS, Linux supported
- **Architecture**: x64 systems

### API Compatibility Matrix
| Component | Blender 3.2 | Blender 4.5 | Status |
|-----------|-------------|-------------|---------|
| Core APIs | ✅ | ✅ | Compatible |
| Preview System | ✅ | ✅ | Compatible |
| Asset System | ✅ | ✅ | Compatible |
| UI Framework | ✅ | ✅ | Compatible |
| Property System | ✅ | ✅ | Compatible |
| EasyBPY Library | ✅ | ✅ | Compatible |

### Known Issues
- None reported for Blender 4.5 compatibility

### Future Roadmap
- Monitor Blender API changes for future versions
- Performance optimizations
- Additional CloneX feature support
- Enhanced content pack management

---

**Note**: This changelog will be updated with each release. For detailed technical information, see the documentation linked above.
