# Run uv, optionally through a proxy.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/dev/uv.ps1 sync --locked
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/dev/uv.ps1 lock
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/dev/uv.ps1 -Proxy http://127.0.0.1:7890 sync
#
# The proxy is optional: pass -Proxy to inject HTTP(S)_PROXY / ALL_PROXY for this
# run. Without it, uv uses whatever the environment already provides, so CI and
# other machines never depend on a fixed local port. The index stays pinned to
# official PyPI for this process only (the committed uv.lock is resolved against
# it): domestic mirrors lack pymdown-extensions 11.0.1, and an ambient
# UV_DEFAULT_INDEX pointing at a mirror would otherwise make --locked report a
# stale lockfile.

$ErrorActionPreference = 'Stop'

$proxy = $null
$rest = New-Object System.Collections.Generic.List[string]
$i = 0
while ($i -lt $args.Count) {
    if ($args[$i] -eq '-Proxy' -and ($i + 1) -lt $args.Count) {
        $proxy = $args[$i + 1]
        $i += 2
    } else {
        $rest.Add($args[$i])
        $i += 1
    }
}

if ($proxy) {
    $env:HTTP_PROXY = $proxy
    $env:HTTPS_PROXY = $proxy
    $env:ALL_PROXY = $proxy
}
$env:UV_DEFAULT_INDEX = 'https://pypi.org/simple'
& uv @rest
exit $LASTEXITCODE
