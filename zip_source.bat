@powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content '%~f0' | Select-Object -Skip 1 | Out-String | Invoke-Expression" & pause & exit /b

$sourceDir = "$PWD"
$parentDirName = (Get-Item $sourceDir).Name
$zipName = "${parentDirName}_source.zip"

Write-Host "============================================="
Write-Host "Zipping PURE Source Code (Codes Only)"
Write-Host "Source Folder: $sourceDir"
Write-Host "Output Zip:    $zipName"
Write-Host "============================================="
Write-Host ""

if (Test-Path $zipName) {
    Write-Host "Removing existing $zipName..."
    Remove-Item $zipName -Force
}

# Define extension patterns of code files to INCLUDE
$includeExtensions = @(
    # Python
    "*.py", "*.pyw",
    # Frontend / Javascript / Typescript
    "*.js", "*.jsx", "*.ts", "*.tsx", "*.html", "*.htm", "*.css", "*.scss", "*.sass", "*.less", "*.vue", "*.svelte",
    # Rust
    "*.rs", "Cargo.toml", "Cargo.lock",
    # Go
    "*.go", "go.mod", "go.sum",
    # C / C++ / C# / Java / Kotlin
    "*.c", "*.cpp", "*.cc", "*.cxx", "*.h", "*.hpp", "*.cs", "*.java", "*.kt",
    # Configuration and Data files (non-binary)
    "*.json", "*.yml", "*.yaml", "*.toml", "*.ini", "*.config", "*.xml", "*.csv", "*.sql",
    # Shell / Batch scripts
    "*.bat", "*.cmd", "*.sh", "*.ps1",
    # Documentation
    "*.md", "*.txt", "LICENSE", "README",
    # Package management & config files
    ".gitignore", ".env.example", "requirements.txt", "package.json", "package-lock.json", "tsconfig.json", "Dockerfile", "docker-compose.yml"
)

# Define directory names to EXCLUDE completely
$excludeNames = @(
    ".git", "node_modules", "__pycache__", "venv", ".venv", "env", "ENV",
    ".vscode", ".idea", "dist", "build", "target", "bin", "obj", "out",
    "models", "whisper", ".locks", "data"
)

# Recursive function to scan for files (ignores excluded directories)
function Get-CodeFiles($dir) {
    Get-ChildItem -Path $dir -Force | ForEach-Object {
        if ($_.PSIsContainer) {
            # Skip excluded folders entirely
            if ($excludeNames -notcontains $_.Name) {
                Get-CodeFiles $_.FullName
            }
        } else {
            # Include only matching code files
            $fileName = $_.Name
            foreach ($ext in $includeExtensions) {
                if ($fileName -like $ext) {
                    $_
                    break
                }
            }
        }
    }
}

# Find files
$files = Get-CodeFiles $sourceDir

if ($files) {
    Write-Host "Found $($files.Count) code files. Preparing package..."
    
    # Create a unique temp folder
    $tempDir = Join-Path $env:TEMP ("zip_temp_" + (Get-Date -Format "yyyyMMddHHmmss"))
    New-Item -ItemType Directory -Path $tempDir | Out-Null
    
    # Copy files while maintaining directory structure
    foreach ($file in $files) {
        $relPath = (Resolve-Path -Path $file.FullName -Relative) -replace '^\.\\', ''
        $destPath = Join-Path $tempDir $relPath
        $destParent = Split-Path $destPath -Parent
        
        if (!(Test-Path $destParent)) {
            New-Item -ItemType Directory -Path $destParent | Out-Null
        }
        
        Copy-Item -Path $file.FullName -Destination $destPath -Force
        Write-Host "Adding file: $relPath"
    }
    
    Write-Host "Compressing to $zipName..."
    Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $zipName -Force
    
    # Clean up temp folder
    Remove-Item -Path $tempDir -Recurse -Force
    Write-Host ""
    Write-Host "[SUCCESS] Created $zipName containing pure source code only!"
} else {
    Write-Host "Error: No code files found to zip."
}
