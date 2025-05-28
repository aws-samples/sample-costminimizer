#!/bin/bash

# Base docker run command with common parameters
DOCKER_BASE_CMD="docker run -it -v ~/.aws:/root/.aws -v ~/cow:/root/cow -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN costminimizer"

# Function to display menu and get user choice
show_menu() {
    clear
    echo "=== CostMinimizer Docker Menu ==="
    echo "1. Run CostExplorer (--ce)"
    echo "2. Run ComputeOptimizer (--co)"
    echo "3. Run Trusted Advisor (--ta)"
    echo "4. Run CUR Reports (--cur)"
    echo "5. Configure CostMinimizer (--configure)"
    echo "6. Open bash shell in container"
    echo "7. Run with S3 bucket storage"
    echo "0. Exit"
    echo "================================="
    echo -n "Enter your choice [0-7]: "
    read choice
}

# Main loop
while true; do
    show_menu
    
    case $choice in
        1)
            echo "Running CostExplorer..."
            $DOCKER_BASE_CMD --ce
            read -p "Press Enter to continue..."
            ;;
        2)
            echo "Running ComputeOptimizer..."
            $DOCKER_BASE_CMD --co
            read -p "Press Enter to continue..."
            ;;
        3)
            echo "Running Trusted Advisor..."
            $DOCKER_BASE_CMD --ta
            read -p "Press Enter to continue..."
            ;;
        4)
            echo "Running CUR Reports..."
            read -p "Enter CUR database name: " cur_db
            read -p "Enter CUR table name: " cur_table
            $DOCKER_BASE_CMD --cur --cur-db "$cur_db" --cur-table "$cur_table"
            read -p "Press Enter to continue..."
            ;;
        5)
            echo "Configuring CostMinimizer..."
            $DOCKER_BASE_CMD --configure --auto-update-conf
            read -p "Press Enter to continue..."
            ;;
        6)
            echo "Opening bash shell in container..."
            docker run -it -v ~/.aws:/root/.aws -v ~/cow:/root/cow -e AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY -e AWS_SESSION_TOKEN --entrypoint /bin/bash costminimizer
            ;;
        7)
            echo "Running with S3 bucket storage..."
            read -p "Enter report type (ce, co, ta, cur): " report_type
            read -p "Enter S3 bucket name: " bucket_name
            
            case $report_type in
                ce|CE)
                    report_param="--ce"
                    ;;
                co|CO)
                    report_param="--co"
                    ;;
                ta|TA)
                    report_param="--ta"
                    ;;
                cur|CUR)
                    report_param="--cur"
                    read -p "Enter CUR database name: " cur_db
                    read -p "Enter CUR table name: " cur_table
                    report_param="$report_param --cur-db $cur_db --cur-table $cur_table"
                    ;;
                *)
                    echo "Invalid report type. Using CostExplorer."
                    report_param="--ce"
                    ;;
            esac
            
            $DOCKER_BASE_CMD $report_param -b "$bucket_name"
            read -p "Press Enter to continue..."
            ;;
        0)
            echo "Exiting..."
            exit 0
            ;;
        *)
            echo "Invalid option. Press Enter to continue..."
            read
            ;;
    esac
done