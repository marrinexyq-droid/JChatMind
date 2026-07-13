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
$protectedRoots = @(
    (Join-Path $repoRoot ".github/skills"),
    (Join-Path $repoRoot "rag-mcp/.venv"),
    (Join-Path $repoRoot "rag-mcp/.deps")
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
        $cachePath = $_.FullName
        $isProtected = $protectedRoots | Where-Object {
            $cachePath.Equals($_, [StringComparison]::OrdinalIgnoreCase) -or
            $cachePath.StartsWith(
                $_ + [IO.Path]::DirectorySeparatorChar,
                [StringComparison]::OrdinalIgnoreCase
            )
        }
        if (
            $cachePath.StartsWith($repoRoot + [IO.Path]::DirectorySeparatorChar) -and
            -not $isProtected
        ) {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -WhatIf:$WhatIf
        }
    }
