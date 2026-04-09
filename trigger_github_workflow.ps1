$owner   = "edequev-commits"
$repo    = "market-narrative-app"
$workflow= "daily_dashboard.yml"   # nombre exacto del archivo en .github/workflows
$branch  = "main"
$token = $env:MARKET_DASHBOARD_GITHUB_TOKEN

if (-not $token) {
    Write-Host "Falta la variable de entorno MARKET_DASHBOARD_GITHUB_TOKEN"
    exit 1
}

$headers = @{
  Accept = "application/vnd.github+json"
  Authorization = "Bearer $token"
}

$body = @{
  ref = $branch
} | ConvertTo-Json

$url = "https://api.github.com/repos/$owner/$repo/actions/workflows/$workflow/dispatches"

Invoke-RestMethod -Uri $url -Method Post -Headers $headers -Body $body -ContentType "application/json"

Write-Host "Workflow disparado correctamente."