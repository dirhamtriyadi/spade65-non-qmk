param(
    [string]$ArtifactDirectory = "artifacts"
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExecutable = if ($env:SPADE65_BUILD_PYTHON) { $env:SPADE65_BUILD_PYTHON } else { "python" }
$Distribution = Join-Path $RepositoryRoot "dist\Spade65"
$OutputDirectory = Join-Path $RepositoryRoot $ArtifactDirectory
$Output = Join-Path $OutputDirectory "Spade65-Windows-x64.zip"

function Remove-SmokeDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    # A just-exited CLR/WebView2 process or antivirus scanner can briefly keep
    # a packaged DLL open. Retry the bounded cleanup instead of making an
    # otherwise valid artifact fail on that transient Windows lock.
    for ($Attempt = 1; $Attempt -le 10; $Attempt++) {
        try {
            Remove-Item -Recurse -Force $Path
            return
        }
        catch {
            if ($Attempt -eq 10) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
}

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

Copy-Item (Join-Path $RepositoryRoot "LICENSE") $Distribution
Copy-Item (Join-Path $RepositoryRoot "THIRD-PARTY-NOTICES.md") $Distribution
$LegalDirectory = Join-Path $Distribution "licenses"
New-Item -ItemType Directory -Force -Path $LegalDirectory | Out-Null
Copy-Item (Join-Path $RepositoryRoot "licenses\*") $LegalDirectory -Recurse

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
    foreach ($RelativePath in @(
        "LICENSE",
        "THIRD-PARTY-NOTICES.md",
        "licenses\GPL-3.0.txt",
        "licenses\LGPL-3.0.txt",
        "licenses\LGPL-2.1.txt",
        "licenses\Qt-6.11.2-LICENSE.Chromium",
        "licenses\QtWebEngine-6.11.2-THIRD-PARTY-NOTICES.html",
        "licenses\GFDL-1.3-no-invariants-only.txt",
        "licenses\PERMISSIVE-LICENSES.txt",
        "licenses\NUMPY-2.1.3-LINUX-WHEEL-LICENSE.txt",
        "licenses\NUMPY-2.5.2-LINUX-WHEEL-LICENSES.txt",
        "licenses\PYTHON-3.12.txt",
        "licenses\PYTHON-3.13.txt",
        "licenses\PYINSTALLER.txt"
    )) {
        if (-not (Test-Path (Join-Path $SmokeDirectory $RelativePath) -PathType Leaf)) {
            throw "Windows ZIP is missing $RelativePath"
        }
    }
    # PowerShell may return immediately after launching a GUI-subsystem binary.
    # Start-Process -Wait covers the complete PyInstaller process tree so its
    # CLR DLLs are released before the extracted archive is removed.
    $GuiSmoke = Start-Process -FilePath $ArchivedGui `
        -ArgumentList "--smoke-test" -Wait -PassThru
    if ($GuiSmoke.ExitCode -ne 0) {
        throw "Archived Windows GUI smoke test failed with exit code $($GuiSmoke.ExitCode)"
    }
    & $ArchivedCli --smoke-test
    if ($LASTEXITCODE -ne 0) { throw "Archived Windows smoke test failed" }
}
finally {
    if (Test-Path $SmokeDirectory) {
        Remove-SmokeDirectory -Path $SmokeDirectory
    }
}
