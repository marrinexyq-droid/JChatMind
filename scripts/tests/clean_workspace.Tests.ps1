$ErrorActionPreference = "Stop"

$sourceScript = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..\clean_workspace.ps1")).Path
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
)
$fixtureRoot = Join-Path $tempRoot ("jchatmind-clean-workspace-test-" + [guid]::NewGuid())

try {
    $fixtureScriptDir = New-Item -ItemType Directory -Force -Path (Join-Path $fixtureRoot "scripts")
    Copy-Item -LiteralPath $sourceScript -Destination (Join-Path $fixtureScriptDir.FullName "clean_workspace.ps1")

    $protectedCaches = @(
        ".github/skills/tooling/__pycache__",
        "rag-mcp/.venv/Lib/site-packages/example/__pycache__",
        "rag-mcp/.deps/vendor/example/__pycache__"
    )
    $ordinaryCaches = @(
        "src/example/__pycache__",
        ".github/skills-extra/tooling/__pycache__",
        "rag-mcp/.venv-extra/example/__pycache__",
        "rag-mcp/.deps-extra/example/__pycache__"
    )

    foreach ($relativeCache in $protectedCaches + $ordinaryCaches) {
        $cachePath = Join-Path $fixtureRoot $relativeCache
        New-Item -ItemType Directory -Force -Path $cachePath | Out-Null
        Set-Content -LiteralPath (Join-Path $cachePath "sentinel.txt") -Value $relativeCache
    }

    $fixtureScript = Join-Path $fixtureScriptDir.FullName "clean_workspace.ps1"
    & $fixtureScript -WhatIf

    foreach ($relativeCache in $protectedCaches + $ordinaryCaches) {
        if (-not (Test-Path -LiteralPath (Join-Path $fixtureRoot $relativeCache))) {
            throw "-WhatIf removed fixture cache: $relativeCache"
        }
    }

    & $fixtureScript

    foreach ($relativeCache in $protectedCaches) {
        if (-not (Test-Path -LiteralPath (Join-Path $fixtureRoot $relativeCache))) {
            throw "Protected cache was removed: $relativeCache"
        }
    }
    foreach ($relativeCache in $ordinaryCaches) {
        if (Test-Path -LiteralPath (Join-Path $fixtureRoot $relativeCache)) {
            throw "Ordinary cache was not removed: $relativeCache"
        }
    }

    Write-Output "PASS: WhatIf preserved all fixtures"
    Write-Output "PASS: protected __pycache__ directories preserved=$($protectedCaches.Count)"
    Write-Output "PASS: ordinary __pycache__ directories removed=$($ordinaryCaches.Count)"
}
finally {
    if (Test-Path -LiteralPath $fixtureRoot) {
        $resolvedFixture = (Resolve-Path -LiteralPath $fixtureRoot).Path
        $isSafeFixture =
            $resolvedFixture.StartsWith(
                $tempRoot + [IO.Path]::DirectorySeparatorChar,
                [StringComparison]::OrdinalIgnoreCase
            ) -and
            ([IO.Path]::GetFileName($resolvedFixture)).StartsWith(
                "jchatmind-clean-workspace-test-",
                [StringComparison]::Ordinal
            )
        if (-not $isSafeFixture) {
            throw "Refusing to remove unsafe test fixture: $resolvedFixture"
        }
        Remove-Item -LiteralPath $resolvedFixture -Recurse -Force
    }
}
