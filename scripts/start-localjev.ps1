param(
    [string]$LocalJevPath = (Join-Path $env:USERPROFILE '.cache/grid-project/localjev')
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath (Join-Path $LocalJevPath 'src/index.ts'))) {
    throw 'LocalJev checkout is missing.'
}
$settings = @{
    LOCALJEV_UPSTREAM = 'http://127.0.0.1:11434'
    LOCALJEV_UPSTREAM_MODEL = 'qwen2.5:7b-instruct'
    LOCALJEV_HOST = '127.0.0.1'
    LOCALJEV_PORT = '18080'
    LOCALJEV_UPSTREAM_API_KEY = ''
    LOCALJEV_API_KEY = ''
    LOCALJEV_TIMEOUT = '45'
}
$previous = @{}
foreach ($name in $settings.Keys) {
    $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    [Environment]::SetEnvironmentVariable($name, $settings[$name], 'Process')
}
Push-Location -LiteralPath $LocalJevPath
try {
    # Foreground on purpose: the user owns this terminal and stops it with Ctrl+C.
    & bun run src/index.ts
} finally {
    Pop-Location
    foreach ($name in $previous.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process')
    }
}
