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


### Installation
```bash
# Clone the repository
git clone <repository-url>
cd CostMinimizer

# Install dependencies
pip install -r requirements.txt

# Configure the tool
CostMinimizer --configure
```

### Quick Start
1. Configure AWS credentials:
```bash
CostMinimizer --configure
```

2. Run a basic cost analysis:
```bash
CostMinimizer -b -t -c  # Runs Cost Explorer, Trusted Advisor, and Compute Optimizer reports
```

3. Generate AI recommendations:
```bash
CostMinimizer -r -f report.xlsx  # Generates AI recommendations based on report data
```

### Operation Modes

1. CLI Mode (Default):
   ```bash
   # Run in CLI mode with interactive options
   CostMinimizer --mode cli
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
CostMinimizer -b

# Generate Trusted Advisor reports only
CostMinimizer -t

# Generate all reports with email notification
CostMinimizer -b -t -c -s user@example.com
```

2. Ask questions about cost data:
```bash
# Ask a specific question about costs
CostMinimizer -q "What are my top 3 AWS services by cost?" -f cost_report.xlsx
```


### Troubleshooting
1. Authentication Issues
- Error: "Unable to validate credentials"
  ```bash
  # Verify AWS credentials
  aws configure list
  # Reconfigure CostMinimizer
  CostMinimizer --configure
  ```

2. Report Generation Failures
- Check log file at `~/.CostMinimizer/CostMinimizer_tooling.log`
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

