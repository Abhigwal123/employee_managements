# === CONFIG ===
$serverUser = "root"
$serverIP   = "82.165.209.92"
$serverRoot = "/var/www/Project_Up"

Write-Host "=== Smart Scheduling - Backend Docker Refactor Upload ===" -ForegroundColor Cyan
$localRoot = (Get-Location).Path

function Get-RelativePath($fullPath, $rootPath) {
    $rel = $fullPath.Substring($rootPath.Length).TrimStart('\')
    return $rel -replace '\\','/'
}

function Upload-File($localPath) {
    if (-not (Test-Path $localPath)) {
        Write-Host "Skipping (not found): $localPath" -ForegroundColor Yellow
        return
    }

    $full = (Resolve-Path $localPath).Path
    $rel  = Get-RelativePath $full $localRoot
    $remotePath = "$serverRoot/$rel"
    $remoteDir  = $remotePath.Substring(0, $remotePath.LastIndexOf("/"))

    Write-Host "-> $rel" -ForegroundColor Green

    ssh "$serverUser@$serverIP" "mkdir -p '$remoteDir'"

    # FINAL, VERIFIED, POWERSHELL-SAFE VERSION
    scp "$full" "$($serverUser)@${serverIP}:$remotePath"
}



Write-Host "`n[1/4] Uploading Docker & Compose files..." -ForegroundColor Cyan
Upload-File "backend\Dockerfile"
Upload-File "docker-compose.yml"
Upload-File "docker-compose.prod.yml"

Write-Host "`n[2/4] Uploading backend root Python files..." -ForegroundColor Cyan
Get-ChildItem "backend" -File -Filter *.py | ForEach-Object {
    Upload-File $_.FullName
}

Write-Host "`n[3/4] Uploading alembic env.py..." -ForegroundColor Cyan
Upload-File "backend\alembic\env.py"

Write-Host "`n[4/4] Uploading backend app Python files..." -ForegroundColor Cyan
Get-ChildItem "backend\app" -Recurse -File -Filter *.py | ForEach-Object {
    Upload-File $_.FullName
}

Write-Host "`n=== Upload Complete ===" -ForegroundColor Cyan
Write-Host "Run on server: cd /var/www/Project_Up && docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build" -ForegroundColor Magenta
