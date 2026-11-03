param(
    [string]$RunId = (Get-Date -Format 'yyyyMMdd_HHmmss')
)

# Run from a local interactive PowerShell. Never paste the key into a shell command.
# Uses the existing approved campaign ledger: this script does not grant new rights/budget.
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^[A-Za-z0-9_-]+$') {
    throw 'RunId must contain only letters, digits, underscores and hyphens.'
}
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
$approvalPath = Join-Path $projectRoot 'artifacts\phase2\approval.json'
if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path -LiteralPath $approvalPath)) {
    throw 'Existing Python environment and approved Phase 2 permission record are required.'
}
$previousKey = $env:OPENAI_API_KEY
$secretBuffer = [IntPtr]::Zero
$secretValue = $null
Push-Location -LiteralPath $projectRoot
try {
    # Fully offline permission/manifest validation happens before asking for a credential.
    $preflightJson = & $pythonPath -m vidoclens teacher run artifacts/phase2/api_plan_v1 unused_dry_run_output `
        --permission artifacts/phase2/approval.json --dry-run
    if ($LASTEXITCODE -ne 0) { throw 'Preflight failed.' }
    $preflight = $preflightJson | ConvertFrom-Json
    if (@($preflight.blockers).Count -gt 0) { throw 'Permission gate is still blocked.' }
    Write-Output $preflightJson
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) {
        $secretValue = Read-Host 'OpenAI API key (hidden; process memory only)' -AsSecureString
        $secretBuffer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secretValue)
        $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretBuffer)
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretBuffer)
        $secretBuffer = [IntPtr]::Zero
        $secretValue.Dispose()
        $secretValue = $null
    }
    if ([string]::IsNullOrWhiteSpace($env:OPENAI_API_KEY)) { throw 'API key was empty.' }
    $runDirectories = @()
    foreach ($experiment in @('pilot', 'A1', 'A2', 'A3', 'A5')) {
        $runDirectory = "artifacts/phase2/live_${RunId}_${experiment}"
        & $pythonPath -m vidoclens teacher run artifacts/phase2/api_plan_v1 $runDirectory `
            --experiment $experiment --permission artifacts/phase2/approval.json
        if ($LASTEXITCODE -ne 0) { throw "Experiment $experiment stopped; keep its evidence and ledger." }
        $runDirectories += $runDirectory
    }
    $evaluationPath = "artifacts/phase2/evaluation_${RunId}.json"
    & $pythonPath -m vidoclens teacher evaluate artifacts/phase2/api_plan_v1 @runDirectories $evaluationPath
    if ($LASTEXITCODE -ne 0) { throw 'Evaluation failed; preserve the original runs.' }
    foreach ($experiment in @('pilot', 'A1', 'A2', 'A3', 'A5')) {
        & $pythonPath -m vidoclens teacher run artifacts/phase2/api_plan_v1 `
            "artifacts/phase2/replay_${RunId}_${experiment}" --experiment $experiment `
            --permission artifacts/phase2/approval.json
        if ($LASTEXITCODE -ne 0) { throw 'Cache replay failed; review before any new submission.' }
    }
    Write-Output "Runs and evaluation saved at $evaluationPath. Review/freeze is still required for G2."
}
finally {
    $env:OPENAI_API_KEY = $previousKey
    $previousKey = $null
    if ($secretBuffer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretBuffer)
    }
    if ($null -ne $secretValue) { $secretValue.Dispose() }
    Pop-Location
}
