param([switch]$WhatIf)

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$relativeTargets = @(
    "jchatmind/target",
    "ui/dist",
    "rag-mcp/.pytest_cache",
    "rag-mcp/.tmp",
    "rag-mcp/logs",
    "rag-mcp/output",
    "rag-mcp/data/db",
    "scripts/__pycache__"
)

foreach ($relativeTarget in $relativeTargets) {
    $candidate = Join-Path $repoRoot $relativeTarget
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $resolved = (Resolve-Path -LiteralPath $candidate).Path
    if (-not $resolved.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to remove path outside repository: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -WhatIf:$WhatIf
}

$cacheDirs = @(Get-ChildItem -LiteralPath $repoRoot -Directory -Recurse -Filter __pycache__)
$cacheDirs | Sort-Object FullName -Descending |
    ForEach-Object {
        if ($_.FullName.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar)) {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -WhatIf:$WhatIf
        }
    }
