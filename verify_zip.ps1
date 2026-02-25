Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = "D:\Users\DCM\OneDrive\Documents\GitHub\clone_tools_2_5_Clonex_WTFork\build\clonex_wtfork_v2.5.0.zip"
$zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)

Write-Host "ZIP Contents (first 10 entries):" -ForegroundColor Yellow
$count = 0
foreach ($entry in $zip.Entries) {
    if ($count -lt 10) {
        Write-Host "  $($entry.FullName)"
        $count++
    }
}

# Check for proper structure
$hasInitPy = $false
foreach ($entry in $zip.Entries) {
    if ($entry.FullName -eq "clonex_wtfork\__init__.py" -or $entry.FullName -eq "clonex_wtfork/__init__.py") {
        $hasInitPy = $true
        break
    }
}

Write-Host ""
if ($hasInitPy) {
    Write-Host "ZIP structure is correct for Blender installation" -ForegroundColor Green
} else {
    Write-Host "Warning: ZIP structure may not be correct" -ForegroundColor Red
}

$zip.Dispose()
