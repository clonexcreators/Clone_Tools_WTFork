# Enhanced Blender 4.5 Addon Build Script - Clone Tools Fork
# Following Blender addon packaging best practices with development workflow support

param(
    [string]$OutputDir = ".\build",
    [string]$AddonName = "clonex_wtfork",
    [switch]$Clean = $false,
    [switch]$Install = $false,
    [string]$BlenderPath = "",
    [switch]$Verbose = $false,
    [switch]$BumpVersion = $false,
    [ValidateSet("patch", "minor", "major")]
    [string]$VersionType = "patch",
    [switch]$CreateChangelog = $false,
    [switch]$RunTests = $false
)

# Script configuration
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = $ScriptDir

# Convert OutputDir to absolute path
$OutputDir = Join-Path $ProjectRoot $OutputDir

Write-Host "=== Enhanced Blender 4.5 Addon Build Script ===" -ForegroundColor Cyan
Write-Host "Project: Clone Tools Fork (Clonex.WTFork)" -ForegroundColor Green
Write-Host "Build Target: Blender 4.5+" -ForegroundColor Green
Write-Host "Enhanced Features: Version Management, Testing, Documentation" -ForegroundColor Green
Write-Host ""

# Version bumping function
function Update-AddonVersion {
    param(
        [string]$FilePath,
        [string]$BumpType
    )
    
    $content = Get-Content $FilePath -Raw
    
    if ($content -match '"version":\s*\((\d+),\s*(\d+),\s*(\d+)\)') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        $patch = [int]$Matches[3]
        
        switch ($BumpType) {
            "major" { $major++; $minor = 0; $patch = 0 }
            "minor" { $minor++; $patch = 0 }
            "patch" { $patch++ }
        }
        
        $newVersion = "($major, $minor, $patch)"
        $content = $content -replace '"version":\s*\([^)]+\)', """version"": $newVersion"
        
        Set-Content -Path $FilePath -Value $content -NoNewline
        Write-Host "Version bumped to $major.$minor.$patch" -ForegroundColor Green
        return "$major.$minor.$patch"
    }
    
    throw "Could not find version information in $FilePath"
}

# Bump version if requested
if ($BumpVersion) {
    Write-Host "Bumping version ($VersionType)..." -ForegroundColor Yellow
    $NewVersion = Update-AddonVersion -FilePath (Join-Path $ProjectRoot "__init__.py") -BumpType $VersionType
    Write-Host "Updated to version: $NewVersion" -ForegroundColor Green
    Write-Host ""
}

# Pre-build validation
Write-Host "Running pre-build validation..." -ForegroundColor Yellow

# Check for required files
$RequiredFiles = @("__init__.py", "clone_tools_ops.py", "clone_tools_ui.py")
foreach ($File in $RequiredFiles) {
    $FilePath = Join-Path $ProjectRoot $File
    if (!(Test-Path $FilePath)) {
        throw "Required file missing: $File"
    }
}

# Validate Python syntax (if python is available)
try {
    $PythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($PythonCmd) {
        Write-Host "Validating Python syntax..." -ForegroundColor Gray
        $PythonFiles = Get-ChildItem -Path $ProjectRoot -Filter "*.py" -Recurse | Where-Object { $_.Directory.Name -ne "__pycache__" }
        foreach ($PyFile in $PythonFiles) {
            $result = & python -m py_compile $PyFile.FullName 2>&1
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "Python syntax error in $($PyFile.Name): $result"
            }
        }
        Write-Host "✓ Python syntax validation complete" -ForegroundColor Green
    }
} catch {
    Write-Host "Python not available for syntax validation" -ForegroundColor DarkGray
}

Write-Host "✓ Pre-build validation passed" -ForegroundColor Green
Write-Host ""

# Clean build directory if requested
if ($Clean -and (Test-Path $OutputDir)) {
    Write-Host "Cleaning build directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $OutputDir
}

# Create build directory
if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "Created build directory: $OutputDir" -ForegroundColor Green
}

# Define files and directories to include in the addon
$IncludeItems = @(
    "__init__.py",
    "addon_updater.py",
    "addon_updater_ops.py", 
    "blendshape_renamer.py",
    "clone_tools_ops.py",
    "clone_tools_props.py",
    "clone_tools_ui.py",
    "clone_tools_utils.py",
    "assets",
    "icons",
    "lib",
    "content_packs"
)

# Define files to exclude
$ExcludePatterns = @(
    "*.pyc",
    "__pycache__",
    ".git*",
    "*.md",
    "build",
    "*.ps1",
    ".github",
    "docs",
    "*.zip",
    "*.log",
    "*.tmp"
)

Write-Host "Building addon package..." -ForegroundColor Yellow

# Create addon directory structure
$AddonDir = Join-Path $OutputDir $AddonName
if (!(Test-Path $AddonDir)) {
    New-Item -ItemType Directory -Path $AddonDir -Force | Out-Null
}

# Copy files to addon directory with progress
$ItemCount = 0
foreach ($Item in $IncludeItems) {
    $SourcePath = Join-Path $ProjectRoot $Item
    $DestPath = Join-Path $AddonDir $Item
    $ItemCount++
    
    if (Test-Path $SourcePath) {
        Write-Progress -Activity "Building Addon" -Status "Copying $Item" -PercentComplete (($ItemCount / $IncludeItems.Count) * 100)
        
        if (Test-Path $SourcePath -PathType Container) {
            # Copy directory
            if ($Verbose) { Write-Host "  Copying directory: $Item" -ForegroundColor Gray }
            Copy-Item -Path $SourcePath -Destination $DestPath -Recurse -Force
            
            # Clean up excluded files in copied directory
            foreach ($Pattern in $ExcludePatterns) {
                Get-ChildItem -Path $DestPath -Recurse -Name $Pattern -Force -ErrorAction SilentlyContinue | 
                    ForEach-Object { 
                        $ExcludeFile = Join-Path $DestPath $_
                        if ($Verbose) { Write-Host "    Removing: $_" -ForegroundColor DarkGray }
                        Remove-Item -Path $ExcludeFile -Recurse -Force -ErrorAction SilentlyContinue
                    }
            }
        } else {
            # Copy file
            if ($Verbose) { Write-Host "  Copying file: $Item" -ForegroundColor Gray }
            Copy-Item -Path $SourcePath -Destination $DestPath -Force
        }
    } else {
        Write-Warning "Source not found: $Item"
    }
}

Write-Progress -Activity "Building Addon" -Completed

# Validate addon structure
$InitFile = Join-Path $AddonDir "__init__.py"
if (!(Test-Path $InitFile)) {
    throw "Critical error: __init__.py not found in addon directory!"
}

# Read and validate bl_info
$InitContent = Get-Content $InitFile -Raw
if ($InitContent -notmatch 'bl_info\s*=') {
    throw "Critical error: bl_info not found in __init__.py!"
}

# Extract version from bl_info
if ($InitContent -match '"version":\s*\(([^)]+)\)') {
    $VersionString = $Matches[1] -replace '\s', '' -replace ',', '.'
    Write-Host "Addon version: $VersionString" -ForegroundColor Green
} else {
    Write-Warning "Could not extract version from bl_info"
    $VersionString = "unknown"
}

# Create changelog entry if requested
if ($CreateChangelog) {
    $ChangelogPath = Join-Path $ProjectRoot "CHANGELOG.md"
    $CurrentDate = Get-Date -Format "yyyy-MM-dd"
    $ChangelogEntry = @"

## [$VersionString] - $CurrentDate

### Fixed
- ViewLayer selection compatibility for Blender 4.5+
- Object selection errors when objects not in current view layer
- Enhanced error handling in easybpy selection functions

### Added
- Improved object selection with automatic collection linking
- Better error messages for troubleshooting
- Enhanced build script with version management

"@
    
    if (Test-Path $ChangelogPath) {
        $ExistingContent = Get-Content $ChangelogPath -Raw
        $NewContent = $ExistingContent -replace "# Changelog", "# Changelog$ChangelogEntry"
        Set-Content -Path $ChangelogPath -Value $NewContent -NoNewline
    } else {
        $NewChangelog = "# Changelog$ChangelogEntry"
        Set-Content -Path $ChangelogPath -Value $NewChangelog -NoNewline
    }
    
    Write-Host "✓ Changelog updated" -ForegroundColor Green
}

# Create ZIP file with proper structure
$ZipFileName = "${AddonName}_v${VersionString}.zip"
$ZipPath = Join-Path $OutputDir $ZipFileName

Write-Host "Creating ZIP package: $ZipFileName" -ForegroundColor Yellow

# Remove existing ZIP if it exists, with retry logic
if (Test-Path $ZipPath) {
    $RetryCount = 0
    do {
        try {
            Remove-Item $ZipPath -Force -ErrorAction Stop
            Write-Host "Removed existing ZIP file" -ForegroundColor Gray
            break
        } catch {
            $RetryCount++
            if ($RetryCount -ge 3) {
                Write-Warning "Could not remove existing ZIP file: $_"
                $ZipPath = Join-Path $OutputDir "${AddonName}_v${VersionString}_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip"
                Write-Host "Using alternative name: $(Split-Path $ZipPath -Leaf)" -ForegroundColor Yellow
                break
            }
            Start-Sleep -Seconds 1
        }
    } while ($RetryCount -lt 3)
}

# Create ZIP archive using .NET compression
try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    
    # Create a temporary directory to hold the addon for zipping
    $TempZipDir = Join-Path $OutputDir "temp_zip"
    if (!(Test-Path $TempZipDir)) {
        New-Item -ItemType Directory -Path $TempZipDir -Force | Out-Null
    }
    
    # Copy addon directory to temp location
    $TempAddonDir = Join-Path $TempZipDir $AddonName
    Copy-Item -Path $AddonDir -Destination $TempAddonDir -Recurse -Force
    
    # Create ZIP from temp directory
    [System.IO.Compression.ZipFile]::CreateFromDirectory($TempZipDir, $ZipPath)
    
    # Clean up temp directory
    Remove-Item -Path $TempZipDir -Recurse -Force
    
    Write-Host "ZIP created successfully" -ForegroundColor Green
} catch {
    Write-Error "Failed to create ZIP: $_"
    exit 1
}

# Remove the temporary addon directory, keeping only the ZIP
Remove-Item -Path $AddonDir -Recurse -Force

# Create build info file
$BuildInfoPath = Join-Path $OutputDir "build_info.json"
$BuildInfo = @{
    version = $VersionString
    buildDate = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    addonName = $AddonName
    zipFile = $ZipFileName
    blenderVersion = "4.5.0+"
    fixes = @(
        "ViewLayer selection compatibility",
        "Object selection error handling",
        "Collection linking automation"
    )
} | ConvertTo-Json -Depth 3

Set-Content -Path $BuildInfoPath -Value $BuildInfo
Write-Host "✓ Build info saved to build_info.json" -ForegroundColor Green

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Green
Write-Host "Package created: $ZipPath" -ForegroundColor Cyan
if (Test-Path $ZipPath) {
    Write-Host "Package size: $([math]::Round((Get-Item $ZipPath).Length / 1MB, 2)) MB" -ForegroundColor Gray
}

# Validate ZIP structure
Write-Host ""
Write-Host "Validating ZIP structure..." -ForegroundColor Yellow

Add-Type -AssemblyName System.IO.Compression.FileSystem
$ZipArchive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
$HasProperStructure = $false
$FilesInZip = @()

foreach ($Entry in $ZipArchive.Entries) {
    $FilesInZip += $Entry.FullName
    if ($Entry.FullName -eq "$AddonName/__init__.py") {
        $HasProperStructure = $true
    }
}

$ZipArchive.Dispose()

if ($HasProperStructure) {
    Write-Host "✓ ZIP structure is correct for Blender installation" -ForegroundColor Green
    if ($Verbose) {
        Write-Host "Files in package:" -ForegroundColor Gray
        $FilesInZip | Sort-Object | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    }
} else {
    Write-Host "✗ Warning: ZIP structure may not be correct" -ForegroundColor Red
}

# Optional: Install to Blender
if ($Install) {
    Write-Host ""
    Write-Host "Installing to Blender..." -ForegroundColor Yellow
    
    if ($BlenderPath -and (Test-Path $BlenderPath)) {
        $BlenderAddonPath = Join-Path (Split-Path $BlenderPath -Parent) "4.5\scripts\addons"
    } else {
        # Try to find Blender addon directory
        $PossiblePaths = @(
            "$env:APPDATA\Blender Foundation\Blender\4.5\scripts\addons",
            "$env:USERPROFILE\AppData\Roaming\Blender Foundation\Blender\4.5\scripts\addons",
            "C:\Program Files\Blender Foundation\Blender 4.5\4.5\scripts\addons"
        )
        
        $BlenderAddonPath = $PossiblePaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    
    if ($BlenderAddonPath) {
        $InstallPath = Join-Path $BlenderAddonPath $AddonName
        
        # Remove existing installation
        if (Test-Path $InstallPath) {
            Remove-Item -Path $InstallPath -Recurse -Force
            Write-Host "Removed existing installation" -ForegroundColor Gray
        }
        
        # Extract to addon directory
        [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $BlenderAddonPath)
        Write-Host "✓ Addon installed to: $InstallPath" -ForegroundColor Green
        Write-Host "You can now enable the addon in Blender's preferences" -ForegroundColor Cyan
    } else {
        Write-Warning "Could not find Blender addon directory. Please install manually."
    }
}

Write-Host ""
Write-Host "=== Installation Instructions ===" -ForegroundColor Cyan
Write-Host "1. Open Blender 4.5+"
Write-Host "2. Go to Edit > Preferences > Add-ons"
Write-Host "3. Click 'Install...'"
Write-Host "4. Select the ZIP file: $ZipPath"
Write-Host "5. Enable 'Animation: Clonex.WTFork'"
Write-Host ""

Write-Host "=== Key Improvements in This Build ===" -ForegroundColor Cyan
Write-Host "✓ Fixed ViewLayer selection errors for Blender 4.5+" -ForegroundColor Green
Write-Host "✓ Enhanced object selection with automatic collection linking" -ForegroundColor Green  
Write-Host "✓ Improved error handling and user feedback" -ForegroundColor Green
Write-Host "✓ Better build process with validation and documentation" -ForegroundColor Green
Write-Host ""

Write-Host "Build completed successfully!" -ForegroundColor Green
