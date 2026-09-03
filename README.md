> ⚠️ **New contributors and AI agents: you MUST read [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) before taking any action.**

# EY Internship — Fraud Analytics
This project was carried out as part of an internship in the AI & Data department at EY, designed as a simulated consulting mission: the intern plays both the role of the client (TuniDistrib SA, a fictional retail company) and the EY consultant tasked with solving their business problem.

**Client Problem:** Detection of fraudulent transactions involving suppliers (shared bank accounts, fictitious suppliers, duplicate invoicing, statistical anomalies).

**Technical Approach:**
- Generation of interconnected synthetic data (transactions, suppliers, employees)
- Data cleaning and normalization (bank accounts, supplier names, supplier-specific thresholds)
- 3-Level Detection: Business rules, unsupervised Machine Learning (Isolation Forest), and collusion graph analysis
- Final reporting via a Power BI dashboard

**Context:** An educational project grounded in real-world statistics (EY Global Integrity Report, ACFE Report to the Nations) to validate the relevance of the topic.

## Project Structure

The project structure follows Python standards with a clear separation between data, scripts, and reports:

```
DATA/
├── README.md                 # This file
├── PROJECT_CONTEXT.md        # Technical context and current state of the project
├── requirements.txt          # Project dependencies
├── .gitignore                # Files ignored by Git
├── data/                     
│   └── raw/                  # Generated raw data and fraud logs
├── output_clean/             # Unique reference folder for processed and scored data
│   └── archive/              # Archived old files and intermediate states
├── scripts/
│   ├── 01_generation/        # Synthetic data generation and fraud injection
│   ├── 02_diagnostic/        # Exploratory analysis and raw data diagnostics
│   ├── 03_cleaning/          # Data cleaning and normalization
│   ├── 04_detection/         # Business rules, ML feature engineering, and collusion graphs
│   ├── 05_execution/         # Entry point for pipeline orchestration (run_pipeline.py)
│   └── 06_validation/        # Performance evaluation scripts (recall/precision)
├── notebooks/                # Jupyter Notebooks for analysis, ML training, and graph exploration
├── models/                   # Exported machine learning models (joblib)
├── reports/                  # Generated dashboards and analyses
└── tests/                    # Test datasets and experimental reports (e.g., test1_generalisation)
```

## Execution Order

To run the entire pipeline, execute the main orchestration script from the root directory:

```bash
python scripts/05_execution/run_pipeline.py --transactions data/raw/transactions.csv --fournisseurs data/raw/fournisseurs.csv --employes data/raw/employes.csv --output output_clean/transactions_scorees.csv
```
This single script orchestrates:
1. **Cleaning**: Normalizes the data.
2. **Business Rules (Level 1)**: Applies detection rules on the clean data.
3. **Machine Learning (Level 2)**: Loads the pre-trained Isolation Forest model and makes predictions.
4. **Collusion Graphs (Level 3)**: Detects collusion clusters using network analysis.
5. **Consolidation**: Computes the final risk score for each transaction.

To evaluate the pipeline against the injected fraud log:
```bash
python scripts/06_validation/run_eval.py
```
