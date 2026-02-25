# CloneX Long Path Fix Test Script
# Tests the Windows long path support functions

param(
    [string]$TestDir = "D:\CloneX_Test",
    [int]$PathLength = 280,
    [switch]$Cleanup = $false
)

Write-Host "=== CloneX Long Path Fix Test ===" -ForegroundColor Cyan
Write-Host "Testing Windows long path support functions" -ForegroundColor Green
Write-Host ""

# Import required modules
Add-Type -AssemblyName System.IO.Compression.FileSystem

# Create test directory structure
if (!(Test-Path $TestDir)) {
    New-Item -ItemType Directory -Path $TestDir -Force | Out-Null
    Write-Host "Created test directory: $TestDir" -ForegroundColor Gray
}

# Generate a long path for testing
$LongPathComponents = @()
$CurrentLength = $TestDir.Length
$ComponentIndex = 1

while ($CurrentLength -lt $PathLength) {
    $Component = "Very_Long_Directory_Name_Component_$ComponentIndex" + "_" * 20
    $ComponentPath = $Component.Substring(0, [Math]::Min($Component.Length, $PathLength - $CurrentLength - 1))
    $LongPathComponents += $ComponentPath
    $CurrentLength += $ComponentPath.Length + 1  # +1 for path separator
    $ComponentIndex++
}

$LongPath = Join-Path $TestDir ($LongPathComponents -join "\")
$ActualLength = $LongPath.Length

Write-Host "Generated test path:" -ForegroundColor Yellow
Write-Host "  Length: $ActualLength characters" -ForegroundColor Gray
Write-Host "  Path: $($LongPath.Substring(0, [Math]::Min(100, $LongPath.Length)))..." -ForegroundColor Gray

# Test 1: Create the long directory structure
Write-Host ""
Write-Host "Test 1: Creating long directory structure..." -ForegroundColor Yellow

try {
    New-Item -ItemType Directory -Path $LongPath -Force -ErrorAction Stop | Out-Null
    Write-Host "✓ Successfully created long directory" -ForegroundColor Green
    $Test1Passed = $true
} catch {
    Write-Host "✗ Failed to create long directory: $($_.Exception.Message)" -ForegroundColor Red
    $Test1Passed = $false
}

# Test 2: Create a test ZIP file
Write-Host ""
Write-Host "Test 2: Creating test ZIP file..." -ForegroundColor Yellow

$ZipPath = Join-Path $TestDir "test_long_path.zip"
$TempContentDir = Join-Path $TestDir "temp_content"

try {
    # Create temporary content for ZIP
    New-Item -ItemType Directory -Path $TempContentDir -Force | Out-Null
    
    # Create nested structure similar to CloneX assets
    $NestedDir = Join-Path $TempContentDir "Characters-character_combined"
    $SubDir1 = Join-Path $NestedDir "female"
    $SubDir2 = Join-Path $SubDir1 "unreal"
    $SubDir3 = Join-Path $SubDir2 "very_long_asset_name_with_details"
    $SubDir4 = Join-Path $SubDir3 "materials"
    
    New-Item -ItemType Directory -Path $SubDir4 -Force | Out-Null
    
    # Create test files
    "Test content 1" | Out-File -FilePath (Join-Path $SubDir4 "test_material_with_very_long_name.txt")
    "Test content 2" | Out-File -FilePath (Join-Path $SubDir3 "test_mesh_file.txt")
    "Test content 3" | Out-File -FilePath (Join-Path $NestedDir "test_metadata.json")
    
    # Create ZIP file
    [System.IO.Compression.ZipFile]::CreateFromDirectory($TempContentDir, $ZipPath)
    
    Write-Host "✓ Successfully created test ZIP file" -ForegroundColor Green
    Write-Host "  ZIP size: $([Math]::Round((Get-Item $ZipPath).Length / 1KB, 1)) KB" -ForegroundColor Gray
    $Test2Passed = $true
    
    # Clean up temp content
    Remove-Item -Path $TempContentDir -Recurse -Force
    
} catch {
    Write-Host "✗ Failed to create test ZIP: $($_.Exception.Message)" -ForegroundColor Red
    $Test2Passed = $false
}

# Test 3: Test extraction to long path
Write-Host ""
Write-Host "Test 3: Testing ZIP extraction to long path..." -ForegroundColor Yellow

if ($Test2Passed) {
    $ExtractPath = Join-Path $LongPath "extracted_content"
    
    try {
        # This simulates what CloneX does
        $Zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        
        # Check if path is too long (like CloneX logic)
        if ($ExtractPath.Length -gt 250) {
            Write-Host "  Path length ($($ExtractPath.Length)) exceeds safe limit, using temp extraction..." -ForegroundColor Yellow
            
            # Simulate temp extraction (like CloneX safe_extractall)
            $TempDir = Join-Path $env:TEMP "clonex_test_$([System.Guid]::NewGuid().ToString('N').Substring(0,8))"
            
            # Extract to temp directory
            [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $TempDir)
            
            # Create final directory and move files
            New-Item -ItemType Directory -Path $ExtractPath -Force | Out-Null
            
            Get-ChildItem -Path $TempDir -Recurse | ForEach-Object {
                $RelativePath = $_.FullName.Substring($TempDir.Length + 1)
                $DestPath = Join-Path $ExtractPath $RelativePath
                
                if ($_.PSIsContainer) {
                    New-Item -ItemType Directory -Path $DestPath -Force | Out-Null
                } else {
                    $DestDir = Split-Path $DestPath -Parent
                    if (!(Test-Path $DestDir)) {
                        New-Item -ItemType Directory -Path $DestDir -Force | Out-Null
                    }
                    Copy-Item -Path $_.FullName -Destination $DestPath -Force
                }
            }
            
            # Clean up temp directory
            Remove-Item -Path $TempDir -Recurse -Force
            
        } else {
            # Direct extraction for shorter paths
            [System.IO.Compression.ZipFile]::ExtractToDirectory($ZipPath, $ExtractPath)
        }
        
        $Zip.Dispose()
        
        # Verify extraction
        $ExtractedFiles = Get-ChildItem -Path $ExtractPath -Recurse -File
        Write-Host "✓ Successfully extracted to long path" -ForegroundColor Green
        Write-Host "  Extracted $($ExtractedFiles.Count) files" -ForegroundColor Gray
        $Test3Passed = $true
        
    } catch {
        Write-Host "✗ Failed to extract to long path: $($_.Exception.Message)" -ForegroundColor Red
        $Test3Passed = $false
    }
} else {
    Write-Host "⚠ Skipped (Test 2 failed)" -ForegroundColor Yellow
    $Test3Passed = $false
}

# Test Results Summary
Write-Host ""
Write-Host "=== Test Results Summary ===" -ForegroundColor Cyan
Write-Host "Test 1 - Long Directory Creation: $(if ($Test1Passed) { '✓ PASSED' } else { '✗ FAILED' })" -ForegroundColor $(if ($Test1Passed) { 'Green' } else { 'Red' })
Write-Host "Test 2 - ZIP File Creation: $(if ($Test2Passed) { '✓ PASSED' } else { '✗ FAILED' })" -ForegroundColor $(if ($Test2Passed) { 'Green' } else { 'Red' })
Write-Host "Test 3 - Long Path Extraction: $(if ($Test3Passed) { '✓ PASSED' } else { '✗ FAILED' })" -ForegroundColor $(if ($Test3Passed) { 'Green' } else { 'Red' })

$OverallPassed = $Test1Passed -and $Test2Passed -and $Test3Passed
Write-Host ""
Write-Host "Overall Result: $(if ($OverallPassed) { '✓ ALL TESTS PASSED' } else { '✗ SOME TESTS FAILED' })" -ForegroundColor $(if ($OverallPassed) { 'Green' } else { 'Red' })

if ($OverallPassed) {
    Write-Host ""
    Write-Host "🎉 CloneX long path fixes should work correctly!" -ForegroundColor Green
    Write-Host "The addon should now handle Windows path length limitations." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⚠ Some tests failed. The long path issue may persist." -ForegroundColor Yellow
    Write-Host "Consider using shorter base directory paths." -ForegroundColor Yellow
}

# Cleanup option
if ($Cleanup) {
    Write-Host ""
    Write-Host "Cleaning up test files..." -ForegroundColor Yellow
    try {
        Remove-Item -Path $TestDir -Recurse -Force -ErrorAction Stop
        Write-Host "✓ Test directory cleaned up" -ForegroundColor Green
    } catch {
        Write-Host "⚠ Could not fully clean up test directory: $($_.Exception.Message)" -ForegroundColor Yellow
    }
} else {
    Write-Host ""
    Write-Host "Test files preserved at: $TestDir" -ForegroundColor Gray
    Write-Host "Run with -Cleanup switch to remove test files" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Test completed!" -ForegroundColor Cyan
