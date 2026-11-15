# The pre-push check (spec §10): this repository is public, so nothing that names the owner's machines or opens them
# may be pushed. It reads every tracked file and every commit about to be pushed (messages, authors and the lines they
# add) and fails on: private network addresses, logins (a name, an at sign, a machine) and emails other than the
# no-reply ones, token-shaped
# strings, URLs to hosts not listed below, files named .env or secrets.json, and the owner's own words in the
# git-ignored tools/check-public.local.txt (their domain and host names, which this repository must never hold).
#   check-public.ps1                 the tree, and the commits not yet on the remote branch
#   check-public.ps1 -Range A..B     the tree, and the commits in that range
param([string]$Range = '')
$ErrorActionPreference = 'Stop'
$root = (git -C $PSScriptRoot rev-parse --show-toplevel).Trim()
Set-Location $root

$allowedEmails = @('118999043+snowie-ctrl@users.noreply.github.com', 'noreply@anthropic.com')
# Hosts a URL may name: the loopback, the placeholders the copied tests use, the public sources Pride credits, and
# the SVG namespace.
$allowedHosts = @('localhost', '127.0.0.1', 'example.test', 'api.example', 'home.lan',
                  'github.com', 'raw.githubusercontent.com', 'fonts.google.com', 'fonts.googleapis.com',
                  'openfontlicense.org', 'scripts.sil.org', 'claude.com', 'unlicense.org', 'www.qt.io',
                  'www.w3.org')
$allowFile = Join-Path $root 'tools\check-public.allow'
$allowed = if (Test-Path $allowFile) { @(Get-Content $allowFile | Where-Object { $_.Trim() -and -not $_.StartsWith('#') } | ForEach-Object { $_.Trim() }) } else { @() }
$localFile = Join-Path $root 'tools\check-public.local.txt'
$localWords = if (Test-Path $localFile) { @(Get-Content $localFile | Where-Object { $_.Trim() -and -not $_.StartsWith('#') } | ForEach-Object { $_.Trim() }) } else { @() }

$rules = @(
    @{ Name = 'private address'; Pattern = '\b(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b' },
    @{ Name = 'login or email'; Pattern = '[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*' },
    @{ Name = 'token-shaped'; Pattern = '\b[0-9a-fA-F]{32,}\b' },
    @{ Name = 'token-shaped'; Pattern = '[A-Za-z0-9+/_-]{32,}={0,2}' },
    @{ Name = 'unlisted host'; Pattern = 'https?://([A-Za-z0-9.-]+)' }
)

$hits = New-Object System.Collections.Generic.List[string]

function Mask([string]$text) {
    if ($text.Length -le 6) { return $text.Substring(0, [Math]::Min(2, $text.Length)) + '...' }
    return $text.Substring(0, 4) + '...(' + $text.Length + ' chars)'
}

function Test-Line([string]$where, [string]$line) {
    foreach ($rule in $rules) {
        foreach ($m in [regex]::Matches($line, $rule.Pattern)) {
            $value = $m.Value
            if ($allowed -contains $value) { continue }
            # (if/elseif rather than switch: a continue inside a switch only leaves the switch.)
            if ($rule.Name -eq 'login or email') {
                if ($allowedEmails -contains $value) { continue }
                # A decorator or an at-rule is not a login: something must stand on both sides of the @.
                if ($m.Index -gt 0 -and $line[$m.Index - 1] -eq '@') { continue }
            } elseif ($rule.Name -eq 'token-shaped') {
                # Long identifiers (test names, paths) are words, not tokens: a token mixes digits with letters of
                # both cases, or is a long run of hex.
                if ($value -notmatch '^[0-9a-fA-F]+$') {
                    if (-not ($value -cmatch '[a-z]' -and $value -cmatch '[A-Z]' -and $value -match '[0-9]')) { continue }
                }
            } elseif ($rule.Name -eq 'unlisted host') {
                $hostName = $m.Groups[1].Value.ToLower().TrimEnd('.')
                if ($allowedHosts -contains $hostName) { continue }
                # Names reserved for examples and tests (RFC 2606 and 6761) are never anyone's machine.
                if ($hostName -match '(^|\.)(test|example|invalid|localhost)$') { continue }
                $value = $hostName
            }
            $hits.Add("${where}: $($rule.Name): $(Mask $value)")
        }
    }
    foreach ($word in $localWords) {
        if ($line.IndexOf($word, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
            $hits.Add("${where}: local private word: $(Mask $word)")
        }
    }
}

# ---- The tree ----
foreach ($path in (git ls-files)) {
    $leaf = Split-Path $path -Leaf
    if ($leaf -eq '.env' -or $leaf -eq 'secrets.json' -or $leaf -eq 'prideAdminConfig.json') {
        $hits.Add("${path}: forbidden file: $leaf")
        continue
    }
    $full = Join-Path $root $path
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { continue }
    $bytes = [IO.File]::ReadAllBytes($full)
    # Binary files (pictures, fonts, the icon) are skipped: a NUL in the first 8000 bytes, as git decides.
    if ([Array]::IndexOf($bytes[0..([Math]::Min($bytes.Length, 8000) - 1)], [byte]0) -ge 0) { continue }
    $n = 0
    foreach ($line in [Text.Encoding]::UTF8.GetString($bytes) -split "`n") {
        $n++
        Test-Line "${path}:$n" $line
    }
}

# ---- The commits about to be pushed ----
if (-not $Range) {
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    $upstream = "origin/$branch"
    git rev-parse --verify -q $upstream *> $null
    if ($LASTEXITCODE -ne 0) { $upstream = 'origin/main' }
    git rev-parse --verify -q $upstream *> $null
    $Range = if ($LASTEXITCODE -eq 0) { "$upstream..HEAD" } else { 'HEAD' }
}
$commits = @(git rev-list $Range)
foreach ($commit in $commits) {
    $short = $commit.Substring(0, 7)
    foreach ($email in @((git show -s --format='%ae' $commit), (git show -s --format='%ce' $commit))) {
        if ($allowedEmails -notcontains $email.Trim()) { $hits.Add("commit ${short}: commit email: $(Mask $email.Trim())") }
    }
    foreach ($line in (git show -s --format='%B' $commit)) { Test-Line "commit $short message" $line }
    foreach ($line in (git show --format= --no-color --unified=0 $commit)) {
        if ($line.StartsWith('+') -and -not $line.StartsWith('+++')) { Test-Line "commit $short" $line.Substring(1) }
        if ($line -match '^\+\+\+ b/(.*)$') {
            $leaf = Split-Path $Matches[1] -Leaf
            if ($leaf -eq '.env' -or $leaf -eq 'secrets.json' -or $leaf -eq 'prideAdminConfig.json') {
                $hits.Add("commit ${short}: forbidden file: $leaf")
            }
        }
    }
}

if ($hits.Count -eq 0) {
    Write-Output 'clean'
    exit 0
}
$hits | Sort-Object -Unique | ForEach-Object { Write-Output $_ }
Write-Output "$($hits.Count) hit(s): nothing may be pushed until the owner has looked."
exit 1
