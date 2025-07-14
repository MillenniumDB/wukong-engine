# Parameters
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$DataPath,

    [string]$config
)

# Data Directory
if (-not (Test-Path -Path $DataPath -PathType Container)) {
    Write-Host "[CRITICAL_ERROR] Data directory `"$DataPath`" does not exist."
    exit 1
}
Write-Host "Using data directory: `"$DataPath`""

# Config File
$ConfigFilePath = ".\config\default.toml"
if ($config) {
    $ConfigFilePath = $config
    if (-not (Test-Path -Path $ConfigFilePath -PathType Leaf)) {
        Write-Host "[CRITICAL_ERROR] Configuration file `"$ConfigFilePath`" does not exist."
        exit 1
    }
    Write-Host "Using custom configuration file: `"$ConfigFilePath`""
} else {
    Write-Host "Using default configuration file: `"config/default.toml`""
}

# Env file
if (-not (Test-Path -Path ".env" -PathType Leaf)) {
    Write-Host "[CRITICAL_ERROR] The required `".env`" file for environment variables is not present."
    exit 1
}

# Get absolute paths
$DataDir = (Resolve-Path -Path $DataPath).Path
$ConfigFile = (Resolve-Path -Path $ConfigFilePath).Path

# Run the Docker container
$ImageName = "wukong-engine:latest"
docker run --rm `
    --env-file .env `
    -v "$DataDir:/data" `
    -v "$ConfigFile:/config/config.toml" `
    $ImageName `
    /data --config /config/config.toml

# Exit if the docker command fails
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
Write-Host "Done!"