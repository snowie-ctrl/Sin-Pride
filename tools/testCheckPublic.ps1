# Tests tools/check-public.ps1 against a scratch repository: a clean tree passes, and each kind of leak is caught,
# in the tree and in a commit about to be pushed. Planted values are put together at run time, so this file never
# holds one whole and the check stays clean on it.
$ErrorActionPreference = 'Stop'
$check = Join-Path $PSScriptRoot 'check-public.ps1'
$failures = 0

function New-Scratch {
    $dir = Join-Path $env:TEMP ('pride-checkpublic-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory $dir | Out-Null
    git -C $dir init -q -b main
    git -C $dir config user.email '118999043+snowie-ctrl@users.noreply.github.com'
    git -C $dir config user.name 'snowie-ctrl'
    New-Item -ItemType Directory "$dir\tools" | Out-Null
    Copy-Item $check "$dir\tools\check-public.ps1"
    Set-Content -Encoding utf8 "$dir\tools\check-public.allow" 'f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5'
    Set-Content -Encoding utf8 "$dir\README.md" "# Scratch`nSee https://github.com/yuhonas/free-exercise-db at f00c92c7dcf1216a928a52c3706c7ce8e2f71ed5."
    git -C $dir add -A
    git -C $dir commit -q -m 'start'
    return $dir
}

function Expect([string]$name, [string]$dir, [int]$code, [string]$mention = '') {
    $out = & powershell -NoProfile -File "$dir\tools\check-public.ps1" -Range 'HEAD' 2>&1 | Out-String
    $got = $LASTEXITCODE
    if ($got -ne $code -or ($mention -and $out -notmatch [regex]::Escape($mention))) {
        Write-Output "FAIL ${name}: exit $got (wanted $code)`n$out"
        $script:failures++
    } else {
        Write-Output "ok   $name"
    }
}

function Plant([string]$file, [string]$text) {
    $dir = New-Scratch
    Set-Content -Encoding utf8 (Join-Path $dir $file) $text
    git -C $dir add -A
    git -C $dir commit -q -m 'planted'
    return $dir
}

$ip     = '192.' + '168.1.20'
$login  = 'admin' + '@' + 'boxname'
$email  = 'someone' + '@' + 'mail.test'
$hex    = ('ab12' * 16)
$b64    = 'Zm9v' + 'QmFy' + 'MTIzNDU2Nzg5MGFiY2RlZkFCQ0RFRg' + 'Xy9pZ2h0'
$url    = 'https://' + 'my-home-server' + '.example.org/api'

Expect 'a clean tree passes' (New-Scratch) 0 'clean'
Expect 'a private address is caught' (Plant 'notes.txt' "server at $ip") 1 'private address'
Expect 'a login is caught' (Plant 'notes.txt' "ssh $login") 1 'login or email'
Expect 'an email is caught' (Plant 'notes.txt' "mail $email") 1 'login or email'
Expect 'a long hex token is caught' (Plant 'notes.txt' "token = $hex") 1 'token-shaped'
Expect 'a base64 token is caught' (Plant 'notes.txt' "key: $b64") 1 'token-shaped'
Expect 'an unknown host is caught' (Plant 'notes.txt' "see $url") 1 'unlisted host'
Expect 'a .env file is caught' (Plant '.env' 'PUBLISH=dry') 1 'forbidden file'
Expect 'a secrets.json is caught' (Plant 'secrets.json' '{}') 1 'forbidden file'

# A local word (the owner's own domain) is caught although the repository never holds the list.
$dir = Plant 'notes.txt' ('through the ' + 'castle' + 'gate tunnel')
Set-Content -Encoding utf8 "$dir\tools\check-public.local.txt" ('castle' + 'gate')
Expect 'a local private word is caught' $dir 1 'local private word'

# A leak removed in a later commit is still in the history about to be pushed.
$dir = Plant 'notes.txt' "server at $ip"
Set-Content -Encoding utf8 "$dir\notes.txt" 'nothing here'
git -C $dir commit -q -am 'removed it'
Expect 'a leak only in the pushed history is caught' $dir 1 'private address'

# A commit made under another email is caught.
$dir = New-Scratch
git -C $dir -c user.email=$email commit -q --allow-empty -m 'other author'
Expect 'a commit email is caught' $dir 1 'commit email'

# What is allowed: localhost, the loopback, the example hosts the copied tests use, the no-reply emails.
$dir = Plant 'ok.txt' ("http://127.0.0.1:5089/api/pride http://localhost/x https://api.example/api/pride " +
                        "http://home.lan:5000/api/pride http://example.test/api/pride http://admin.example.test:5000/x " +
                        "Co-Authored-By: Claude <noreply" + "@anthropic.com> " +
                        "a test_name_thatIsLongButHasNoDigitsAtAllInIt")
Expect 'allowed things pass' $dir 0 'clean'

if ($failures -gt 0) { Write-Output "$failures failed"; exit 1 }
Write-Output 'all passed'
exit 0
