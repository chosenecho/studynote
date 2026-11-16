# Run uv through the local proxy.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/dev/uv.ps1 lock
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/dev/uv.ps1 sync
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/dev/uv.ps1 run mkdocs build --strict
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools/dev/uv.ps1 -Proxy http://127.0.0.1:7890 sync
#
# Default proxy is FlClash's mixed port 10808 (accepts plain HTTP CONNECT).
# The index is pinned to official PyPI: domestic mirrors lack
# pymdown-extensions 11.0.1, which the site needs.

$ErrorActionPreference = 'Stop'

$proxy = 'http://127.0.0.1:10808'
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

$env:HTTP_PROXY = $proxy
$env:HTTPS_PROXY = $proxy
$env:ALL_PROXY = $proxy
$env:UV_DEFAULT_INDEX = 'https://pypi.org/simple'
$env:UV_HTTP_TIMEOUT = '120'

& uv @rest
exit $LASTEXITCODE
