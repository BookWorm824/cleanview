# CleanView installer (Windows 10/11). Run via "Install CleanView.bat".
# Installs into %LOCALAPPDATA%\CleanView. No admin rights needed.
# CleanView is fully separate from CleanListen; if CleanListen is installed,
# its speech model and ffmpeg are copied (not shared) to skip re-downloading.
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Root   = Join-Path $env:LOCALAPPDATA 'CleanView'
$AppDir = Join-Path $Root 'app'
$Venv   = Join-Path $Root 'venv'
$Tmp    = Join-Path $Root 'downloads'
$CL     = Join-Path $env:LOCALAPPDATA 'CleanListen\app'
$ModelName = 'sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8'
$ModelUrl  = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$ModelName.tar.bz2"
$FfmpegUrl = 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'
$PyInstallerUrl = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe'

function Step($n, $text) { Write-Host ""; Write-Host "[$n/6] $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "      $text" -ForegroundColor Green }
function Fail($text) { throw $text }

function Download($url, $dest) {
    # curl.exe ships with Windows 10+ and is much faster than Invoke-WebRequest
    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    if (Test-Path $curl) {
        & $curl -L --fail --retry 3 -o $dest $url
        if ($LASTEXITCODE -ne 0) { Fail "Download failed: $url" }
    } else {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
    }
}

function Find-Python {
    # A Python 3.11-3.13 that includes tkinter (the window toolkit)
    $check = 'import sys, tkinter; print(sys.executable)'
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        foreach ($v in '3.12', '3.13', '3.11') {
            try {
                $exe = (& py "-$v" -c $check 2>$null | Select-Object -Last 1)
                if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe)) { return $exe.Trim() }
            } catch {}
        }
    }
    foreach ($v in '312', '313', '311') {
        $exe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v\python.exe"
        if (Test-Path $exe) {
            try {
                & $exe -c $check *> $null
                if ($LASTEXITCODE -eq 0) { return $exe }
            } catch {}
        }
    }
    return $null
}

try {
    Write-Host "CleanView setup" -ForegroundColor White
    Write-Host "This takes 5-15 minutes. Leave this window open."
    if (-not (Test-Path (Join-Path $PSScriptRoot 'app\CleanView.pyw'))) {
        Fail "Setup files are missing. Right-click the zip, choose 'Extract All', and run setup from the extracted folder."
    }
    New-Item -ItemType Directory -Force -Path $Root, $AppDir, $Tmp | Out-Null

    # 1. app files
    Step 1 "Copying CleanView..."
    Copy-Item -Path (Join-Path $PSScriptRoot 'app\*') -Destination $AppDir -Recurse -Force
    Ok "Done"

    # 2. Python
    Step 2 "Checking for Python..."
    $python = Find-Python
    if (-not $python) {
        Write-Host "      Python not found - installing Python 3.12 (just for you, no admin needed)..."
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            & winget install -e --id Python.Python.3.12 --scope user --silent `
                --accept-package-agreements --accept-source-agreements | Out-Host
            $python = Find-Python
        }
        if (-not $python) {
            $inst = Join-Path $Tmp 'python-installer.exe'
            Download $PyInstallerUrl $inst
            Start-Process -FilePath $inst -Wait -ArgumentList `
                '/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'Include_tcltk=1', `
                'Include_launcher=1', 'Include_test=0', 'Shortcuts=0'
            $python = Find-Python
        }
        if (-not $python) { Fail "Couldn't install Python automatically. Install Python 3.12 from python.org, then run this setup again." }
    }
    Ok "Using $python"

    # 3. CleanView's own Python environment + libraries
    Step 3 "Installing the speech and picture libraries..."
    if (-not (Test-Path (Join-Path $Venv 'Scripts\python.exe'))) {
        & $python -m venv $Venv
        if ($LASTEXITCODE -ne 0) { Fail "Couldn't create the Python environment." }
    }
    $vpy = Join-Path $Venv 'Scripts\python.exe'
    & $vpy -m pip install --upgrade pip --quiet --disable-pip-version-check
    & $vpy -m pip install --quiet --disable-pip-version-check sherpa-onnx numpy onnxruntime tokenizers subliminal
    if ($LASTEXITCODE -ne 0) { Fail "Installing libraries failed. Check your internet connection and run setup again." }
    # Smart App Control can block chardet's compiled parts; use the plain-Python versions
    $pv = (& $vpy -c "import sys; print('%d.%d' % sys.version_info[:2])").Trim()
    $pure = Join-Path $env:TEMP 'cleanview_pure'
    Remove-Item $pure -Recurse -Force -ErrorAction SilentlyContinue
    & $vpy -m pip download --quiet --disable-pip-version-check --no-deps --only-binary=:all: --platform any --python-version $pv -d $pure chardet charset-normalizer
    $wheels = @(Get-ChildItem $pure -Filter *.whl -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
    if ($wheels.Count -gt 0) { & $vpy -m pip install --quiet --disable-pip-version-check --no-deps --force-reinstall @wheels }
    & $vpy -m pip install --quiet --disable-pip-version-check --no-deps nudenet
    if ($LASTEXITCODE -ne 0) { Fail "Installing the picture checker failed. Check your internet connection and run setup again." }
    & $vpy -c "import sherpa_onnx, numpy, tkinter, tokenizers, onnxruntime"
    if ($LASTEXITCODE -ne 0) { Fail "Libraries installed but won't load." }
    Ok "Done"

    # 4. ffmpeg (reads and writes the video files)
    Step 4 "Getting the video tools (ffmpeg)..."
    $bin = Join-Path $AppDir 'bin'
    New-Item -ItemType Directory -Force -Path $bin | Out-Null
    if (-not (Test-Path (Join-Path $bin 'ffmpeg.exe'))) {
        $clbin = Join-Path $CL 'bin'
        if ((Test-Path (Join-Path $clbin 'ffmpeg.exe')) -and (Test-Path (Join-Path $clbin 'ffprobe.exe'))) {
            Copy-Item (Join-Path $clbin 'ffmpeg.exe'), (Join-Path $clbin 'ffprobe.exe') $bin -Force
            Ok "Copied from CleanListen"
        } else {
            $zip = Join-Path $Tmp 'ffmpeg.zip'
            Download $FfmpegUrl $zip
            $x = Join-Path $Tmp 'ffmpeg'
            if (Test-Path $x) { Remove-Item $x -Recurse -Force }
            Expand-Archive -Path $zip -DestinationPath $x -Force
            foreach ($exe in 'ffmpeg.exe', 'ffprobe.exe') {
                $f = Get-ChildItem -Path $x -Recurse -Filter $exe | Select-Object -First 1
                if (-not $f) { Fail "ffmpeg download looked wrong (no $exe)." }
                Copy-Item $f.FullName $bin -Force
            }
            Remove-Item $x -Recurse -Force
            Remove-Item $zip -Force
            Ok "Done"
        }
    } else { Ok "Already there" }

    # 5. speech model
    Step 5 "Getting the speech model (about 650 MB)..."
    $models = Join-Path $AppDir 'models'
    $mdir = Join-Path $models $ModelName
    New-Item -ItemType Directory -Force -Path $models | Out-Null
    if (-not (Test-Path (Join-Path $mdir 'tokens.txt'))) {
        $clm = Join-Path $CL "models\$ModelName"
        if (Test-Path (Join-Path $clm 'tokens.txt')) {
            Copy-Item $clm $models -Recurse -Force
            Ok "Copied from CleanListen"
        } else {
            $tar = Join-Path $Tmp "$ModelName.tar.bz2"
            Download $ModelUrl $tar
            & tar.exe -xjf $tar -C $models
            if ($LASTEXITCODE -ne 0 -or -not (Test-Path (Join-Path $mdir 'tokens.txt'))) { Fail "Unpacking the speech model failed. Run setup again." }
            Remove-Item $tar -Force
            Ok "Done"
        }
    } else { Ok "Already there" }

    # 6. icon on the desktop and in the Start menu
    Step 6 "Adding the CleanView icon..."
    $pyw = Join-Path $Venv 'Scripts\pythonw.exe'
    $launcher = Join-Path $AppDir 'launcher.pyw'
    $s = New-Object -ComObject WScript.Shell
    foreach ($dir in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))) {
        if (-not $dir) { continue }
        $l = $s.CreateShortcut((Join-Path $dir 'CleanView.lnk'))
        $l.TargetPath = $pyw
        $l.Arguments = '"' + $launcher + '"'
        $l.WorkingDirectory = $AppDir
        $l.IconLocation = (Join-Path $AppDir 'cleanview.ico')
        $l.Description = 'Clean up movies and TV shows'
        $l.Save()
    }
    Ok "On your desktop and in the Start menu"

    Write-Host ""
    Write-Host "All done! Opening CleanView..." -ForegroundColor Green
    Start-Process -FilePath $pyw -ArgumentList ('"' + $launcher + '"') -WorkingDirectory $AppDir
}
catch {
    Write-Host ""
    Write-Host "Setup stopped: $_" -ForegroundColor Red
    Write-Host "Send a screenshot of this window if you need help."
}
