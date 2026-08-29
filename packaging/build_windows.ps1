param(
    [string]$ArtifactDirectory = "artifacts"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExecutable = if ($env:SPADE65_BUILD_PYTHON) { $env:SPADE65_BUILD_PYTHON } else { "python" }
$Distribution = Join-Path $RepositoryRoot "dist\Spade65"
$OutputDirectory = Join-Path $RepositoryRoot $ArtifactDirectory
$Output = Join-Path $OutputDirectory "Spade65-Windows-x64.zip"

& $PythonExecutable (Join-Path $RepositoryRoot "packaging\check_version.py") --print-version | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $PythonExecutable -m PyInstaller --noconfirm --clean (Join-Path $RepositoryRoot "packaging\spade65.spec")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$Executable = Join-Path $Distribution "Spade65.exe"
$CliExecutable = Join-Path $Distribution "Spade65CLI.exe"
if (-not (Test-Path $Executable -PathType Leaf)) {
    throw "PyInstaller did not produce $Executable"
}
if (-not (Test-Path $CliExecutable -PathType Leaf)) {
    throw "PyInstaller did not produce $CliExecutable"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
if (Test-Path $Output) { Remove-Item -Force $Output }
Compress-Archive -Path (Join-Path $Distribution "*") -DestinationPath $Output
if (-not (Test-Path $Output -PathType Leaf)) {
    throw "Failed to create $Output"
}

$SmokeDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("Spade65-zip-smoke-" + [guid]::NewGuid())
try {
    Expand-Archive -Path $Output -DestinationPath $SmokeDirectory
    $ArchivedGui = Join-Path $SmokeDirectory "Spade65.exe"
    $ArchivedCli = Join-Path $SmokeDirectory "Spade65CLI.exe"
    if (-not (Test-Path $ArchivedGui -PathType Leaf)) {
        throw "Windows ZIP is missing Spade65.exe"
    }
    if (-not (Test-Path $ArchivedCli -PathType Leaf)) {
        throw "Windows ZIP is missing Spade65CLI.exe"
    }
    & $ArchivedCli --smoke-test
    if ($LASTEXITCODE -ne 0) { throw "Archived Windows smoke test failed" }
}
finally {
    if (Test-Path $SmokeDirectory) {
        Remove-Item -Recurse -Force $SmokeDirectory
    }
}
