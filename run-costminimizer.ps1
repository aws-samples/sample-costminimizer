# Base docker run command with common parameters
$DockerBaseCmd = "docker run -it -v $HOME/.aws:/root/.aws -v $HOME/cow:/root/cow -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN costminimizer"

# Function to display menu and get user choice
function Show-Menu {
    Clear-Host
    Write-Host "=== CostMinimizer Docker Menu ===" -ForegroundColor Cyan
    Write-Host "1. Run CostExplorer (--ce)"
    Write-Host "2. Run ComputeOptimizer (--co)"
    Write-Host "3. Run Trusted Advisor (--ta)"
    Write-Host "4. Run CUR Reports (--cur)"
    Write-Host "5. Configure CostMinimizer (--configure)"
    Write-Host "6. Open bash shell in container"
    Write-Host "7. Run with S3 bucket storage"
    Write-Host "0. Exit"
    Write-Host "=================================" -ForegroundColor Cyan
    
    $choice = Read-Host "Enter your choice [0-7]"
    return $choice
}

# Main loop
while ($true) {
    $choice = Show-Menu
    
    switch ($choice) {
        "1" {
            Write-Host "Running CostExplorer..." -ForegroundColor Green
            Invoke-Expression "$DockerBaseCmd --ce"
            Read-Host "Press Enter to continue..."
        }
        "2" {
            Write-Host "Running ComputeOptimizer..." -ForegroundColor Green
            Invoke-Expression "$DockerBaseCmd --co"
            Read-Host "Press Enter to continue..."
        }
        "3" {
            Write-Host "Running Trusted Advisor..." -ForegroundColor Green
            Invoke-Expression "$DockerBaseCmd --ta"
            Read-Host "Press Enter to continue..."
        }
        "4" {
            Write-Host "Running CUR Reports..." -ForegroundColor Green
            $curDb = Read-Host "Enter CUR database name"
            $curTable = Read-Host "Enter CUR table name"
            Invoke-Expression "$DockerBaseCmd --cur --cur-db $curDb --cur-table $curTable"
            Read-Host "Press Enter to continue..."
        }
        "5" {
            Write-Host "Configuring CostMinimizer..." -ForegroundColor Green
            Invoke-Expression "$DockerBaseCmd --configure --auto-update-conf"
            Read-Host "Press Enter to continue..."
        }
        "6" {
            Write-Host "Opening bash shell in container..." -ForegroundColor Green
            Invoke-Expression "docker run -it -v $HOME/.aws:/root/.aws -v $HOME/cow:/root/cow -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN --entrypoint /bin/bash costminimizer"
        }
        "7" {
            Write-Host "Running with S3 bucket storage..." -ForegroundColor Green
            $reportType = Read-Host "Enter report type (ce, co, ta, cur)"
            $bucketName = Read-Host "Enter S3 bucket name"
            
            switch ($reportType.ToLower()) {
                "ce" { $reportParam = "--ce" }
                "co" { $reportParam = "--co" }
                "ta" { $reportParam = "--ta" }
                "cur" { 
                    $reportParam = "--cur" 
                    $curDb = Read-Host "Enter CUR database name"
                    $curTable = Read-Host "Enter CUR table name"
                    $reportParam = "$reportParam --cur-db $curDb --cur-table $curTable"
                }
                default { 
                    Write-Host "Invalid report type. Using CostExplorer." -ForegroundColor Yellow
                    $reportParam = "--ce" 
                }
            }
            
            Invoke-Expression "$DockerBaseCmd $reportParam -b $bucketName"
            Read-Host "Press Enter to continue..."
        }
        "0" {
            Write-Host "Exiting..." -ForegroundColor Yellow
            exit
        }
        default {
            Write-Host "Invalid option. Press Enter to continue..." -ForegroundColor Red
            Read-Host
        }
    }
}