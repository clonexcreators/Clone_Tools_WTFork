# Clone Tools Fork - Blender 4.5 Build Guide

## 🎯 Overview
This repository contains the Clone Tools Fork (Clonex.WTFork) addon properly configured and packaged for Blender 4.5+. The build system follows Blender addon best practices and resolves common packaging issues.

## ✅ Build System Features
- **Proper ZIP Structure**: Fixes the "**init**.py should be in a directory" error
- **Blender 4.5+ Compatibility**: Updated version requirements and compatibility checks
- **Automated Build Process**: PowerShell script with comprehensive error handling
- **File Validation**: Ensures correct addon structure before packaging
- **Clean Build Environment**: Removes temporary files and handles locked files

## 🚀 Quick Start

### Method 1: Double-Click Build (Easiest)
```
1. Double-click `build_addon.bat`
2. Wait for build to complete
3. Find the ZIP file in the `build` directory
```

### Method 2: PowerShell Command Line
```powershell
# Basic build
.\build_addon.ps1

# Clean build (recommended)
.\build_addon.ps1 -Clean

# Verbose output
.\build_addon.ps1 -Clean -Verbose

# Build and attempt installation
.\build_addon.ps1 -Install -BlenderPath "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
```

## 📦 Build Output
- **ZIP File**: `build/clonex_wtfork_v2.5.0.zip` (~21MB)
- **Structure**: Proper Blender addon format with `clonex_wtfork/__init__.py`
- **Validation**: Automatic structure verification

## 🔧 Installation Instructions

### In Blender:
1. Open Blender 4.5 or higher
2. Go to `Edit > Preferences > Add-ons`
3. Click `Install...`
4. Select `build/clonex_wtfork_v2.5.0.zip`
5. Enable `Animation: Clonex.WTFork`

### Verification:
- The addon should appear in the Animation category
- No import errors should occur
- All features should be accessible

## 📋 Build Script Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `-OutputDir` | Build output directory | `-OutputDir ".\dist"` |
| `-AddonName` | Addon directory name in ZIP | `-AddonName "my_addon"` |
| `-Clean` | Clean build directory first | `-Clean` |
| `-Install` | Auto-install to Blender | `-Install` |
| `-BlenderPath` | Path to Blender executable | `-BlenderPath "C:\...\blender.exe"` |
| `-Verbose` | Detailed output | `-Verbose` |

## 🛠️ Development Best Practices

### File Structure
```
clone_tools_2_5_Clonex_WTFork/
├── __init__.py              # Main addon entry point
├── *.py                     # Addon modules
├── assets/                  # Asset files
├── icons/                   # UI icons
├── lib/                     # Libraries
├── content_packs/           # Content packages
├── build_addon.ps1          # Build script
├── build_addon.bat          # Batch wrapper
└── build/                   # Build output (generated)
    └── clonex_wtfork_v2.5.0.zip
```

### Version Management
- Version defined in `bl_info` in `__init__.py`
- Automatic version extraction for ZIP naming
- Blender compatibility checking (requires 4.5+)

### Build Process
1. **Preparation**: Clean previous builds, create directories
2. **File Collection**: Copy all necessary addon files
3. **Cleanup**: Remove excluded files (*.pyc, __pycache__, etc.)
4. **Packaging**: Create properly structured ZIP
5. **Validation**: Verify ZIP structure
6. **Optional Installation**: Direct install to Blender

## 🔍 Troubleshooting

### Common Issues

#### "ZIP packaged incorrectly" Error
- **Cause**: __init__.py at ZIP root instead of in subdirectory
- **Solution**: Use the provided build script
- **Verification**: Check that ZIP contains `clonex_wtfork/__init__.py`

#### "File is being used by another process"
- **Cause**: Previous build artifacts locked by system
- **Solution**: Use `-Clean` parameter or manually delete build directory
- **Prevention**: Close file explorers and Blender before building

#### PowerShell Execution Policy
- **Error**: "execution of scripts is disabled"
- **Solution**: Run as Administrator and execute:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```

#### Blender Version Compatibility
- **Error**: Addon won't enable due to version mismatch
- **Check**: Ensure Blender 4.5+ is being used
- **Fix**: Update Blender or modify `bl_info["blender"]` version requirement

### Debug Commands
```powershell
# Check ZIP contents
.\verify_zip.ps1

# List build directory
Get-ChildItem -Path .\build -Recurse

# Check PowerShell execution policy
Get-ExecutionPolicy

# Test Blender path
Test-Path "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe"
```

## 📊 Build Validation

The build system automatically validates:
- ✅ Correct ZIP structure (`addon_name/__init__.py`)
- ✅ bl_info presence and format
- ✅ Version extraction
- ✅ File size reporting
- ✅ Required files inclusion

## 🔄 Continuous Integration Ready

The build script is designed for CI/CD environments:
- Non-interactive execution
- Proper exit codes
- Comprehensive logging
- Error handling and reporting

## 📝 Changelog Integration

Version 2.5.0 updates:
- ✅ Blender 4.5 compatibility
- ✅ Fixed ZIP packaging structure
- ✅ Automated build system
- ✅ Enhanced error handling
- ✅ Best practices implementation

## 🤝 Contributing

When making changes:
1. Test with `.\build_addon.ps1 -Clean -Verbose`
2. Verify ZIP structure with `.\verify_zip.ps1`
3. Test installation in clean Blender 4.5 instance
4. Update version in `__init__.py` if needed

## 📄 License

This project maintains the original Clone Tools license and adds community improvements under the same terms.

---

**Build completed successfully! 🎉**

The addon is now ready for distribution and installation in Blender 4.5+.
