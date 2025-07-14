# Build the Docker image
$ImageName = "wukong-engine:latest"
Write-Host "Building Docker image: '$ImageName'"
docker build -t $ImageName .
Write-Host "Docker image '$ImageName' built successfully!"