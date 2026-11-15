# Copied from Gluttony app/tests/build.ps1 at c1ed705; changes: PRIDE_ names.
# Configures and builds the test build (Debug, tests on) from a plain shell.
# Paths default to the owner's machine; override with PRIDE_QT / PRIDE_QT_TOOLS / PRIDE_VCVARS.
$ErrorActionPreference = 'Stop'
$qt     = if ($env:PRIDE_QT)       { $env:PRIDE_QT }       else { 'D:\allNewQT6\6.11.1\msvc2022_64' }
$tools  = if ($env:PRIDE_QT_TOOLS) { $env:PRIDE_QT_TOOLS } else { 'D:\allNewQT6\Tools' }
$vcvars = if ($env:PRIDE_VCVARS)   { $env:PRIDE_VCVARS }   else { 'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat' }
$src    = Split-Path $PSScriptRoot -Parent
$build  = Join-Path $src 'build\tests'

$env:PATH = "$tools\CMake_64\bin;$tools\Ninja;$qt\bin;$env:PATH"
cmd /c "`"$vcvars`" >nul && cmake -S `"$src`" -B `"$build`" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DCMAKE_PREFIX_PATH=$qt -DPRIDE_BUILD_TESTS=ON && cmake --build `"$build`""
exit $LASTEXITCODE