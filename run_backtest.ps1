$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = $env:PYTHON
if (-not $python) {
    $candidates = @(
        (Join-Path $root ".venv\Scripts\python.exe"),
        (Join-Path $root "..\SkyQ_Scan\.venv\Scripts\python.exe"),
        (Join-Path $root "..\.venv_databento\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            $python = $candidate
            break
        }
    }
}
if (-not $python) {
    $python = "python"
}

& $python "scripts\run_backtest.py" @args
exit $LASTEXITCODE
