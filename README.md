# CostMinimizer: AI-Powered AWS Cost Optimization Tool

CostMinimizer is a comprehensive AWS cost analysis and optimization tool that leverages AWS Cost Explorer, Trusted Advisor,Compute Optimizer and Cost & Usage Report to provide actionable insights for optimizing your AWS infrastructure costs. CostMinimizer also provide actionable cost-saving recommendations powered by AI. It helps AWS users identify cost optimization opportunities, analyze spending patterns, and generate detailed reports with specific recommendations.

The tool combines data from multiple AWS cost management services to provide a holistic view of your AWS spending. It features automated report generation, AI-powered analysis using AWS Bedrock, and supports both CLI and module integration modes. Key features include:

- Comprehensive cost analysis across AWS accounts and services
- AI-powered recommendations for cost optimization
- Integration with AWS Cost Explorer, Trusted Advisor, and Compute Optimizer
- Automated report generation in Excel and PowerPoint formats
- Support for custom cost allocation tags and filtering
- Secure credential management and encryption capabilities
- Interactive CLI interface with configurable options

## Repository Structure
```

.
├── src/CostMinimizer/          # Main source code directory
│   ├── arguments/              # Command line argument parsing
│   ├── commands/               # CLI command implementations
│   ├── config/                 # Configuration management and database
│   ├── report_providers/       # Report generation providers
│   │   ├── ce_reports/         # Cost Explorer report implementations
│   │   ├── co_reports/         # Compute Optimizer report implementations
│   │   ├── cur_reports/        # Cost & Usage report implementations
│   │   └── ta_reports/         # Trusted Advisor report implementations
│   ├── report_output_handler/  # Report output formatting
│   └── security/               # Authentication and encryption
├── test/                       # Test files
├── requirements.txt            # Python dependencies
└── setup.py                    # python setup.py file
```

## Usage Instructions
### Prerequisites
- Python 3.8 or higher (tested on 3.13)
- AWS credentials configured with appropriate permissions
- Local database configuration (supported through config/database.py)
- The following AWS services enabled:
  - AWS Cost Explorer
  - AWS Cost and Usage Report CUR
  - AWS Trusted Advisor
  - AWS Compute Optimizer
  - AWS Organizations (optional)
  - AWS Bedrock (for AI-powered analysis)


### Installation and configuration
```bash
# Clone the repository
git clone git@github.com:aws-samples/sample-costminimizer.git
cd CostMinimizer

# Install dependencies
pip install -r requirements.txt

# Setup and install python tooling
python setup.py develop

# Configure the tool
CostMinimizer --configure
```

### Quick Start
```bash

1. Verify your AWS credentials:
aws sts get-caller-identity        # CostMinimizer is using the AWS credentials defined in environment variables or .aws/

(optional: you can automaticaly register the existing credentials as the default admin one of the tooling:
costminimizer --configure --auto-update-conf
Therefore reports will be saved into C:\Users\$USERNAME$\cow\$ACCOUNTID_CREDENTIALS$-2025-04-04-09-46\
)

2. List all options for the tooling:
CostMinimizer --help

3. Run a basic cost analysis:
CostMinimizer --ce --ta --co --cur # Runs Cost Explorer, Trusted Advisor, Compute Optimizer reports, and CUR Cost and Usage Reports

4. Generate AI recommendations:
CostMinimizer -r --ce --cur    # Generates AI recommendations based on report data

5. Ask genAI a question about the cost report:
CostMinimizer -q "based on the CostMinimizer.xlsx results provided in attached file, in the Accounts tab of the excel sheets, 
what is the cost of my AWS service for the year 2024 for the account nammed slepetre@amazon.com ?" -f "C:\Users\slepetre\cow\125538328000-2025-04-04-09-46\CostMinimizer.xlsx"
```

### Operation Modes

1. CLI Mode (Default):
   ```bash
   # Run in CLI mode with interactive options
   CostMinimizer --mode cli   # --mode cli is optional, default mode is this one, there is no need to specify --mode cli
   ```

2. Module Integration Mode:
   ```python
   from CostMinimizer import App
   app = App(config)
   app.main()
   ```

### More Detailed Examples
1. Generate specific reports:
```bash
# Generate Cost Explorer reports only
CostMinimizer --ce

# Generate Trusted Advisor reports only
CostMinimizer --ta

# Generate CUR Cost and Usage Reports only
CostMinimizer --cur

# Generate Compute Optimizer Reports only
CostMinimizer --co

# Generate all reports and send the result by email using -s option
CostMinimizer --ce --ta --co --cur -s user@example.com

# Generate CUR graviton reports for a specific CUR database and table (here AWS account 000065822619 for 2025 02)
costminimizer --cur --cur --cur-db customer_cur_data --cur-table cur_000065822619_202502 --checks cur_gravitoneccsavings cur_gravitonrdssavings cur_lambdaarmsavings --region us-east-1

```

2. Ask questions about cost data:
```bash
# Ask a specific question about costs
CostMinimizer -q "based on the CostMinimizer.xlsx results provided in attached file, in the Accounts tab of the excel sheets, what is the cost of my AWS service for the year 2024 for the account named slepetre@amazon.com ?" -f "C:\Users\slepetre\cow\125538328000-2025-04-03-11-08\CostMinimizer.xlsx"
```


### Troubleshooting
1. Authentication Issues
- Error: "Unable to validate credentials"
  ```bash
  # Verify AWS credentials
  aws configure list
  aws sts get-caller-identity        # CostMinimizer is using the AWS credentials defined in environment variables or .aws/

  # Reconfigure CostMinimizer
  CostMinimizer --configure --auto-update-conf    # Auto update the values of the configuration of the tooling
                                                  # Retreives the credentials from the environment variables, and configure tooling with these values
  ```

2. Report Generation Failures
- Check log file at `~/cow/CostMinimizer.log`
- Verify required AWS permissions
- Ensure Cost Explorer API is enabled

3. Database Issues
- Delete the SQLite database file and reconfigure:
  ```bash
  rm ~/cow/CostMinimizer.db
  CostMinimizer --configure
  ```

## Data Flow
CostMinimizer processes AWS cost data through multiple stages to generate comprehensive cost optimization recommendations.

```ascii
[AWS Services] --> [Data Collection] --> [Processing] --> [Analysis] --> [Output]
   |                    |                    |              |            |
   |                    |                    |              |            |
Cost Explorer    Fetch Raw Data     Data Aggregation    AI Analysis   Reports
Trusted Advisor  API Queries        Normalization       Cost Insights  Excel
Compute Opt.    Authentication     Transformation      Recommendations PowerPoint
Organizations   Cache Management    Tag Processing     Pattern Detection
```

Key Components:
- Arguments Parser: Flexible CLI argument handling
- Configuration Manager: Manages application settings and state
- Authentication Manager: Secure AWS credential handling
- Command Factory: Implements command pattern for operations
- Report Request Parser: Processes and validates report requests
- Database Integration: Stores configurations and report metadata
- AI Integration: Processes natural language cost queries
- Multiple Output Formats: Supports Excel and PowerPoint reporting

## Infrastructure

The AWS infrastructure includes:

Python tooling:
- `Tool`: Generates and sends monthly cost reports
  - Memory: 512MB
  - Runtime: Python 3.8+

IAM Roles:
- `CostExplorerReportLambdaIAMRole`: Provides permissions for:
  - Cost Explorer API access
  - Compute optimizer access
  - Cost and Usage Report
  - Organizations API access
  - SES email sending
  - S3 bucket access

