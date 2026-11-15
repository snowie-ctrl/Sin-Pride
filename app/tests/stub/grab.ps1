# Copied from Gluttony app/tests/stub/grab.ps1 at c1ed705; changes: Pride's switches and hooks (PRIDE_*), the stub on
# port 5089, -Exercise and -Text in place of recipes and queries, -CatalogDown, and -Offline as an offline start on
# the kept catalog.
# Runs the test build of the app against the stub API and saves a screenshot of one page. The stub serves snapshot/
# when it exists (snapshot.py), and the fixture's 11 exercises otherwise; -Fixture always serves the fixture (ids by
# name: 1 Barbell Curl, 5 Kettlebell Halo with no pictures, 6 Plank, 7 Pullups).
#   grab.ps1 -Out catalog.png -Fixture                          (the Catalog)
#   grab.ps1 -Out login.png -NewDevice                          (the sign-in form)
#   grab.ps1 -Out curls.png -Fixture -Text curl                 (the Catalog narrowed by name)
#   grab.ps1 -Out exercise.png -Fixture -Exercise 1             (Barbell Curl's page)
#   grab.ps1 -Out nopicture.png -Fixture -Exercise 5            (an exercise with no pictures)
#   grab.ps1 -Out plates.png -Fixture -PicturesFail             (every picture a placeholder)
#   grab.ps1 -Out down.png -Fixture -CatalogDown                (no catalog on the device, none to be had)
#   grab.ps1 -Out offline.png -Fixture -Offline                 (an offline start on the kept catalog)
#   grab.ps1 -Out chip.png -Fixture -Click "<x>,<y>"            (click something first, e.g. a filter chip)
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [string]$Page = 'catalog-page',
    [int]$Exercise = 0,
    [string]$Text = '',
    [int]$Delay = 8000,
    [string]$Click = '',
    [int]$ClickDelay = 5000,
    [string]$Size = '',
    [switch]$Lan,
    [switch]$NewDevice,
    [switch]$CatalogDown,
    [switch]$PicturesFail,
    [int]$Slow = 0,
    [switch]$Fixture,
    [switch]$Offline,
    [string]$Exe = ''
)
$ErrorActionPreference = 'Stop'
$here   = $PSScriptRoot
$src    = Split-Path (Split-Path $here -Parent) -Parent
$repo   = Split-Path $src -Parent
$qt     = if ($env:PRIDE_QT) { $env:PRIDE_QT } else { 'D:\allNewQT6\6.11.1\msvc2022_64' }
# -Exe runs another build (a release package) instead of the test build. PowerShell names are not case-sensitive, so
# $exe below is $Exe itself: whether a package was asked for is kept before it is overwritten.
$packaged = [bool]$Exe
$exe    = if ($Exe) { (Resolve-Path -LiteralPath $Exe).Path } else { Join-Path $src 'build\tests\appPride.exe' }
# A git worktree has no venv of its own, so PRIDE_PYTHON can point at the main checkout's.
$python = if ($env:PRIDE_PYTHON) { $env:PRIDE_PYTHON } else { Join-Path $repo 'server/.venv/Scripts/python.exe' }

# A bare filename has no parent folder, so it lands in the current one.
$outDir = Split-Path $Out -Parent
if (-not $outDir) { $outDir = '.' }
$outFile = (Resolve-Path -LiteralPath $outDir).Path + '\' + (Split-Path $Out -Leaf)
if (Test-Path -LiteralPath $outFile) { Remove-Item -LiteralPath $outFile -Force }

$secrets = Join-Path $env:TEMP 'pride-stub-secrets.json'
# With -Lan the stub is also the home address; it answers /ping, so the app picks it.
$base = 'http://127.0.0.1:5089/api/pride'
$json = if ($Lan) { "{`"apiBase`": `"$base`", `"lanApiBase`": `"$base`"}" } else { "{`"apiBase`": `"$base`"}" }
$json | Set-Content -Encoding ascii $secrets

# A fresh settings folder and data folder each run, so runs don't affect each other or the owner's.
$scratch = Join-Path $env:TEMP ('pride-grab-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force "$scratch\settings", "$scratch\data" | Out-Null

$env:STUB_NEW_DEVICE    = if ($NewDevice) { '1' } else { '' }
$env:STUB_CATALOG_DOWN  = if ($CatalogDown) { '1' } else { '' }
$env:STUB_PICTURES_FAIL = if ($PicturesFail) { '1' } else { '' }
$env:STUB_SLOW          = if ($Slow) { "$Slow" } else { '' }
# Always set, so a STUB_SNAPSHOT left in the caller's shell never changes what a grab serves.
$env:STUB_SNAPSHOT      = if ($Fixture) { Join-Path $here 'fixture' } else { '' }

$stub = $null
try {
    $stub = Start-Process $python -ArgumentList "`"$here\stub_server.py`"" -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 2

    # A package must carry its own Qt: nothing else is put on its PATH, so a missing DLL shows here.
    $env:PATH = if ($packaged) { "$env:SystemRoot\System32;$env:SystemRoot" } else { "$qt\bin;$env:PATH" }
    if ($packaged) {
        foreach ($name in 'QT_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'QML_IMPORT_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH') {
            Set-Item -Path "Env:$name" -Value ''
        }
    }
    $env:PRIDE_SECRETS      = $secrets
    $env:PRIDE_SETTINGS_DIR = "$scratch\settings"
    $env:PRIDE_DATA_DIR     = "$scratch\data"
    # The basic render loop runs QML animations off the clock, so grabs are repeatable.
    $env:QSG_RENDER_LOOP    = 'basic'
    $env:PRIDE_GRAB_SIZE    = $Size

    if ($Offline) {
        # A first run signs in and keeps the catalog (and the pictures it shows), then the stub stops, so the grab is
        # an offline start of the account signed in last.
        $env:PRIDE_START_PAGE     = 'catalog-page'
        $env:PRIDE_START_EXERCISE = ''
        $env:PRIDE_START_TEXT     = ''
        $env:PRIDE_CLICK          = ''
        $env:PRIDE_GRAB           = Join-Path $scratch 'first-run.png'
        $env:PRIDE_GRAB_DELAY     = '6000'
        Start-Process $exe -Wait
        Stop-Process -Id $stub.Id -ErrorAction SilentlyContinue
        $stub = $null
    }

    $env:PRIDE_START_PAGE     = $Page
    $env:PRIDE_START_EXERCISE = if ($Exercise) { "$Exercise" } else { '' }
    $env:PRIDE_START_TEXT     = $Text
    $env:PRIDE_GRAB           = $outFile
    $env:PRIDE_GRAB_DELAY     = "$Delay"
    $env:PRIDE_CLICK          = $Click
    $env:PRIDE_CLICK_DELAY    = "$ClickDelay"
    Start-Process $exe -Wait
} finally {
    if ($stub) { Stop-Process -Id $stub.Id -ErrorAction SilentlyContinue }
    Remove-Item -Recurse -Force $scratch -ErrorAction SilentlyContinue
}
if (-not (Test-Path -LiteralPath $outFile)) {
    throw "The app exited without saving $outFile (did it start? is the build in $exe current?)"
}
Write-Output "Saved $outFile"
